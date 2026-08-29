"""Evidence-based AI Insights engine — analyzes already-recorded OG-PIOS data and produces
structured, source-cited insights. Mirrors `alert_rules.py`'s shape (DB-using generators + a
dedup/reaffirm orchestrator), and deliberately **reuses `alert_rules.py`'s private
`_generate_*_alerts` functions directly** (never the public `run_alert_rules()` orchestrator) as
the primary evidence source for insight types that check the same underlying condition an alert
already does — this keeps `run_insight_engine()` free of any side effect on the `alerts` table,
so the two engines stay independently runnable.

Every insight distinguishes OBSERVED FACT / CALCULATED METRIC / CORRELATION / POSSIBLE
CONTRIBUTOR at the data level (`AIInsightEvidence.evidence_type`), never only in prose.
Confidence is derived transparently from how many *independent evidence categories* support an
insight (`insight_calculations.derive_confidence_level`) — never a fabricated statistical score.
This module is 100% deterministic: it never calls an AI provider (see
`services/ai_providers/`, invoked only by the router's `/interpret`/`/assistant` endpoints).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.ai import AIInsightEvidence, AIRecommendation
from app.models.economics import ProductionLoss
from app.models.equipment import DowntimeEvent, Equipment, MaintenanceRecord
from app.models.field import Facility, Field, Well
from app.models.production import ProductionRecord
from app.routers.cost_revenue import (
    MAINTENANCE_COST_CURRENCY,
    _compute_scope_totals,
    _latest_period,
    _load_price_series,
    _operating_cost_query,
    _per_unit_by_currency,
    _split_operating_costs,
)
from app.routers.equipment import _resolve_scope
from app.services.alert_rules import (
    AlertCandidate,
    _generate_economics_alerts,
    _generate_equipment_alerts,
    _generate_maintenance_alerts,
    _generate_production_alerts,
    _generate_production_loss_alerts,
)
from app.services.insight_calculations import classify_trend, derive_confidence_level, to_aware_utc
from app.services.system_settings import (
    get_alert_maintenance_repeated_events_count,
    get_alert_maintenance_repeated_events_window_days,
    get_boe_gas_factor,
    get_insight_cross_domain_lookback_days,
    get_insight_high_maintenance_cost_vs_production_threshold_usd,
    get_insight_maintenance_frequency_increase_multiplier,
    get_insight_production_increase_pct,
    get_insight_trend_window_months,
    get_insight_well_comparison_ratio_threshold,
)

INSIGHT_DISCLAIMER = (
    "AI-generated estimate requiring engineering review; not a guaranteed conclusion. This is a "
    "rule-based, evidence-cited observation of recorded data — not a prediction, and not a "
    "substitute for qualified engineering or operational judgment."
)

OPEN_STATUSES = ("new", "reviewed")

# Fixed multipliers mirroring cost_revenue.py's own embedded /cost-revenue/alerts thresholds
# exactly (1.25x month-over-month, 1.5x company average) — these two insight types deliberately
# reuse that endpoint's framing rather than alert_rules.py's differently-shaped economics rules,
# so they intentionally match its hard-coded values rather than introducing new configurable
# settings for logic that's already a documented, working precedent elsewhere.
RISING_COST_MOM_MULTIPLIER = 1.25
HIGH_COST_PER_BBL_VS_AVG_MULTIPLIER = 1.5


@dataclass
class EvidenceCandidate:
    evidence_type: str  # observed_fact / calculated_metric / correlation / possible_contributor
    description: str
    source_type: str | None = None
    source_id: int | None = None
    source_label: str | None = None
    value: float | None = None
    unit: str | None = None


@dataclass
class InsightCandidate:
    category: str
    insight_type: str
    severity: str
    title: str
    summary: str
    dedup_key: str
    evidence: list[EvidenceCandidate] = field(default_factory=list)
    confidence_level: str = "low"
    well_id: int | None = None
    field_id: int | None = None
    facility_id: int | None = None
    equipment_id: int | None = None
    maintenance_record_id: int | None = None
    production_loss_id: int | None = None
    alert_id: int | None = None
    recommended_investigation: str | None = None
    estimated_production_impact_value: float | None = None
    estimated_production_impact_unit: str | None = None
    estimated_production_impact_note: str | None = None
    estimated_financial_impact_value: float | None = None
    estimated_financial_impact_currency: str | None = None
    estimated_financial_impact_note: str | None = None


@dataclass
class InsightRunResult:
    created: int
    updated: int
    by_category: dict[str, dict[str, int]]
    disclaimer_text: str


def _dedup_key(insight_type: str, scope_type: str, scope_id: int | str) -> str:
    return f"{insight_type}:{scope_type}:{scope_id}"


def _finalize(evidence: list[EvidenceCandidate], candidate_kwargs: dict) -> InsightCandidate:
    confidence = derive_confidence_level(len({e.evidence_type for e in evidence}))
    return InsightCandidate(evidence=evidence, confidence_level=confidence, **candidate_kwargs)


def _alert_evidence(candidate: AlertCandidate, source_type: str) -> list[EvidenceCandidate]:
    """Standard 2-item evidence baseline built from an AlertCandidate's own fields — an
    observed_fact (the underlying condition, in its own words) plus a calculated_metric (the
    figure that crossed a threshold, if any). Insight types that reuse an alert candidate
    directly start from this; the cross-domain generator adds further evidence on top.

    `source_id` must be the ID matching the *given* `source_type` — a candidate commonly has
    several FKs set at once (a well-linked equipment's alert carries both `well_id` and
    `equipment_id`), so picking "whichever FK happens to be set first" would silently attach the
    wrong record's ID to a `source_type="production_loss"` (or any other) evidence row. None of
    those FKs being set for the requested type is a legitimate case (source_id stays None), not
    an error to guess around.
    """
    source_id_by_type = {
        "well": candidate.well_id,
        "equipment": candidate.equipment_id,
        "maintenance_record": candidate.maintenance_record_id,
        "production_loss": candidate.production_loss_id,
    }
    source_id = source_id_by_type.get(source_type)
    evidence = [
        EvidenceCandidate(
            evidence_type="observed_fact",
            description=candidate.description,
            source_type=source_type,
            source_id=source_id,
            source_label=candidate.title,
        )
    ]
    if candidate.current_value is not None:
        evidence.append(
            EvidenceCandidate(
                evidence_type="calculated_metric",
                description=f"Current value: {candidate.current_value} {candidate.unit or ''}".strip(),
                source_type="computed",
                source_label=candidate.title,
                value=candidate.current_value,
                unit=candidate.unit,
            )
        )
    return evidence


def _scope_for_dedup(candidate: AlertCandidate) -> tuple[str, int | str]:
    if candidate.well_id:
        return "well", candidate.well_id
    if candidate.equipment_id:
        return "equipment", candidate.equipment_id
    if candidate.maintenance_record_id:
        return "work_order", candidate.maintenance_record_id
    if candidate.production_loss_id:
        return "loss_event", candidate.production_loss_id
    if candidate.field_id:
        return "field", candidate.field_id
    return "unknown", 0


def _candidate_to_insight(candidate: AlertCandidate, insight_type: str, category: str, source_type: str) -> InsightCandidate:
    evidence = _alert_evidence(candidate, source_type)
    scope_type, scope_id = _scope_for_dedup(candidate)
    return _finalize(
        evidence,
        dict(
            category=category,
            insight_type=insight_type,
            severity=candidate.severity,
            title=candidate.title,
            summary=candidate.description,
            well_id=candidate.well_id,
            field_id=candidate.field_id,
            facility_id=candidate.facility_id,
            equipment_id=candidate.equipment_id,
            maintenance_record_id=candidate.maintenance_record_id,
            production_loss_id=candidate.production_loss_id,
            recommended_investigation=candidate.recommended_action,
            dedup_key=_dedup_key(insight_type, scope_type, scope_id),
        ),
    )


def _downtime_hours(event: DowntimeEvent, now: datetime) -> float:
    start = to_aware_utc(event.start_time)
    end = to_aware_utc(event.end_time) if event.end_time is not None else now
    end = min(end, now)
    return max((end - start).total_seconds() / 3600, 0.0)


# ----- Production -----


def _monthly_totals_by_well(
    db: Session, well_ids: list[int], months: int, reference_date: date
) -> dict[int, list[float]]:
    """Average daily oil rate per calendar month, oldest first, per well, for the trailing
    `months` months ending at reference_date's month — batched across every well in `well_ids`
    as one query instead of one query per well (this function replaced a per-well
    `_monthly_well_totals(db, well_id, ...)` called in a loop)."""
    if not well_ids:
        return {}
    window_start = reference_date - timedelta(days=months * 31)
    records = (
        db.query(ProductionRecord)
        .filter(
            ProductionRecord.well_id.in_(well_ids),
            ProductionRecord.record_date >= window_start,
            ProductionRecord.record_date <= reference_date,
        )
        .all()
    )
    buckets_by_well: dict[int, dict[tuple[int, int], list[float]]] = defaultdict(dict)
    for r in records:
        key = (r.record_date.year, r.record_date.month)
        buckets_by_well[r.well_id].setdefault(key, []).append(r.oil_bopd)
    return {
        well_id: [sum(buckets[k]) / len(buckets[k]) for k in sorted(buckets.keys())]
        for well_id, buckets in buckets_by_well.items()
    }


def _generate_production_insights(db: Session, alert_candidates: list[AlertCandidate]) -> list[InsightCandidate]:
    candidates: list[InsightCandidate] = []

    for c in alert_candidates:
        if c.alert_type == "production_decline":
            candidates.append(_candidate_to_insight(c, "production_decline", "production", "well"))
        elif c.alert_type == "production_below_target":
            candidates.append(_candidate_to_insight(c, "production_below_target", "production", "well"))
        elif c.alert_type == "unusual_production_change":
            candidates.append(_candidate_to_insight(c, "production_anomaly", "production", "well"))

    reference_date = db.query(ProductionRecord.record_date).order_by(ProductionRecord.record_date.desc()).first()
    reference_date = reference_date[0] if reference_date else None
    if reference_date is None:
        return candidates

    increase_pct = get_insight_production_increase_pct(db)
    trend_window_months = get_insight_trend_window_months(db)
    ratio_threshold = get_insight_well_comparison_ratio_threshold(db)

    active_wells = db.query(Well).filter(Well.status == "active").all()
    active_well_ids = [w.id for w in active_wells]

    # Batched once across all active wells — replaces what was previously one query per well
    # per lookup inside the loop below.
    records_30_by_well: dict[int, list[ProductionRecord]] = defaultdict(list)
    window_30_start = reference_date - timedelta(days=29)
    for r in (
        db.query(ProductionRecord)
        .filter(
            ProductionRecord.well_id.in_(active_well_ids),
            ProductionRecord.record_date >= window_30_start,
            ProductionRecord.record_date <= reference_date,
        )
        .all()
    ):
        records_30_by_well[r.well_id].append(r)
    monthly_trend_by_well = _monthly_totals_by_well(db, active_well_ids, trend_window_months, reference_date)
    monthly_1_by_well = _monthly_totals_by_well(db, active_well_ids, 1, reference_date)

    for well in active_wells:
        records_30 = records_30_by_well.get(well.id, [])
        if len(records_30) >= 14:
            avg_30 = sum(r.oil_bopd for r in records_30) / len(records_30)
            window_7_start = reference_date - timedelta(days=6)
            records_7 = [r for r in records_30 if r.record_date >= window_7_start]
            if records_7 and avg_30 > 0:
                avg_7 = sum(r.oil_bopd for r in records_7) / len(records_7)
                change = (avg_7 - avg_30) / avg_30 * 100
                if change > increase_pct:
                    evidence = [
                        EvidenceCandidate(
                            "observed_fact",
                            f"{well.well_id}'s trailing 30-day average oil production is {avg_30:.1f} BOPD.",
                            "computed", None, well.well_id, round(avg_30, 1), "BOPD",
                        ),
                        EvidenceCandidate(
                            "calculated_metric",
                            f"{well.well_id}'s trailing 7-day average is {avg_7:.1f} BOPD, up {change:.1f}%.",
                            "computed", None, well.well_id, round(change, 1), "%",
                        ),
                    ]
                    candidates.append(
                        _finalize(
                            evidence,
                            dict(
                                category="production", insight_type="production_increase", severity="informational",
                                title=f"{well.well_id} — Production Increase", summary=evidence[1].description,
                                well_id=well.id,
                                recommended_investigation="Confirm whether this reflects a planned operating change or a sustained improvement worth understanding.",
                                dedup_key=_dedup_key("production_increase", "well", well.id),
                            ),
                        )
                    )

        monthly = monthly_trend_by_well.get(well.id, [])
        if len(monthly) >= 3:
            direction = classify_trend(monthly)
            if direction in ("rising", "declining"):
                series_text = ", ".join(f"{v:.1f}" for v in monthly)
                evidence = [
                    EvidenceCandidate(
                        "observed_fact",
                        f"{well.well_id}'s monthly average oil rate over the last {len(monthly)} months: {series_text} BOPD.",
                        "computed", None, well.well_id,
                    ),
                    EvidenceCandidate(
                        "calculated_metric",
                        f"{well.well_id}'s production trend over this window is {direction}.",
                        "computed", None, well.well_id,
                    ),
                ]
                candidates.append(
                    _finalize(
                        evidence,
                        dict(
                            category="production", insight_type="production_trend", severity="informational",
                            title=f"{well.well_id} — Production Trend: {direction.capitalize()}",
                            summary=evidence[1].description,
                            well_id=well.id,
                            recommended_investigation="Review this well's longer-term production history for context.",
                            dedup_key=_dedup_key("production_trend", "well", well.id),
                        ),
                    )
                )

    for f in db.query(Field).all():
        wells = (
            db.query(Well)
            .join(Facility, Well.facility_id == Facility.id)
            .filter(Facility.field_id == f.id, Well.status == "active")
            .all()
        )
        latest_rates: dict[int, float] = {}
        for well in wells:
            monthly = monthly_1_by_well.get(well.id, [])
            if monthly:
                latest_rates[well.id] = monthly[-1]
        if len(latest_rates) < 3:
            continue
        rates = sorted(latest_rates.values())
        mid = len(rates) // 2
        median = rates[mid] if len(rates) % 2 == 1 else (rates[mid - 1] + rates[mid]) / 2
        if median <= 0:
            continue
        underperformers = {wid: rate for wid, rate in latest_rates.items() if rate < median * ratio_threshold}
        if not underperformers:
            continue
        wells_by_id = {w.id: w for w in wells}
        evidence = [
            EvidenceCandidate(
                "observed_fact", f"{f.name}'s median well oil rate this period is {median:.1f} BOPD.",
                "computed", None, f.name, round(median, 1), "BOPD",
            )
        ]
        for wid, rate in underperformers.items():
            well = wells_by_id[wid]
            evidence.append(
                EvidenceCandidate(
                    "calculated_metric",
                    f"{well.well_id} is producing {rate:.1f} BOPD, {rate / median * 100:.0f}% of the field median.",
                    "well", wid, well.well_id, round(rate, 1), "BOPD",
                )
            )
        names = ", ".join(wells_by_id[wid].well_id for wid in underperformers)
        candidates.append(
            _finalize(
                evidence,
                dict(
                    category="production", insight_type="well_performance_comparison", severity="low",
                    title=f"{f.name} — Well Performance Comparison",
                    summary=f"{len(underperformers)} well(s) in {f.name} are producing below {int(ratio_threshold * 100)}% of the field median: {names}.",
                    field_id=f.id,
                    recommended_investigation="Review the underperforming wells for artificial-lift issues, reservoir decline, or mechanical problems.",
                    dedup_key=_dedup_key("well_performance_comparison", "field", f.id),
                ),
            )
        )

        # Same underperformer set, reframed as an actionable optimization opportunity (Current vs.
        # Potential vs. estimated Gain) rather than a plain observation — the field median stands in
        # for "potential" since there's no separate capacity/type-curve model in this codebase.
        for wid, rate in underperformers.items():
            well = wells_by_id[wid]
            potential_gain = median - rate
            candidates.append(
                _finalize(
                    [
                        EvidenceCandidate(
                            "observed_fact", f"{well.well_id} is currently producing {rate:.1f} BOPD.",
                            "well", wid, well.well_id, round(rate, 1), "BOPD",
                        ),
                        EvidenceCandidate(
                            "calculated_metric",
                            f"{f.name}'s field median well oil rate is {median:.1f} BOPD, used here as the potential "
                            f"benchmark for {well.well_id}.",
                            "computed", None, f.name, round(median, 1), "BOPD",
                        ),
                        EvidenceCandidate(
                            "possible_contributor",
                            f"If {well.well_id} were brought to the field median rate, estimated additional production "
                            f"is {potential_gain:.1f} BOPD — requires engineering review to confirm achievability "
                            "(artificial-lift, choke, or reservoir constraints may limit this).",
                            "well", wid, well.well_id, round(potential_gain, 1), "BOPD",
                        ),
                    ],
                    dict(
                        category="optimization", insight_type="production_optimization_opportunity", severity="informational",
                        title=f"{well.well_id} — Potential Production Optimization",
                        summary=(
                            f"{well.well_id} is producing {rate:.1f} BOPD vs. a field median of {median:.1f} BOPD in "
                            f"{f.name} — an estimated {potential_gain:.1f} BOPD optimization opportunity."
                        ),
                        well_id=wid, field_id=f.id,
                        recommended_investigation="Investigate artificial-lift performance, choke setting, and reservoir conditions to assess whether this gap is recoverable.",
                        estimated_production_impact_value=round(potential_gain, 1),
                        estimated_production_impact_unit="BOPD",
                        estimated_production_impact_note="Estimated gain if brought to field median performance — not guaranteed achievable.",
                        dedup_key=_dedup_key("production_optimization_opportunity", "well", wid),
                    ),
                )
            )

    return candidates


# ----- Equipment -----


def _generate_equipment_insights(db: Session, alert_candidates: list[AlertCandidate]) -> list[InsightCandidate]:
    candidates: list[InsightCandidate] = []
    health_seen: set[int] = set()

    for c in alert_candidates:
        if c.alert_type in ("equipment_low_health", "equipment_critical_health", "equipment_failure"):
            if c.equipment_id in health_seen:
                continue
            health_seen.add(c.equipment_id)
            candidates.append(_candidate_to_insight(c, "equipment_health_deterioration", "equipment", "equipment"))
        elif c.alert_type == "abnormal_equipment_readings":
            candidates.append(_candidate_to_insight(c, "abnormal_equipment_readings", "equipment", "equipment"))

    repeated_window_days = get_alert_maintenance_repeated_events_window_days(db)
    repeated_count_threshold = get_alert_maintenance_repeated_events_count(db)
    window_start = date.today() - timedelta(days=repeated_window_days)
    records = (
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
    for r in records:
        counts[r.equipment_id] = counts.get(r.equipment_id, 0) + 1
    for equipment_id, count in counts.items():
        if count < repeated_count_threshold:
            continue
        equipment = db.get(Equipment, equipment_id)
        if equipment is None:
            continue
        field_id, _, facility_id, _, well_id, _ = _resolve_scope(equipment)
        evidence = [
            EvidenceCandidate(
                "observed_fact",
                f"{equipment.equipment_tag} has had {count} corrective/emergency maintenance events in the last {repeated_window_days} days.",
                "equipment", equipment.id, equipment.equipment_tag, count, "events",
            )
        ]
        if equipment.health_score is not None:
            evidence.append(
                EvidenceCandidate(
                    "calculated_metric",
                    f"{equipment.equipment_tag}'s current health score is {equipment.health_score:.1f}.",
                    "equipment", equipment.id, equipment.equipment_tag, equipment.health_score, "score",
                )
            )
        candidates.append(
            _finalize(
                evidence,
                dict(
                    category="equipment", insight_type="equipment_repeated_issues", severity="high",
                    title=f"{equipment.equipment_tag} — Repeated Equipment Issues", summary=evidence[0].description,
                    equipment_id=equipment.id, well_id=well_id, field_id=field_id, facility_id=facility_id,
                    recommended_investigation="Investigate for a recurring root cause across these events rather than treating each in isolation.",
                    dedup_key=_dedup_key("equipment_repeated_issues", "equipment", equipment.id),
                ),
            )
        )

    return candidates


# ----- Maintenance -----


def _generate_maintenance_insights(
    db: Session, maintenance_alert_candidates: list[AlertCandidate], economics_alert_candidates: list[AlertCandidate]
) -> list[InsightCandidate]:
    candidates: list[InsightCandidate] = []
    overdue_seen: set[tuple] = set()

    for c in maintenance_alert_candidates:
        if c.alert_type in ("maintenance_overdue", "critical_maintenance"):
            key = (c.equipment_id, c.maintenance_record_id)
            if key in overdue_seen:
                continue
            overdue_seen.add(key)
            source_type = "maintenance_record" if c.maintenance_record_id else "equipment"
            candidates.append(_candidate_to_insight(c, "maintenance_overdue", "maintenance", source_type))

    for c in economics_alert_candidates:
        if c.alert_type == "high_maintenance_cost":
            candidates.append(_candidate_to_insight(c, "high_maintenance_cost", "maintenance", "equipment"))

    frequency_multiplier = get_insight_maintenance_frequency_increase_multiplier(db)
    window_days = get_alert_maintenance_repeated_events_window_days(db)
    repeated_count_threshold = get_alert_maintenance_repeated_events_count(db)
    today = date.today()
    this_window_start = today - timedelta(days=window_days)
    prior_window_start = today - timedelta(days=window_days * 2)

    this_records = (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.start_date.isnot(None),
            MaintenanceRecord.start_date >= this_window_start,
            MaintenanceRecord.equipment_id.isnot(None),
        )
        .all()
    )
    prior_records = (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.start_date.isnot(None),
            MaintenanceRecord.start_date >= prior_window_start,
            MaintenanceRecord.start_date < this_window_start,
            MaintenanceRecord.equipment_id.isnot(None),
        )
        .all()
    )
    this_counts: dict[int, int] = {}
    for r in this_records:
        this_counts[r.equipment_id] = this_counts.get(r.equipment_id, 0) + 1
    prior_counts: dict[int, int] = {}
    for r in prior_records:
        prior_counts[r.equipment_id] = prior_counts.get(r.equipment_id, 0) + 1

    for equipment_id, this_count in this_counts.items():
        prior_count = prior_counts.get(equipment_id, 0)
        if prior_count > 0 and this_count >= 2 and this_count >= prior_count * frequency_multiplier:
            equipment = db.get(Equipment, equipment_id)
            if equipment is None:
                continue
            field_id, _, facility_id, _, well_id, _ = _resolve_scope(equipment)
            evidence = [
                EvidenceCandidate(
                    "observed_fact",
                    f"{equipment.equipment_tag} had {prior_count} maintenance event(s) in the prior {window_days}-day window.",
                    "equipment", equipment.id, equipment.equipment_tag, prior_count, "events",
                ),
                EvidenceCandidate(
                    "calculated_metric",
                    f"{equipment.equipment_tag} has had {this_count} maintenance event(s) in the last {window_days} days.",
                    "equipment", equipment.id, equipment.equipment_tag, this_count, "events",
                ),
            ]
            candidates.append(
                _finalize(
                    evidence,
                    dict(
                        category="maintenance", insight_type="increasing_maintenance_frequency", severity="medium",
                        title=f"{equipment.equipment_tag} — Increasing Maintenance Frequency", summary=evidence[1].description,
                        equipment_id=equipment.id, well_id=well_id, field_id=field_id, facility_id=facility_id,
                        recommended_investigation="Review recent maintenance records for a developing pattern rather than isolated events.",
                        dedup_key=_dedup_key("increasing_maintenance_frequency", "equipment", equipment.id),
                    ),
                )
            )

    corrective_window_start = today - timedelta(days=window_days)
    corrective_records = (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.maintenance_type == "corrective",
            MaintenanceRecord.start_date.isnot(None),
            MaintenanceRecord.start_date >= corrective_window_start,
            MaintenanceRecord.equipment_id.isnot(None),
        )
        .all()
    )
    corrective_counts: dict[int, int] = {}
    for r in corrective_records:
        corrective_counts[r.equipment_id] = corrective_counts.get(r.equipment_id, 0) + 1
    for equipment_id, count in corrective_counts.items():
        if count < repeated_count_threshold:
            continue
        equipment = db.get(Equipment, equipment_id)
        if equipment is None:
            continue
        field_id, _, facility_id, _, well_id, _ = _resolve_scope(equipment)
        evidence = [
            EvidenceCandidate(
                "observed_fact",
                f"{equipment.equipment_tag} has had {count} corrective maintenance events in the last {window_days} days.",
                "equipment", equipment.id, equipment.equipment_tag, count, "events",
            )
        ]
        candidates.append(
            _finalize(
                evidence,
                dict(
                    category="maintenance", insight_type="recurring_corrective_maintenance", severity="high",
                    title=f"{equipment.equipment_tag} — Recurring Corrective Maintenance", summary=evidence[0].description,
                    equipment_id=equipment.id, well_id=well_id, field_id=field_id, facility_id=facility_id,
                    recommended_investigation="Consider whether preventive maintenance intervals should be adjusted for this equipment.",
                    dedup_key=_dedup_key("recurring_corrective_maintenance", "equipment", equipment.id),
                ),
            )
        )

    return candidates


# ----- Production Loss -----


def _generate_production_loss_insights(db: Session, alert_candidates: list[AlertCandidate]) -> list[InsightCandidate]:
    candidates: list[InsightCandidate] = []
    for c in alert_candidates:
        if c.alert_type == "high_production_loss":
            candidates.append(_candidate_to_insight(c, "high_production_loss", "production_loss", "production_loss"))
        elif c.alert_type == "repeated_production_loss_events":
            candidates.append(_candidate_to_insight(c, "repeated_production_loss_events", "production_loss", "well"))
        elif c.alert_type == "high_downtime":
            candidates.append(_candidate_to_insight(c, "high_downtime", "production_loss", "production_loss"))
        elif c.alert_type == "high_estimated_lost_revenue":
            candidate = _candidate_to_insight(c, "high_lost_revenue", "production_loss", "production_loss")
            candidate.estimated_financial_impact_value = c.current_value
            candidate.estimated_financial_impact_currency = "USD"
            candidate.estimated_financial_impact_note = c.description
            candidates.append(candidate)
    return candidates


# ----- Economics -----


def _generate_economics_insights(db: Session, economics_alert_candidates: list[AlertCandidate]) -> list[InsightCandidate]:
    candidates: list[InsightCandidate] = []

    for c in economics_alert_candidates:
        if c.alert_type == "declining_operating_margin":
            candidates.append(_candidate_to_insight(c, "declining_operating_margin", "economics", "computed"))
        elif c.alert_type == "high_estimated_financial_impact":
            candidate = _candidate_to_insight(c, "high_downtime_financial_impact", "economics", "computed")
            candidate.estimated_financial_impact_value = c.current_value
            candidate.estimated_financial_impact_currency = "USD"
            candidate.estimated_financial_impact_note = c.description
            candidates.append(candidate)

    this_start, this_end = _latest_period(db)
    prev_end = this_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    boe_gas_factor = get_boe_gas_factor(db)
    price_series = _load_price_series(db)
    fields = db.query(Field).all()

    field_cost_per_bbl: dict[int, tuple[dict[str, float], str]] = {}

    for f in fields:
        this_costs = _operating_cost_query(db, this_start, this_end, field_id=f.id).all()
        prev_costs = _operating_cost_query(db, prev_start, prev_end, field_id=f.id).all()
        this_dict, _, _ = _split_operating_costs(this_costs)
        prev_dict, _, _ = _split_operating_costs(prev_costs)
        for currency, this_amount in this_dict.items():
            prev_amount = prev_dict.get(currency)
            if prev_amount and this_amount > prev_amount * RISING_COST_MOM_MULTIPLIER:
                pct = (this_amount - prev_amount) / prev_amount * 100
                evidence = [
                    EvidenceCandidate(
                        "observed_fact", f"{f.name}'s operating cost was {currency} {prev_amount:,.0f} last month.",
                        "computed", None, f.name, prev_amount, currency,
                    ),
                    EvidenceCandidate(
                        "calculated_metric",
                        f"{f.name}'s operating cost is {currency} {this_amount:,.0f} this month, up {pct:.1f}%.",
                        "computed", None, f.name, round(pct, 1), "%",
                    ),
                ]
                candidates.append(
                    _finalize(
                        evidence,
                        dict(
                            category="economics", insight_type="rising_operating_cost", severity="medium",
                            title=f"{f.name} — Rising Operating Cost", summary=evidence[1].description,
                            field_id=f.id,
                            recommended_investigation="Review cost entries for this field to identify what's driving the increase.",
                            dedup_key=_dedup_key("rising_operating_cost", "field_currency", f"{f.id}:{currency}"),
                        ),
                    )
                )

        totals = _compute_scope_totals(db, this_start, this_end, price_series, boe_gas_factor, field_id=f.id)
        field_cost_per_bbl[f.id] = (_per_unit_by_currency(totals["operating_dict"], totals["oil_total"]), f.name)

    for currency in {c for d, _ in field_cost_per_bbl.values() for c in d}:
        values = [d[currency] for d, _ in field_cost_per_bbl.values() if currency in d]
        if not values:
            continue
        avg = sum(values) / len(values)
        for f_id, (d, f_name) in field_cost_per_bbl.items():
            if currency in d and avg > 0 and d[currency] > avg * HIGH_COST_PER_BBL_VS_AVG_MULTIPLIER:
                evidence = [
                    EvidenceCandidate(
                        "calculated_metric", f"{f_name}'s cost per barrel is {currency} {d[currency]:,.2f}.",
                        "computed", None, f_name, d[currency], f"{currency}/bbl",
                    ),
                    EvidenceCandidate(
                        "correlation", f"Company-wide average cost per barrel is {currency} {avg:,.2f}.",
                        "computed", None, "Company average", round(avg, 2), f"{currency}/bbl",
                    ),
                ]
                candidates.append(
                    _finalize(
                        evidence,
                        dict(
                            category="economics", insight_type="high_cost_per_barrel", severity="medium",
                            title=f"{f_name} — High Cost per Barrel", summary=evidence[0].description,
                            field_id=f_id,
                            recommended_investigation="Compare this field's cost structure against lower-cost fields to identify savings opportunities.",
                            dedup_key=_dedup_key("high_cost_per_barrel", "field_currency", f"{f_id}:{currency}"),
                        ),
                    )
                )

    threshold_per_bbl = get_insight_high_maintenance_cost_vs_production_threshold_usd(db)
    for f in fields:
        totals = _compute_scope_totals(db, this_start, this_end, price_series, boe_gas_factor, field_id=f.id)
        if totals["oil_total"] > 0 and totals["maintenance_total"] > 0:
            ratio = totals["maintenance_total"] / totals["oil_total"]
            if ratio > threshold_per_bbl:
                evidence = [
                    EvidenceCandidate(
                        "observed_fact", f"{f.name} produced {totals['oil_total']:.1f} bbl of oil this period.",
                        "computed", None, f.name, round(totals["oil_total"], 1), "bbl",
                    ),
                    EvidenceCandidate(
                        "calculated_metric",
                        f"{f.name}'s maintenance cost is {MAINTENANCE_COST_CURRENCY} {totals['maintenance_total']:,.0f}, or {MAINTENANCE_COST_CURRENCY} {ratio:.2f} per barrel produced.",
                        "computed", None, f.name, round(ratio, 2), f"{MAINTENANCE_COST_CURRENCY}/bbl",
                    ),
                ]
                candidates.append(
                    _finalize(
                        evidence,
                        dict(
                            category="economics", insight_type="high_maintenance_cost_vs_production", severity="medium",
                            title=f"{f.name} — High Maintenance Cost Relative to Production", summary=evidence[1].description,
                            field_id=f.id,
                            recommended_investigation="Review whether maintenance spend is proportional to this field's production output.",
                            dedup_key=_dedup_key("high_maintenance_cost_vs_production", "field", f.id),
                        ),
                    )
                )

    return candidates


# ----- Cross-Domain -----


def _generate_cross_domain_insights(
    db: Session, production_candidates: list[AlertCandidate], equipment_candidates: list[AlertCandidate]
) -> list[InsightCandidate]:
    """One generator, two tiered outputs (Decision 8) — never a bespoke 3rd equipment detector.
    AlertCandidate lists alone can't supply "recent maintenance/downtime happened, nothing
    alert-worthy about it" as evidence (alert generators only emit alert-worthy candidates), so
    this generator runs its own supplementary queries scoped to the co-occurring well/equipment.
    """
    candidates: list[InsightCandidate] = []
    lookback_days = get_insight_cross_domain_lookback_days(db)

    decline_by_well = {c.well_id: c for c in production_candidates if c.alert_type == "production_decline" and c.well_id}
    health_by_equipment = {
        c.equipment_id: c
        for c in equipment_candidates
        if c.alert_type in ("equipment_low_health", "equipment_critical_health", "equipment_failure") and c.equipment_id
    }
    if not decline_by_well or not health_by_equipment:
        return candidates

    now = datetime.now(timezone.utc)
    window_start_date = date.today() - timedelta(days=lookback_days)
    window_start_dt = datetime.combine(window_start_date, datetime.min.time(), tzinfo=timezone.utc)

    equipment_rows = db.query(Equipment).filter(Equipment.id.in_(health_by_equipment.keys())).all()
    for equipment in equipment_rows:
        if equipment.well_id is None or equipment.well_id not in decline_by_well:
            continue
        decline_candidate = decline_by_well[equipment.well_id]
        health_candidate = health_by_equipment[equipment.id]
        well = db.get(Well, equipment.well_id)
        if well is None:
            continue

        evidence = [
            EvidenceCandidate(
                "observed_fact", decline_candidate.description, "well", equipment.well_id, well.well_id,
                decline_candidate.current_value, decline_candidate.unit,
            ),
            # calculated_metric, not observed_fact — the health score is itself a computed
            # value (equipment_health.py's compute_health()), not a directly recorded reading.
            # Distinguishing the two evidence types here also means 2 independent sources
            # (production records + equipment scoring) genuinely count as 2 evidence
            # categories for the transparent confidence rule, not 1.
            EvidenceCandidate(
                "calculated_metric", health_candidate.description, "equipment", equipment.id, equipment.equipment_tag,
                equipment.health_score, "score",
            ),
        ]

        recent_maintenance = (
            db.query(MaintenanceRecord)
            .filter(
                MaintenanceRecord.equipment_id == equipment.id,
                MaintenanceRecord.start_date.isnot(None),
                MaintenanceRecord.start_date >= window_start_date,
            )
            .all()
        )
        recent_downtime = (
            db.query(DowntimeEvent)
            .filter(
                or_(DowntimeEvent.equipment_id == equipment.id, DowntimeEvent.well_id == equipment.well_id),
                DowntimeEvent.start_time >= window_start_dt,
            )
            .all()
        )

        if recent_maintenance:
            evidence.append(
                EvidenceCandidate(
                    "possible_contributor",
                    f"{len(recent_maintenance)} maintenance event(s) recorded for {equipment.equipment_tag} in the last {lookback_days} days.",
                    "maintenance_record", recent_maintenance[0].id, recent_maintenance[0].work_order_number,
                    len(recent_maintenance), "events",
                )
            )
        if recent_downtime:
            total_downtime_hours = sum(_downtime_hours(e, now) for e in recent_downtime)
            evidence.append(
                EvidenceCandidate(
                    "possible_contributor",
                    f"{total_downtime_hours:.1f} hours of downtime recorded for {equipment.equipment_tag} in the last {lookback_days} days.",
                    "computed", None, f"{equipment.equipment_tag} downtime", round(total_downtime_hours, 1), "hours",
                )
            )

        if recent_maintenance and recent_downtime:
            insight_type = "equipment_production_maintenance_downtime_correlation"
            severity = "high"
            title = f"{well.well_id} — Possible Equipment-Related Production Issue"
            summary = (
                f"{well.well_id}'s production has declined while {equipment.equipment_tag}'s health score has "
                "deteriorated, with recent maintenance activity and downtime also recorded for this equipment. "
                "This reflects a correlation across independent signals, not a confirmed cause — engineering "
                "review is recommended."
            )
        else:
            insight_type = "equipment_linked_to_production_decline"
            severity = "medium"
            title = f"{well.well_id} — Equipment May Be Linked to Production Decline"
            summary = (
                f"{well.well_id}'s production has declined while {equipment.equipment_tag}'s health score has "
                "also deteriorated. This is a correlation, not a confirmed cause."
            )

        candidates.append(
            _finalize(
                evidence,
                dict(
                    category="cross_domain", insight_type=insight_type, severity=severity, title=title, summary=summary,
                    well_id=equipment.well_id, equipment_id=equipment.id,
                    field_id=decline_candidate.field_id, facility_id=decline_candidate.facility_id,
                    recommended_investigation=(
                        "Review this equipment's operating history, recent maintenance records, and downtime log "
                        "alongside the well's production trend."
                    ),
                    dedup_key=_dedup_key(insight_type, "well_equipment", f"{equipment.well_id}:{equipment.id}"),
                ),
            )
        )

    return candidates


# ----- Orchestrator -----


def run_insight_engine(db: Session) -> InsightRunResult:
    now = datetime.now(timezone.utc)

    production_alert_candidates = _generate_production_alerts(db)
    equipment_alert_candidates = _generate_equipment_alerts(db)
    maintenance_alert_candidates = _generate_maintenance_alerts(db)
    production_loss_alert_candidates = _generate_production_loss_alerts(db)
    economics_alert_candidates = _generate_economics_alerts(db)

    generated: list[tuple[str, list[InsightCandidate]]] = [
        ("production", _generate_production_insights(db, production_alert_candidates)),
        ("equipment", _generate_equipment_insights(db, equipment_alert_candidates)),
        (
            "maintenance",
            _generate_maintenance_insights(db, maintenance_alert_candidates, economics_alert_candidates),
        ),
        ("production_loss", _generate_production_loss_insights(db, production_loss_alert_candidates)),
        ("economics", _generate_economics_insights(db, economics_alert_candidates)),
        (
            "cross_domain",
            _generate_cross_domain_insights(db, production_alert_candidates, equipment_alert_candidates),
        ),
    ]

    by_category: dict[str, dict[str, int]] = {category: {"created": 0, "updated": 0} for category, _ in generated}
    created = 0
    updated = 0

    for category, candidates in generated:
        for candidate in candidates:
            existing = (
                db.query(AIRecommendation)
                .filter(AIRecommendation.dedup_key == candidate.dedup_key, AIRecommendation.status.in_(OPEN_STATUSES))
                .first()
            )
            if existing is not None:
                existing.severity = candidate.severity
                existing.title = candidate.title
                existing.summary = candidate.summary
                existing.confidence_level = candidate.confidence_level
                existing.recommended_investigation = candidate.recommended_investigation
                existing.estimated_production_impact_value = candidate.estimated_production_impact_value
                existing.estimated_production_impact_unit = candidate.estimated_production_impact_unit
                existing.estimated_production_impact_note = candidate.estimated_production_impact_note
                existing.estimated_financial_impact_value = candidate.estimated_financial_impact_value
                existing.estimated_financial_impact_currency = candidate.estimated_financial_impact_currency
                existing.estimated_financial_impact_note = candidate.estimated_financial_impact_note
                existing.occurrence_count += 1
                existing.last_confirmed_at = now
                for row in list(existing.evidence):
                    db.delete(row)
                db.flush()
                for e in candidate.evidence:
                    db.add(
                        AIInsightEvidence(
                            insight_id=existing.id, evidence_type=e.evidence_type, description=e.description,
                            source_type=e.source_type, source_id=e.source_id, source_label=e.source_label,
                            value=e.value, unit=e.unit,
                        )
                    )
                updated += 1
                by_category[category]["updated"] += 1
            else:
                insight = AIRecommendation(
                    insight_type=candidate.insight_type,
                    category=candidate.category,
                    severity=candidate.severity,
                    status="new",
                    generated_by="rule_based",
                    title=candidate.title,
                    summary=candidate.summary,
                    recommended_investigation=candidate.recommended_investigation,
                    confidence_level=candidate.confidence_level,
                    estimated_production_impact_value=candidate.estimated_production_impact_value,
                    estimated_production_impact_unit=candidate.estimated_production_impact_unit,
                    estimated_production_impact_note=candidate.estimated_production_impact_note,
                    estimated_financial_impact_value=candidate.estimated_financial_impact_value,
                    estimated_financial_impact_currency=candidate.estimated_financial_impact_currency,
                    estimated_financial_impact_note=candidate.estimated_financial_impact_note,
                    well_id=candidate.well_id,
                    field_id=candidate.field_id,
                    facility_id=candidate.facility_id,
                    equipment_id=candidate.equipment_id,
                    maintenance_record_id=candidate.maintenance_record_id,
                    production_loss_id=candidate.production_loss_id,
                    alert_id=candidate.alert_id,
                    dedup_key=candidate.dedup_key,
                    occurrence_count=1,
                    generated_at=now,
                    last_confirmed_at=now,
                    disclaimer_text=INSIGHT_DISCLAIMER,
                )
                db.add(insight)
                db.flush()
                for e in candidate.evidence:
                    db.add(
                        AIInsightEvidence(
                            insight_id=insight.id, evidence_type=e.evidence_type, description=e.description,
                            source_type=e.source_type, source_id=e.source_id, source_label=e.source_label,
                            value=e.value, unit=e.unit,
                        )
                    )
                created += 1
                by_category[category]["created"] += 1

    db.commit()

    return InsightRunResult(created=created, updated=updated, by_category=by_category, disclaimer_text=INSIGHT_DISCLAIMER)
