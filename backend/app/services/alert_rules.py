"""Transparent, rule-based Alert & Event Intelligence engine.

`run_alert_rules()` is the single entry point, called by `POST /alerts/run`
(routers/alerts.py) and by the seed script (db/seed_wells.py) against real synthetic data.
Every rule is a deterministic threshold/condition check against already-recorded data — no
machine learning, no prediction, no autonomous action. Where an equivalent live/unpersisted
check already exists elsewhere in the codebase (production.py's /issues, equipment.py's
/issues + equipment_health.py's compute_health/_zscore_anomaly, maintenance.py's /schedule,
cost_revenue.py's /alerts), this module reuses that logic directly (its private helpers, or
an equivalent query against the same tables/filters where no extractable helper exists) rather
than re-deriving it — see docs/data-model.md's Alerts section for the full 22-rule table and
the reasoning behind each reuse decision.

This module deliberately imports private helpers from several routers (a services -> routers
dependency, the reverse of the usual layering) because those routers already own the proven
query logic for their domain and this is the established "2nd/3rd consumer reuses a private
helper directly" pattern used throughout this project (e.g. cost_revenue.py importing
_resolve_scope from equipment.py). Kept in services/ (not folded into routers/alerts.py)
specifically so seed_wells.py can call run_alert_rules() directly without pulling in FastAPI.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.ai import Alert, AlertStatusHistory
from app.models.economics import ProductionLoss
from app.models.equipment import DowntimeEvent, Equipment, EquipmentReading, MaintenanceRecord
from app.models.field import Field, Well
from app.models.production import ProductionRecord, ProductionTarget
from app.routers.cost_revenue import (
    MAINTENANCE_COST_CURRENCY,
    _combine_money,
    _compute_scope_totals,
    _latest_period,
    _load_price_series,
    _margin_by_currency,
    _per_unit_by_currency,
)
from app.routers.equipment import _resolve_scope
from app.routers.maintenance import TERMINAL_STATUSES
from app.services.equipment_health import _zscore_anomaly
from app.services.system_settings import (
    get_alert_cost_per_bbl_increase_pct,
    get_alert_cost_per_boe_increase_pct,
    get_alert_downtime_high_threshold_hours,
    get_alert_equipment_health_attention_threshold,
    get_alert_equipment_health_critical_threshold,
    get_alert_high_financial_impact_threshold_usd,
    get_alert_high_lost_revenue_threshold_usd,
    get_alert_high_maintenance_cost_multiplier,
    get_alert_high_operating_cost_threshold_ngn,
    get_alert_high_operating_cost_threshold_usd,
    get_alert_margin_decline_pct,
    get_alert_maintenance_repeated_events_count,
    get_alert_maintenance_repeated_events_window_days,
    get_alert_production_below_target_pct,
    get_alert_production_decline_pct,
    get_alert_production_loss_high_threshold_bbl,
    get_alert_production_loss_repeated_events_count,
    get_alert_production_loss_repeated_events_window_days,
    get_alert_production_unusual_change_pct,
    get_boe_gas_factor,
    get_maintenance_schedule_lookahead_days,
)

ALERT_DISCLAIMER = (
    "Rule-based alert generated from recorded operational, production, maintenance, and "
    "financial data; an indicator requiring engineering or management review, not a "
    "guaranteed conclusion or autonomous action."
)

OPEN_STATES = ("new", "acknowledged", "investigating")
MANUAL_SOURCE = "manual"


@dataclass
class AlertCandidate:
    category: str
    alert_type: str
    severity: str
    title: str
    description: str
    dedup_key: str
    well_id: int | None = None
    field_id: int | None = None
    facility_id: int | None = None
    equipment_id: int | None = None
    maintenance_record_id: int | None = None
    production_loss_id: int | None = None
    threshold_value: float | None = None
    current_value: float | None = None
    unit: str | None = None
    recommended_action: str | None = None


@dataclass
class AlertRunResult:
    created: int
    updated: int
    auto_resolved: int
    by_category: dict[str, dict[str, int]]
    disclaimer_text: str


def _dedup_key(alert_type: str, scope_type: str, scope_id: int | str) -> str:
    return f"{alert_type}:{scope_type}:{scope_id}"


def _tiered_severity(current: float, threshold: float, tiers: list[tuple[float, str]]) -> str:
    """`tiers` is an ascending list of (ratio_of_threshold, severity). Returns the severity of
    the last tier whose ratio the current/threshold value has reached — e.g. tiers
    [(1.0,"medium"), (1.5,"high"), (2.0,"critical")] with current=2.2x threshold -> "critical"."""
    if threshold <= 0:
        return tiers[-1][1]
    ratio = current / threshold
    severity = tiers[0][1]
    for tier_ratio, tier_severity in tiers:
        if ratio >= tier_ratio:
            severity = tier_severity
    return severity


# ----- Production -----


def _generate_production_alerts(db: Session) -> list[AlertCandidate]:
    candidates: list[AlertCandidate] = []
    below_target_pct = get_alert_production_below_target_pct(db)
    decline_pct = get_alert_production_decline_pct(db)
    unusual_pct = get_alert_production_unusual_change_pct(db)

    reference_date = db.query(func.max(ProductionRecord.record_date)).scalar()
    active_wells = db.query(Well).filter(Well.status == "active").all()
    well_ids = [w.id for w in active_wells]

    # Batched once across all active wells, replacing what was previously one query per well
    # per lookup (record-on-date, prior record, target, 30-day window) inside the loop below —
    # same resolution rules as before (see _resolve_target/the per-well queries this replaces),
    # just computed as 4 queries total instead of up to 4×len(active_wells).
    record_by_well: dict[int, ProductionRecord] = {}
    records_30_by_well: dict[int, list[ProductionRecord]] = defaultdict(list)
    prev_record_by_well: dict[int, ProductionRecord] = {}
    target_by_well: dict[int, ProductionTarget] = {}

    if well_ids and reference_date is not None:
        window_30_start = reference_date - timedelta(days=29)

        for r in (
            db.query(ProductionRecord)
            .filter(ProductionRecord.well_id.in_(well_ids), ProductionRecord.record_date == reference_date)
            .all()
        ):
            record_by_well[r.well_id] = r

        for r in (
            db.query(ProductionRecord)
            .filter(
                ProductionRecord.well_id.in_(well_ids),
                ProductionRecord.record_date >= window_30_start,
                ProductionRecord.record_date <= reference_date,
            )
            .all()
        ):
            records_30_by_well[r.well_id].append(r)

        # Most recent record strictly before reference_date, per well — ORDER BY well_id then
        # record_date DESC means the first row seen per well_id is that well's most recent
        # prior record, exactly matching the per-well `.order_by(record_date.desc()).first()`
        # this replaces (not an approximation over a bounded window).
        for r in (
            db.query(ProductionRecord)
            .filter(ProductionRecord.well_id.in_(well_ids), ProductionRecord.record_date < reference_date)
            .order_by(ProductionRecord.well_id, ProductionRecord.record_date.desc())
            .all()
        ):
            prev_record_by_well.setdefault(r.well_id, r)

        # Same "most recent effective target" resolution as _resolve_target, batched.
        for t in (
            db.query(ProductionTarget)
            .filter(ProductionTarget.well_id.in_(well_ids), ProductionTarget.effective_date <= reference_date)
            .order_by(ProductionTarget.well_id, ProductionTarget.effective_date.desc())
            .all()
        ):
            target_by_well.setdefault(t.well_id, t)

    for well in active_wells if reference_date is not None else []:
        record = record_by_well.get(well.id)

        if record is not None:
            target = target_by_well.get(well.id)
            if target is not None and target.oil_target_bopd:
                deficit_pct = (target.oil_target_bopd - record.oil_bopd) / target.oil_target_bopd * 100
                if deficit_pct > below_target_pct:
                    severity = _tiered_severity(
                        deficit_pct, below_target_pct, [(1.0, "medium"), (2.0, "high"), (3.5, "critical")]
                    )
                    candidates.append(
                        AlertCandidate(
                            category="production",
                            alert_type="production_below_target",
                            severity=severity,
                            title=f"{well.well_id} — Production Below Target",
                            description=(
                                f"{well.well_id} oil production is {deficit_pct:.1f}% below the target of "
                                f"{target.oil_target_bopd:.1f} BOPD as of {reference_date} "
                                f"(actual {record.oil_bopd:.1f} BOPD)."
                            ),
                            well_id=well.id,
                            threshold_value=below_target_pct,
                            current_value=round(deficit_pct, 1),
                            unit="%",
                            recommended_action=(
                                "Review well performance and choke/artificial-lift settings; confirm the "
                                "target still reflects current conditions."
                            ),
                            dedup_key=_dedup_key("production_below_target", "well", well.id),
                        )
                    )

            prev_record = prev_record_by_well.get(well.id)
            if prev_record is not None and prev_record.oil_bopd > 0:
                swing = abs(record.oil_bopd - prev_record.oil_bopd) / prev_record.oil_bopd * 100
                if swing > unusual_pct:
                    candidates.append(
                        AlertCandidate(
                            category="production",
                            alert_type="unusual_production_change",
                            severity="low",
                            title=f"{well.well_id} — Unusual Production Change",
                            description=(
                                f"{well.well_id} oil production moved {swing:.1f}% day-over-day "
                                f"({prev_record.oil_bopd:.1f} -> {record.oil_bopd:.1f} BOPD)."
                            ),
                            well_id=well.id,
                            threshold_value=unusual_pct,
                            current_value=round(swing, 1),
                            unit="%",
                            recommended_action=(
                                "Confirm whether this reflects a planned operating change (e.g. a choke "
                                "adjustment) or requires investigation."
                            ),
                            dedup_key=_dedup_key("unusual_production_change", "well", well.id),
                        )
                    )

        records_30 = records_30_by_well.get(well.id, [])
        if len(records_30) >= 14:
            avg_30 = sum(r.oil_bopd for r in records_30) / len(records_30)
            window_7_start = reference_date - timedelta(days=6)
            records_7 = [r for r in records_30 if r.record_date >= window_7_start]
            if records_7 and avg_30 > 0:
                avg_7 = sum(r.oil_bopd for r in records_7) / len(records_7)
                decline = (avg_30 - avg_7) / avg_30 * 100
                if decline > decline_pct:
                    severity = _tiered_severity(
                        decline, decline_pct, [(1.0, "medium"), (1.667, "high"), (2.667, "critical")]
                    )
                    candidates.append(
                        AlertCandidate(
                            category="production",
                            alert_type="production_decline",
                            severity=severity,
                            title=f"{well.well_id} — Production Decline",
                            description=(
                                f"{well.well_id}'s trailing 7-day average oil production ({avg_7:.1f} BOPD) "
                                f"is {decline:.1f}% below its trailing 30-day average ({avg_30:.1f} BOPD)."
                            ),
                            well_id=well.id,
                            threshold_value=decline_pct,
                            current_value=round(decline, 1),
                            unit="%",
                            recommended_action=(
                                "Investigate for possible reservoir decline, equipment issues, or choke "
                                "changes."
                            ),
                            dedup_key=_dedup_key("production_decline", "well", well.id),
                        )
                    )

    # Production outage — reuses production.py's /issues conditions.
    down_events = (
        db.query(DowntimeEvent).filter(DowntimeEvent.end_time.is_(None), DowntimeEvent.well_id.isnot(None)).all()
    )
    down_well_ids = {e.well_id for e in down_events if e.well_id is not None}

    zero_well_ids: set[int] = set()
    if reference_date is not None:
        active_well_ids = {w.id for w in active_wells}
        zero_records = (
            db.query(ProductionRecord)
            .filter(
                ProductionRecord.record_date == reference_date,
                ProductionRecord.oil_bopd == 0,
                ProductionRecord.gas_mscfd == 0,
            )
            .all()
        )
        zero_well_ids = {r.well_id for r in zero_records if r.well_id in active_well_ids}

    outage_well_ids = down_well_ids | zero_well_ids
    if outage_well_ids:
        wells_by_id = {w.id: w for w in db.query(Well).filter(Well.id.in_(outage_well_ids)).all()}
        for well_id in outage_well_ids:
            well = wells_by_id.get(well_id)
            if well is None:
                continue
            reason = (
                "an open downtime event"
                if well_id in down_well_ids
                else f"zero recorded production on {reference_date}"
            )
            candidates.append(
                AlertCandidate(
                    category="production",
                    alert_type="production_outage",
                    severity="critical",
                    title=f"{well.well_id} — Production Outage",
                    description=f"{well.well_id} currently shows {reason}.",
                    well_id=well.id,
                    recommended_action="Dispatch field operations to confirm well status and restore production.",
                    dedup_key=_dedup_key("production_outage", "well", well.id),
                )
            )

    return candidates


# ----- Equipment -----


def _generate_equipment_alerts(db: Session) -> list[AlertCandidate]:
    candidates: list[AlertCandidate] = []
    attention_threshold = get_alert_equipment_health_attention_threshold(db)
    critical_threshold = get_alert_equipment_health_critical_threshold(db)
    window_30d = datetime.now(timezone.utc) - timedelta(days=30)

    for equipment in db.query(Equipment).all():
        field_id, _, facility_id, _, well_id, _ = _resolve_scope(equipment)

        if equipment.status == "failed":
            candidates.append(
                AlertCandidate(
                    category="equipment",
                    alert_type="equipment_failure",
                    severity="critical",
                    title=f"{equipment.equipment_tag} — Equipment Failure",
                    description=(
                        f"{equipment.equipment_tag} ({equipment.name or equipment.equipment_tag}) status "
                        "is Failed."
                    ),
                    equipment_id=equipment.id,
                    well_id=well_id,
                    field_id=field_id,
                    facility_id=facility_id,
                    recommended_action="Schedule corrective/emergency maintenance and assess production impact.",
                    dedup_key=_dedup_key("equipment_failure", "equipment", equipment.id),
                )
            )
        elif equipment.health_score is not None and equipment.health_score < critical_threshold:
            candidates.append(
                AlertCandidate(
                    category="equipment",
                    alert_type="equipment_critical_health",
                    severity="critical",
                    title=f"{equipment.equipment_tag} — Critical Equipment Health",
                    description=(
                        f"{equipment.equipment_tag}'s health score is {equipment.health_score:.1f}, below "
                        f"the critical threshold of {critical_threshold:.0f}."
                    ),
                    equipment_id=equipment.id,
                    well_id=well_id,
                    field_id=field_id,
                    facility_id=facility_id,
                    threshold_value=critical_threshold,
                    current_value=equipment.health_score,
                    unit="score",
                    recommended_action=(
                        "Prioritize inspection and maintenance; consider taking this equipment offline "
                        "for review."
                    ),
                    dedup_key=_dedup_key("equipment_critical_health", "equipment", equipment.id),
                )
            )
        elif equipment.health_score is not None and equipment.health_score < attention_threshold:
            candidates.append(
                AlertCandidate(
                    category="equipment",
                    alert_type="equipment_low_health",
                    severity="high",
                    title=f"{equipment.equipment_tag} — Low Equipment Health",
                    description=(
                        f"{equipment.equipment_tag}'s health score is {equipment.health_score:.1f}, below "
                        f"the attention threshold of {attention_threshold:.0f}."
                    ),
                    equipment_id=equipment.id,
                    well_id=well_id,
                    field_id=field_id,
                    facility_id=facility_id,
                    threshold_value=attention_threshold,
                    current_value=equipment.health_score,
                    unit="score",
                    recommended_action="Schedule a maintenance inspection before the condition worsens.",
                    dedup_key=_dedup_key("equipment_low_health", "equipment", equipment.id),
                )
            )

        def _readings(parameter: str, equipment_id: int = equipment.id) -> list[float]:
            rows = (
                db.query(EquipmentReading)
                .filter(
                    EquipmentReading.equipment_id == equipment_id,
                    EquipmentReading.parameter == parameter,
                    EquipmentReading.reading_at >= window_30d,
                )
                .order_by(EquipmentReading.reading_at)
                .all()
            )
            return [r.value for r in rows]

        current_readings = _readings("current")
        flow_readings = _readings("flow")
        anomaly_param, anomaly_value = None, None
        if _zscore_anomaly(current_readings):
            anomaly_param, anomaly_value = "current", current_readings[-1]
        elif _zscore_anomaly(flow_readings):
            anomaly_param, anomaly_value = "flow", flow_readings[-1]
        if anomaly_param is not None:
            candidates.append(
                AlertCandidate(
                    category="equipment",
                    alert_type="abnormal_equipment_readings",
                    severity="medium",
                    title=f"{equipment.equipment_tag} — Abnormal Equipment Readings",
                    description=(
                        f"{equipment.equipment_tag}'s latest {anomaly_param} reading "
                        f"({anomaly_value:.2f}) deviates more than 2 standard deviations from its "
                        "recent trailing average."
                    ),
                    equipment_id=equipment.id,
                    well_id=well_id,
                    field_id=field_id,
                    facility_id=facility_id,
                    current_value=round(anomaly_value, 2),
                    unit=anomaly_param,
                    recommended_action="Verify sensor calibration and inspect equipment for developing issues.",
                    dedup_key=_dedup_key("abnormal_equipment_readings", "equipment", equipment.id),
                )
            )

    return candidates


# ----- Maintenance -----


def _generate_maintenance_alerts(db: Session) -> list[AlertCandidate]:
    candidates: list[AlertCandidate] = []
    today = date.today()
    lookahead_days = get_maintenance_schedule_lookahead_days(db)
    repeated_count = get_alert_maintenance_repeated_events_count(db)
    repeated_window_days = get_alert_maintenance_repeated_events_window_days(db)

    def _overdue_severity(days_overdue: int) -> str:
        if days_overdue <= 7:
            return "medium"
        if days_overdue <= 30:
            return "high"
        return "critical"

    active_records = (
        db.query(MaintenanceRecord)
        .options(joinedload(MaintenanceRecord.equipment))
        .filter(
            MaintenanceRecord.status.notin_(TERMINAL_STATUSES),
            MaintenanceRecord.planned_completion_date.isnot(None),
        )
        .all()
    )
    for record in active_records:
        if record.equipment is None:
            continue
        days = (record.planned_completion_date - today).days
        field_id, _, facility_id, _, well_id, _ = _resolve_scope(record.equipment)
        label = record.work_order_number or str(record.id)
        if days < 0:
            days_overdue = -days
            candidates.append(
                AlertCandidate(
                    category="maintenance",
                    alert_type="maintenance_overdue",
                    severity=_overdue_severity(days_overdue),
                    title=f"{label} — Maintenance Overdue",
                    description=(
                        f"Work order {label} for {record.equipment.equipment_tag} was due "
                        f"{record.planned_completion_date} and is {days_overdue} day(s) overdue."
                    ),
                    equipment_id=record.equipment_id,
                    well_id=well_id,
                    field_id=field_id,
                    facility_id=facility_id,
                    maintenance_record_id=record.id,
                    current_value=days_overdue,
                    unit="days overdue",
                    recommended_action="Reschedule or complete this work order as soon as possible.",
                    dedup_key=_dedup_key("maintenance_overdue", "work_order", record.id),
                )
            )
        elif days <= lookahead_days:
            candidates.append(
                AlertCandidate(
                    category="maintenance",
                    alert_type="maintenance_due_soon",
                    severity="low",
                    title=f"{label} — Maintenance Due Soon",
                    description=(
                        f"Work order {label} for {record.equipment.equipment_tag} is due "
                        f"{record.planned_completion_date} ({days} day(s) away)."
                    ),
                    equipment_id=record.equipment_id,
                    well_id=well_id,
                    field_id=field_id,
                    facility_id=facility_id,
                    maintenance_record_id=record.id,
                    threshold_value=lookahead_days,
                    current_value=days,
                    unit="days",
                    recommended_action=(
                        "Confirm scheduling and parts/technician availability ahead of the due date."
                    ),
                    dedup_key=_dedup_key("maintenance_due_soon", "work_order", record.id),
                )
            )

    for equipment in db.query(Equipment).filter(Equipment.next_maintenance_due.isnot(None)).all():
        days = (equipment.next_maintenance_due - today).days
        field_id, _, facility_id, _, well_id, _ = _resolve_scope(equipment)
        if days < 0:
            days_overdue = -days
            candidates.append(
                AlertCandidate(
                    category="maintenance",
                    alert_type="maintenance_overdue",
                    severity=_overdue_severity(days_overdue),
                    title=f"{equipment.equipment_tag} — Maintenance Overdue",
                    description=(
                        f"{equipment.equipment_tag}'s scheduled maintenance was due "
                        f"{equipment.next_maintenance_due} and is {days_overdue} day(s) overdue."
                    ),
                    equipment_id=equipment.id,
                    well_id=well_id,
                    field_id=field_id,
                    facility_id=facility_id,
                    current_value=days_overdue,
                    unit="days overdue",
                    recommended_action="Schedule a work order for this equipment as soon as possible.",
                    dedup_key=_dedup_key("maintenance_overdue", "equipment", equipment.id),
                )
            )
        elif days <= lookahead_days:
            candidates.append(
                AlertCandidate(
                    category="maintenance",
                    alert_type="maintenance_due_soon",
                    severity="low",
                    title=f"{equipment.equipment_tag} — Maintenance Due Soon",
                    description=(
                        f"{equipment.equipment_tag}'s scheduled maintenance is due "
                        f"{equipment.next_maintenance_due} ({days} day(s) away)."
                    ),
                    equipment_id=equipment.id,
                    well_id=well_id,
                    field_id=field_id,
                    facility_id=facility_id,
                    threshold_value=lookahead_days,
                    current_value=days,
                    unit="days",
                    recommended_action="Confirm scheduling ahead of the due date.",
                    dedup_key=_dedup_key("maintenance_due_soon", "equipment", equipment.id),
                )
            )

    critical_records = (
        db.query(MaintenanceRecord)
        .options(joinedload(MaintenanceRecord.equipment))
        .filter(MaintenanceRecord.priority == "critical", MaintenanceRecord.status.notin_(TERMINAL_STATUSES))
        .all()
    )
    for record in critical_records:
        if record.equipment is None:
            continue
        field_id, _, facility_id, _, well_id, _ = _resolve_scope(record.equipment)
        label = record.work_order_number or str(record.id)
        candidates.append(
            AlertCandidate(
                category="maintenance",
                alert_type="critical_maintenance",
                severity="critical",
                title=f"{label} — Critical Maintenance",
                description=(
                    f"Work order {label} for {record.equipment.equipment_tag} is flagged critical "
                    f"priority and still {record.status}."
                ),
                equipment_id=record.equipment_id,
                well_id=well_id,
                field_id=field_id,
                facility_id=facility_id,
                maintenance_record_id=record.id,
                recommended_action="Prioritize this work order ahead of non-critical maintenance.",
                dedup_key=_dedup_key("critical_maintenance", "work_order", record.id),
            )
        )

    window_start = today - timedelta(days=repeated_window_days)
    repeated_records = (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.maintenance_type.in_(["corrective", "emergency"]),
            MaintenanceRecord.start_date.isnot(None),
            MaintenanceRecord.start_date >= window_start,
            MaintenanceRecord.equipment_id.isnot(None),
        )
        .all()
    )
    counts: dict[int, int] = {}
    for record in repeated_records:
        counts[record.equipment_id] = counts.get(record.equipment_id, 0) + 1
    for equipment_id, count in counts.items():
        if count < repeated_count:
            continue
        equipment = db.get(Equipment, equipment_id)
        if equipment is None:
            continue
        field_id, _, facility_id, _, well_id, _ = _resolve_scope(equipment)
        candidates.append(
            AlertCandidate(
                category="maintenance",
                alert_type="repeated_maintenance_events",
                severity="high",
                title=f"{equipment.equipment_tag} — Repeated Maintenance Events",
                description=(
                    f"{equipment.equipment_tag} has had {count} corrective/emergency maintenance events "
                    f"in the last {repeated_window_days} days."
                ),
                equipment_id=equipment.id,
                well_id=well_id,
                field_id=field_id,
                facility_id=facility_id,
                threshold_value=repeated_count,
                current_value=count,
                unit="events",
                recommended_action=(
                    "Investigate for a recurring root cause rather than treating each event in isolation."
                ),
                dedup_key=_dedup_key("repeated_maintenance_events", "equipment", equipment.id),
            )
        )

    return candidates


# ----- Production Loss -----


def _generate_production_loss_alerts(db: Session) -> list[AlertCandidate]:
    candidates: list[AlertCandidate] = []
    today = date.today()
    high_loss_threshold = get_alert_production_loss_high_threshold_bbl(db)
    repeated_count = get_alert_production_loss_repeated_events_count(db)
    repeated_window_days = get_alert_production_loss_repeated_events_window_days(db)
    downtime_threshold = get_alert_downtime_high_threshold_hours(db)
    lost_revenue_threshold = get_alert_high_lost_revenue_threshold_usd(db)

    window_30 = today - timedelta(days=30)
    losses = (
        db.query(ProductionLoss)
        .options(joinedload(ProductionLoss.well), joinedload(ProductionLoss.equipment))
        .filter(ProductionLoss.loss_date >= window_30)
        .all()
    )
    for loss in losses:
        field_id = facility_id = well_id = None
        if loss.well_id and loss.well is not None:
            well_id = loss.well.id
            facility_id = loss.well.facility_id
            field_id = loss.well.facility.field_id if loss.well.facility else None
        elif loss.equipment_id and loss.equipment is not None:
            field_id, _, facility_id, _, well_id, _ = _resolve_scope(loss.equipment)
        label = (
            loss.well.well_id
            if loss.well is not None
            else (loss.equipment.equipment_tag if loss.equipment is not None else f"Loss #{loss.id}")
        )

        if loss.estimated_bopd_lost is not None and loss.estimated_bopd_lost > high_loss_threshold:
            severity = _tiered_severity(
                loss.estimated_bopd_lost, high_loss_threshold, [(1.0, "medium"), (2.0, "high"), (4.0, "critical")]
            )
            candidates.append(
                AlertCandidate(
                    category="production_loss",
                    alert_type="high_production_loss",
                    severity=severity,
                    title=f"{label} — High Production Loss",
                    description=(
                        f"{label}'s production-loss event on {loss.loss_date} shows an estimated "
                        f"{loss.estimated_bopd_lost:.1f} bbl lost, above the {high_loss_threshold:.0f} bbl "
                        "threshold."
                    ),
                    well_id=well_id,
                    field_id=field_id,
                    facility_id=facility_id,
                    equipment_id=loss.equipment_id,
                    production_loss_id=loss.id,
                    threshold_value=high_loss_threshold,
                    current_value=round(loss.estimated_bopd_lost, 1),
                    unit="bbl",
                    recommended_action=(
                        "Review the linked failure/downtime cause and confirm corrective action was taken."
                    ),
                    dedup_key=_dedup_key("high_production_loss", "loss_event", loss.id),
                )
            )

        if loss.downtime_hours is not None and loss.downtime_hours > downtime_threshold:
            severity = _tiered_severity(
                loss.downtime_hours, downtime_threshold, [(1.0, "medium"), (2.0, "high"), (4.0, "critical")]
            )
            candidates.append(
                AlertCandidate(
                    category="production_loss",
                    alert_type="high_downtime",
                    severity=severity,
                    title=f"{label} — High Downtime",
                    description=(
                        f"{label}'s production-loss event on {loss.loss_date} recorded "
                        f"{loss.downtime_hours:.1f} hours of downtime, above the "
                        f"{downtime_threshold:.0f}-hour threshold."
                    ),
                    well_id=well_id,
                    field_id=field_id,
                    facility_id=facility_id,
                    equipment_id=loss.equipment_id,
                    production_loss_id=loss.id,
                    threshold_value=downtime_threshold,
                    current_value=round(loss.downtime_hours, 1),
                    unit="hours",
                    recommended_action=(
                        "Review maintenance response time and identify ways to reduce downtime duration."
                    ),
                    dedup_key=_dedup_key("high_downtime", "loss_event", loss.id),
                )
            )

        if (
            loss.estimated_revenue_impact is not None
            and loss.currency == "USD"
            and loss.estimated_revenue_impact > lost_revenue_threshold
        ):
            severity = _tiered_severity(
                loss.estimated_revenue_impact,
                lost_revenue_threshold,
                [(1.0, "medium"), (2.0, "high"), (4.0, "critical")],
            )
            candidates.append(
                AlertCandidate(
                    category="production_loss",
                    alert_type="high_estimated_lost_revenue",
                    severity=severity,
                    title=f"{label} — High Estimated Lost Revenue",
                    description=(
                        f"{label}'s production-loss event on {loss.loss_date} has an estimated USD "
                        f"{loss.estimated_revenue_impact:,.0f} revenue impact, above the USD "
                        f"{lost_revenue_threshold:,.0f} threshold."
                    ),
                    well_id=well_id,
                    field_id=field_id,
                    facility_id=facility_id,
                    equipment_id=loss.equipment_id,
                    production_loss_id=loss.id,
                    threshold_value=lost_revenue_threshold,
                    current_value=round(loss.estimated_revenue_impact, 2),
                    unit="USD",
                    recommended_action="Escalate to management for financial impact review.",
                    dedup_key=_dedup_key("high_estimated_lost_revenue", "loss_event", loss.id),
                )
            )

    window_repeated = today - timedelta(days=repeated_window_days)
    repeated_losses = (
        db.query(ProductionLoss)
        .filter(ProductionLoss.loss_date >= window_repeated, ProductionLoss.well_id.isnot(None))
        .all()
    )
    counts: dict[int, int] = {}
    for loss in repeated_losses:
        counts[loss.well_id] = counts.get(loss.well_id, 0) + 1
    for well_id, count in counts.items():
        if count < repeated_count:
            continue
        well = db.get(Well, well_id)
        if well is None:
            continue
        candidates.append(
            AlertCandidate(
                category="production_loss",
                alert_type="repeated_production_loss_events",
                severity="high",
                title=f"{well.well_id} — Repeated Production-Loss Events",
                description=(
                    f"{well.well_id} has had {count} production-loss events in the last "
                    f"{repeated_window_days} days."
                ),
                well_id=well.id,
                field_id=well.facility.field_id if well.facility else None,
                facility_id=well.facility_id,
                threshold_value=repeated_count,
                current_value=count,
                unit="events",
                recommended_action="Investigate for a recurring root cause across these loss events.",
                dedup_key=_dedup_key("repeated_production_loss_events", "well", well.id),
            )
        )

    return candidates


# ----- Economics -----


def _generate_economics_alerts(db: Session) -> list[AlertCandidate]:
    candidates: list[AlertCandidate] = []
    this_start, this_end = _latest_period(db)
    prev_end = this_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    boe_gas_factor = get_boe_gas_factor(db)
    price_series = _load_price_series(db)

    high_cost_by_currency = {
        "USD": get_alert_high_operating_cost_threshold_usd(db),
        "NGN": get_alert_high_operating_cost_threshold_ngn(db),
    }
    cost_per_bbl_pct = get_alert_cost_per_bbl_increase_pct(db)
    cost_per_boe_pct = get_alert_cost_per_boe_increase_pct(db)
    margin_decline_pct = get_alert_margin_decline_pct(db)
    maint_cost_multiplier = get_alert_high_maintenance_cost_multiplier(db)
    financial_impact_threshold = get_alert_high_financial_impact_threshold_usd(db)

    fields = db.query(Field).all()
    for field in fields:
        this_totals = _compute_scope_totals(db, this_start, this_end, price_series, boe_gas_factor, field_id=field.id)
        prev_totals = _compute_scope_totals(db, prev_start, prev_end, price_series, boe_gas_factor, field_id=field.id)
        this_cost = _combine_money(
            this_totals["operating_dict"],
            {MAINTENANCE_COST_CURRENCY: this_totals["maintenance_total"]} if this_totals["maintenance_total"] else {},
        )
        prev_cost = _combine_money(
            prev_totals["operating_dict"],
            {MAINTENANCE_COST_CURRENCY: prev_totals["maintenance_total"]} if prev_totals["maintenance_total"] else {},
        )

        for currency, amount in this_totals["operating_dict"].items():
            threshold = high_cost_by_currency.get(currency)
            if threshold and amount > threshold:
                severity = _tiered_severity(amount, threshold, [(1.0, "medium"), (1.5, "high"), (2.0, "critical")])
                candidates.append(
                    AlertCandidate(
                        category="economics",
                        alert_type="high_operating_cost",
                        severity=severity,
                        title=f"{field.name} — High Operating Cost",
                        description=(
                            f"{field.name}'s operating cost this period is {currency} {amount:,.0f}, above "
                            f"the {currency} {threshold:,.0f} threshold."
                        ),
                        field_id=field.id,
                        threshold_value=threshold,
                        current_value=round(amount, 2),
                        unit=currency,
                        recommended_action="Review cost entries for this field and confirm they reflect expected activity.",
                        dedup_key=_dedup_key("high_operating_cost", "field_currency", f"{field.id}:{currency}"),
                    )
                )

        this_cost_per_bbl = _per_unit_by_currency(this_cost, this_totals["oil_total"])
        prev_cost_per_bbl = _per_unit_by_currency(prev_cost, prev_totals["oil_total"])
        for currency, this_value in this_cost_per_bbl.items():
            prev_value = prev_cost_per_bbl.get(currency)
            if prev_value and prev_value > 0 and this_value > prev_value * (1 + cost_per_bbl_pct / 100):
                pct = (this_value - prev_value) / prev_value * 100
                severity = _tiered_severity(pct, cost_per_bbl_pct, [(1.0, "medium"), (2.0, "high")])
                candidates.append(
                    AlertCandidate(
                        category="economics",
                        alert_type="rising_cost_per_barrel",
                        severity=severity,
                        title=f"{field.name} — Rising Cost per Barrel",
                        description=(
                            f"{field.name}'s cost per barrel is up {pct:.1f}% month-over-month "
                            f"({currency} {prev_value:,.2f} -> {currency} {this_value:,.2f})."
                        ),
                        field_id=field.id,
                        threshold_value=cost_per_bbl_pct,
                        current_value=round(pct, 1),
                        unit="%",
                        recommended_action="Investigate the cost categories driving the increase.",
                        dedup_key=_dedup_key("rising_cost_per_barrel", "field_currency", f"{field.id}:{currency}"),
                    )
                )

        this_cost_per_boe = _per_unit_by_currency(this_cost, this_totals["boe_total"])
        prev_cost_per_boe = _per_unit_by_currency(prev_cost, prev_totals["boe_total"])
        for currency, this_value in this_cost_per_boe.items():
            prev_value = prev_cost_per_boe.get(currency)
            if prev_value and prev_value > 0 and this_value > prev_value * (1 + cost_per_boe_pct / 100):
                pct = (this_value - prev_value) / prev_value * 100
                severity = _tiered_severity(pct, cost_per_boe_pct, [(1.0, "medium"), (2.0, "high")])
                candidates.append(
                    AlertCandidate(
                        category="economics",
                        alert_type="rising_cost_per_boe",
                        severity=severity,
                        title=f"{field.name} — Rising Cost per BOE",
                        description=(
                            f"{field.name}'s cost per BOE is up {pct:.1f}% month-over-month "
                            f"({currency} {prev_value:,.2f} -> {currency} {this_value:,.2f})."
                        ),
                        field_id=field.id,
                        threshold_value=cost_per_boe_pct,
                        current_value=round(pct, 1),
                        unit="%",
                        recommended_action="Investigate the cost categories driving the increase.",
                        dedup_key=_dedup_key("rising_cost_per_boe", "field_currency", f"{field.id}:{currency}"),
                    )
                )

        this_margin, _ = _margin_by_currency(this_totals["revenue_total"], this_cost)
        prev_margin, _ = _margin_by_currency(prev_totals["revenue_total"], prev_cost)
        for currency, this_value in this_margin.items():
            prev_value = prev_margin.get(currency)
            if prev_value and prev_value > 0 and this_value < prev_value * (1 - margin_decline_pct / 100):
                pct = (prev_value - this_value) / prev_value * 100
                candidates.append(
                    AlertCandidate(
                        category="economics",
                        alert_type="declining_operating_margin",
                        severity="high",
                        title=f"{field.name} — Declining Operating Margin",
                        description=(
                            f"{field.name}'s estimated operating margin is down {pct:.1f}% month-over-month "
                            f"({currency} {prev_value:,.0f} -> {currency} {this_value:,.0f})."
                        ),
                        field_id=field.id,
                        threshold_value=margin_decline_pct,
                        current_value=round(pct, 1),
                        unit="%",
                        recommended_action="Review the revenue and cost drivers behind the margin decline.",
                        dedup_key=_dedup_key(
                            "declining_operating_margin", "field_currency", f"{field.id}:{currency}"
                        ),
                    )
                )

    window_30 = this_end - timedelta(days=30)
    impact_losses = (
        db.query(ProductionLoss)
        .options(joinedload(ProductionLoss.well), joinedload(ProductionLoss.equipment))
        .filter(
            ProductionLoss.loss_date >= window_30,
            ProductionLoss.currency == "USD",
            ProductionLoss.estimated_revenue_impact.isnot(None),
        )
        .all()
    )
    impact_by_field: dict[int, float] = {}
    for loss in impact_losses:
        field_id = None
        if loss.well_id and loss.well is not None and loss.well.facility:
            field_id = loss.well.facility.field_id
        elif loss.equipment_id and loss.equipment is not None:
            field_id, _, _, _, _, _ = _resolve_scope(loss.equipment)
        if field_id is not None:
            impact_by_field[field_id] = impact_by_field.get(field_id, 0.0) + loss.estimated_revenue_impact
    for field_id, total_impact in impact_by_field.items():
        if total_impact <= financial_impact_threshold:
            continue
        field = db.get(Field, field_id)
        if field is None:
            continue
        severity = _tiered_severity(total_impact, financial_impact_threshold, [(1.0, "high"), (2.0, "critical")])
        candidates.append(
            AlertCandidate(
                category="economics",
                alert_type="high_estimated_financial_impact",
                severity=severity,
                title=f"{field.name} — High Estimated Financial Impact",
                description=(
                    f"{field.name}'s trailing-30-day estimated production-loss revenue impact totals USD "
                    f"{total_impact:,.0f}, above the USD {financial_impact_threshold:,.0f} threshold."
                ),
                field_id=field.id,
                threshold_value=financial_impact_threshold,
                current_value=round(total_impact, 2),
                unit="USD",
                recommended_action="Escalate for management review of the underlying production-loss events.",
                dedup_key=_dedup_key("high_estimated_financial_impact", "field", field.id),
            )
        )

    window_start_90 = this_end - timedelta(days=90)
    maintenance_records = (
        db.query(MaintenanceRecord)
        .options(joinedload(MaintenanceRecord.equipment))
        .filter(MaintenanceRecord.start_date.isnot(None), MaintenanceRecord.start_date >= window_start_90)
        .all()
    )
    cost_by_equipment: dict[int, float] = {}
    for r in maintenance_records:
        if r.equipment is None:
            continue
        cost_by_equipment[r.equipment_id] = cost_by_equipment.get(r.equipment_id, 0.0) + (r.cost or 0)
    if cost_by_equipment:
        fleet_avg = sum(cost_by_equipment.values()) / len(cost_by_equipment)
        if fleet_avg > 0:
            for equipment_id, total in cost_by_equipment.items():
                if total <= fleet_avg * maint_cost_multiplier:
                    continue
                equipment = db.get(Equipment, equipment_id)
                if equipment is None:
                    continue
                field_id, _, facility_id, _, well_id, _ = _resolve_scope(equipment)
                candidates.append(
                    AlertCandidate(
                        category="economics",
                        alert_type="high_maintenance_cost",
                        severity="medium",
                        title=f"{equipment.equipment_tag} — High Maintenance Cost",
                        description=(
                            f"{equipment.equipment_tag}'s trailing-90-day maintenance cost is USD "
                            f"{total:,.0f}, more than {maint_cost_multiplier:.1f}x the fleet average of "
                            f"USD {fleet_avg:,.0f}."
                        ),
                        equipment_id=equipment.id,
                        well_id=well_id,
                        field_id=field_id,
                        facility_id=facility_id,
                        threshold_value=round(fleet_avg * maint_cost_multiplier, 2),
                        current_value=round(total, 2),
                        unit="USD",
                        recommended_action=(
                            "Review this equipment's maintenance history for a recurring or systemic issue."
                        ),
                        dedup_key=_dedup_key("high_maintenance_cost", "equipment", equipment.id),
                    )
                )

    return candidates


# ----- Orchestrator -----


def run_alert_rules(db: Session) -> AlertRunResult:
    now = datetime.now(timezone.utc)

    generators = (
        ("production", _generate_production_alerts),
        ("equipment", _generate_equipment_alerts),
        ("maintenance", _generate_maintenance_alerts),
        ("production_loss", _generate_production_loss_alerts),
        ("economics", _generate_economics_alerts),
    )

    by_category: dict[str, dict[str, int]] = {
        category: {"created": 0, "updated": 0} for category, _ in generators
    }
    seen_keys: set[str] = set()
    created = 0
    updated = 0

    for category, generator in generators:
        for candidate in generator(db):
            seen_keys.add(candidate.dedup_key)
            existing = (
                db.query(Alert)
                .filter(Alert.dedup_key == candidate.dedup_key, Alert.state.in_(OPEN_STATES))
                .first()
            )
            if existing is not None:
                existing.severity = candidate.severity
                existing.title = candidate.title
                existing.description = candidate.description
                existing.threshold_value = candidate.threshold_value
                existing.current_value = candidate.current_value
                existing.unit = candidate.unit
                existing.recommended_action = candidate.recommended_action
                existing.occurrence_count += 1
                existing.last_detected_at = now
                updated += 1
                by_category[category]["updated"] += 1
            else:
                alert = Alert(
                    alert_type=candidate.alert_type,
                    category=candidate.category,
                    source_module=candidate.category,
                    severity=candidate.severity,
                    state="new",
                    title=candidate.title,
                    description=candidate.description,
                    recommended_action=candidate.recommended_action,
                    well_id=candidate.well_id,
                    field_id=candidate.field_id,
                    facility_id=candidate.facility_id,
                    equipment_id=candidate.equipment_id,
                    maintenance_record_id=candidate.maintenance_record_id,
                    production_loss_id=candidate.production_loss_id,
                    threshold_value=candidate.threshold_value,
                    current_value=candidate.current_value,
                    unit=candidate.unit,
                    dedup_key=candidate.dedup_key,
                    occurrence_count=1,
                    triggered_at=now,
                    last_detected_at=now,
                )
                db.add(alert)
                db.flush()
                db.add(
                    AlertStatusHistory(alert_id=alert.id, from_state=None, to_state="new", changed_at=now)
                )
                created += 1
                by_category[category]["created"] += 1

    # Auto-resolve: open, rule-generated alerts whose condition wasn't reaffirmed this run.
    # Manual alerts (source_module == "manual") are never touched here — their dedup_key never
    # matches a rule-generated key, so without this exclusion they'd be auto-resolved on the
    # very next run regardless of severity.
    auto_resolved = 0
    open_alerts = db.query(Alert).filter(Alert.state.in_(OPEN_STATES)).all()
    for alert in open_alerts:
        if alert.source_module == MANUAL_SOURCE:
            continue
        if alert.dedup_key in seen_keys:
            continue
        if alert.severity == "critical":
            continue
        prev_state = alert.state
        alert.state = "resolved"
        alert.resolved_at = now
        db.add(
            AlertStatusHistory(
                alert_id=alert.id,
                from_state=prev_state,
                to_state="resolved",
                note="Automatically resolved — condition no longer detected by the rule engine.",
                changed_at=now,
            )
        )
        auto_resolved += 1

    db.commit()

    return AlertRunResult(
        created=created,
        updated=updated,
        auto_resolved=auto_resolved,
        by_category=by_category,
        disclaimer_text=ALERT_DISCLAIMER,
    )
