"""Cross-module report orchestration for the Reports module.

Unlike `whatif_calculations.py` (fully pure, no DB access), this module is DB-using by design —
its entire purpose is aggregating data other modules already compute, mirroring
`insight_engine.py`/`alert_rules.py`'s own DB-using-but-still-a-service shape. Every figure here
comes from calling an existing dashboard/list/calculation function directly — the same "call the
router function as a plain Python function" precedent `ai_insights.py`'s `get_daily_brief`/
`get_management_summary` already established (calling `get_production_kpis`, `get_equipment_
issues`, `get_maintenance_dashboard` directly) — never a re-derived formula. See docs/data-
model.md's Reports section for the full calculation-reuse map back to each source module.

Filter tiers: `get_production_kpis`/`get_production_trends`/`get_production_by_scope`/
`get_actual_vs_target` are natively scope-filterable. Equipment/Maintenance/Production-Loss/
Alerts/AI-Insights have no filterable *dashboard* — only their paginated `list_*` endpoints
accept field/facility/well/equipment/date/category/severity/type filters, so this module calls
those directly (generous `page_size`, aggregates `.items` in Python) rather than duplicating any
WHERE-clause logic a second time.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import User
from app.routers.ai_insights import list_insights
from app.routers.alerts import list_alerts
from app.routers.cost_revenue import _compute_scope_totals, _load_price_series
from app.routers.equipment import list_equipment
from app.routers.maintenance import get_maintenance_schedule, list_maintenance
from app.routers.production import (
    get_actual_vs_target,
    get_production_by_scope,
    get_production_kpis,
    get_production_trends,
)
from app.routers.production_loss import list_production_loss
from app.routers.what_if import _get_scenario_or_404, _results_json_to_schema
from app.services.system_settings import get_boe_gas_factor

REPORT_CALCULATION_VERSION = "1.0"

REPORT_DISCLAIMER = (
    "Aggregated from existing OG-PIOS production, equipment, maintenance, production-loss, cost/"
    "revenue, alert, AI insight, and what-if data. A decision-support summary for engineering/"
    "management review - not an audited or certified record. Estimated financial and production-"
    "loss figures are estimates, not audited accounting results, and no AI-generated content here "
    "should be treated as a confirmed root cause or an instruction to act automatically."
)

# Always included — this codebase has never run against a verified production dataset (no such
# mode/flag exists anywhere), so per the brief's own fallback rule this is never conditional.
SYNTHETIC_DATA_DISCLAIMER = (
    "Development environment: This report contains synthetic/demo operational data and must not "
    "be interpreted as actual field/company performance."
)

REPORT_TYPES: dict[str, dict] = {
    "daily_operations": {
        "label": "Daily Operations Report",
        "sections": ["production", "equipment", "maintenance", "production_loss", "alerts", "ai_insights"],
    },
    "weekly_production": {
        "label": "Weekly Production Report",
        "sections": ["production_trend", "production_by_scope", "actual_vs_target", "production_loss"],
    },
    "monthly_management": {
        "label": "Monthly Management Report",
        "sections": [
            "executive_summary", "production", "equipment", "maintenance",
            "production_loss", "economics", "alerts", "ai_insights",
        ],
    },
    "what_if_scenario": {
        "label": "What-If Scenario Report",
        "sections": ["scenario"],
    },
}


def default_sections(report_type: str) -> list[str]:
    return list(REPORT_TYPES[report_type]["sections"])


def _wants(sections: list[str] | None, key: str) -> bool:
    return not sections or key in sections


@dataclass
class ReportFilterValues:
    date_from: date | None = None
    date_to: date | None = None
    field_id: int | None = None
    facility_id: int | None = None
    well_id: int | None = None
    equipment_id: int | None = None
    commodity: str | None = None
    maintenance_type: str | None = None
    alert_severity: str | None = None
    production_loss_category: str | None = None
    scenario_id: int | None = None

    def as_dict(self) -> dict:
        """JSON-safe (dates as ISO strings) — this dict is embedded directly into `results`,
        which is stored in a JSON column, so it must never carry a raw `date` object."""
        result = {}
        for k, v in self.__dict__.items():
            if v is None:
                continue
            result[k] = v.isoformat() if isinstance(v, date) else v
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ReportFilterValues":
        known = {f: data.get(f) for f in cls.__dataclass_fields__ if f in data}
        return cls(**known)


def _traceability(source_module: str, methodology: str, *, record_count: int | None = None) -> dict:
    return {"source_module": source_module, "methodology": methodology, "record_count": record_count}


def _equipment_ids_for_scope(db: Session, user: User, filters: ReportFilterValues) -> set[int] | None:
    """None means "no scope restriction" (all equipment) — distinct from an empty set (scope
    restricts to zero equipment)."""
    if filters.equipment_id:
        return {filters.equipment_id}
    if not any([filters.field_id, filters.facility_id, filters.well_id]):
        return None
    result = list_equipment(
        field_id=filters.field_id, facility_id=filters.facility_id, well_id=filters.well_id,
        status_filter=None, page=1, page_size=500, db=db, current_user=user,
    )
    return {item.id for item in result.items}


# ----- Section builders — each returns a plain, JSON-safe dict embedding an already-typed
# upstream schema's own `.model_dump(mode="json")`, plus a "_traceability" block. -----


def _production_section(db: Session, user: User, filters: ReportFilterValues) -> dict:
    kpis = get_production_kpis(
        well_id=filters.well_id, field_id=filters.field_id, facility_id=filters.facility_id,
        date_from=filters.date_from, date_to=filters.date_to, db=db, current_user=user,
    )
    return {
        "kpis": kpis.model_dump(mode="json"),
        "_traceability": _traceability(
            "production.get_production_kpis",
            "Volume-weighted water-cut/GOR and BOE (configurable gas factor) computed from "
            "recorded ProductionRecord rows for the selected scope and date range.",
        ),
    }


def _equipment_section(db: Session, user: User, filters: ReportFilterValues) -> dict:
    result = list_equipment(
        field_id=filters.field_id, facility_id=filters.facility_id, well_id=filters.well_id,
        status_filter=None, page=1, page_size=500, sort="health_score", order="asc", db=db, current_user=user,
    )
    items = result.items
    band_counts: dict[str, int] = {}
    for item in items:
        band = item.health_band or "Unscored"
        band_counts[band] = band_counts.get(band, 0) + 1
    critical = [
        {"id": i.id, "equipment_tag": i.equipment_tag, "name": i.name, "status": i.status, "health_score": i.health_score}
        for i in items
        if i.status == "failed" or (i.health_score is not None and i.health_score < 50)
    ][:10]
    return {
        "total_equipment": len(items),
        "health_band_counts": band_counts,
        "critical_equipment": critical,
        "_traceability": _traceability(
            "equipment.list_equipment",
            "Health-band distribution and critical-equipment list computed from each item's "
            "already-scored health_score/health_band (see equipment_health.py) for the selected scope.",
            record_count=result.total,
        ),
    }


def _maintenance_section(db: Session, user: User, filters: ReportFilterValues) -> dict:
    records = list_maintenance(
        equipment_id=filters.equipment_id, well_id=filters.well_id, field_id=filters.field_id,
        facility_id=filters.facility_id, maintenance_type=filters.maintenance_type,
        date_from=filters.date_from, date_to=filters.date_to,
        status_filter=None, page=1, page_size=500, db=db, current_user=user,
    )
    items = records.items
    total_cost = round(sum(i.cost or 0 for i in items), 2)
    total_downtime = round(sum(i.downtime_hours or 0 for i in items), 2)
    by_type: dict[str, int] = {}
    for i in items:
        key = i.maintenance_type or "unspecified"
        by_type[key] = by_type.get(key, 0) + 1

    schedule = get_maintenance_schedule(db=db, current_user=user)
    scope_ids = _equipment_ids_for_scope(db, user, filters)
    overdue = [i for i in schedule.overdue if scope_ids is None or i.equipment_id in scope_ids]
    due_today = [i for i in schedule.due_today if scope_ids is None or i.equipment_id in scope_ids]

    return {
        "record_count": records.total,
        "total_cost": total_cost,
        "total_downtime_hours": total_downtime,
        "by_type": by_type,
        "preventive_count": by_type.get("preventive", 0),
        "corrective_count": by_type.get("corrective", 0),
        "emergency_count": by_type.get("emergency", 0),
        "overdue": [item.model_dump(mode="json") for item in overdue[:20]],
        "due_today": [item.model_dump(mode="json") for item in due_today[:20]],
        "_traceability": _traceability(
            "maintenance.list_maintenance + maintenance.get_maintenance_schedule",
            "Cost/downtime/type counts from work orders matching the selected scope and date "
            "range; overdue/due-today from the rule-based schedule view, filtered to matching equipment.",
            record_count=records.total,
        ),
    }


def _production_loss_section(db: Session, user: User, filters: ReportFilterValues) -> dict:
    result = list_production_loss(
        well_id=filters.well_id, equipment_id=filters.equipment_id, field_id=filters.field_id,
        facility_id=filters.facility_id, category=filters.production_loss_category,
        date_from=filters.date_from, date_to=filters.date_to,
        page=1, page_size=500, db=db, current_user=user,
    )
    items = result.items
    total_oil_lost = round(sum(i.estimated_bopd_lost or 0 for i in items), 1)
    total_gas_lost = round(sum(i.estimated_mscf_lost or 0 for i in items), 1)
    total_downtime = round(sum(i.downtime_hours or 0 for i in items), 2)
    revenue_by_currency: dict[str, float] = {}
    for i in items:
        if i.estimated_revenue_impact is not None and i.currency:
            revenue_by_currency[i.currency] = revenue_by_currency.get(i.currency, 0.0) + i.estimated_revenue_impact

    top_events = sorted(items, key=lambda i: i.estimated_revenue_impact or 0, reverse=True)[:5]
    well_totals: dict[str, float] = {}
    equipment_totals: dict[str, float] = {}
    for i in items:
        impact = i.estimated_revenue_impact or 0
        if i.well_code:
            well_totals[i.well_code] = well_totals.get(i.well_code, 0.0) + impact
        if i.equipment_tag:
            equipment_totals[i.equipment_tag] = equipment_totals.get(i.equipment_tag, 0.0) + impact
    top_wells = sorted(well_totals.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_equipment = sorted(equipment_totals.items(), key=lambda kv: kv[1], reverse=True)[:5]

    return {
        "event_count": result.total,
        "total_oil_bopd_lost": total_oil_lost,
        "total_gas_mscfd_lost": total_gas_lost,
        "total_downtime_hours": total_downtime,
        "estimated_revenue_impact": [{"currency": c, "amount": round(a, 2)} for c, a in sorted(revenue_by_currency.items())],
        "top_loss_events": [
            {
                "id": e.id, "loss_date": e.loss_date.isoformat(), "well_code": e.well_code,
                "equipment_tag": e.equipment_tag, "category": e.category, "cause": e.cause,
                "estimated_revenue_impact": e.estimated_revenue_impact, "currency": e.currency,
            }
            for e in top_events
        ],
        "top_affected_wells": [{"well_code": w, "estimated_revenue_impact": round(v, 2)} for w, v in top_wells],
        "top_affected_equipment": [{"equipment_tag": e, "estimated_revenue_impact": round(v, 2)} for e, v in top_equipment],
        "_traceability": _traceability(
            "production_loss.list_production_loss",
            "Estimated lost production/revenue calculated from recorded downtime and the "
            "applicable production baseline/commodity price for each event in the selected scope "
            "and period (see production_loss_calculations.py) - never fabricated for periods "
            "with no recorded loss.",
            record_count=result.total,
        ),
    }


def _economics_section(db: Session, user: User, filters: ReportFilterValues) -> dict:
    if not filters.date_from or not filters.date_to:
        return {"data_sufficient": False, "missing_data_note": "Economics section requires a date range."}
    boe_gas_factor = get_boe_gas_factor(db)
    price_series = _load_price_series(db)
    totals = _compute_scope_totals(
        db, filters.date_from, filters.date_to, price_series, boe_gas_factor,
        field_id=filters.field_id, facility_id=filters.facility_id,
        well_id=filters.well_id, equipment_id=filters.equipment_id,
    )
    total_cost = {}
    for currency, amount in totals["operating_dict"].items():
        total_cost[currency] = total_cost.get(currency, 0.0) + amount
    if totals["maintenance_total"]:
        total_cost["USD"] = total_cost.get("USD", 0.0) + totals["maintenance_total"]

    margin_by_currency = {}
    mismatch = False
    for currency in set(totals["revenue_total"]) | set(total_cost):
        if currency in totals["revenue_total"] and currency in total_cost:
            margin_by_currency[currency] = round(totals["revenue_total"][currency] - total_cost[currency], 2)
        elif currency in total_cost:
            mismatch = True

    def per_unit(amounts: dict[str, float], volume: float) -> dict[str, float]:
        return {c: round(a / volume, 4) for c, a in amounts.items()} if volume > 0 else {}

    return {
        "oil_bbl": totals["oil_total"],
        "gas_mscf": totals["gas_total"],
        "boe": totals["boe_total"],
        "estimated_revenue": [{"currency": c, "amount": round(a, 2)} for c, a in sorted(totals["revenue_total"].items())],
        "operating_cost": [{"currency": c, "amount": round(a, 2)} for c, a in sorted(totals["operating_dict"].items())],
        "maintenance_cost_usd": totals["maintenance_total"],
        "cost_per_bbl": [{"currency": c, "amount": v} for c, v in sorted(per_unit(total_cost, totals["oil_total"]).items())],
        "cost_per_boe": [{"currency": c, "amount": v} for c, v in sorted(per_unit(total_cost, totals["boe_total"]).items())],
        "estimated_operating_margin": [{"currency": c, "amount": a} for c, a in sorted(margin_by_currency.items())],
        "margin_currency_mismatch": mismatch,
        "_traceability": _traceability(
            "cost_revenue._compute_scope_totals",
            "Estimated revenue = production x resolved commodity price; estimated operating "
            "margin = estimated revenue - operating and maintenance cost, computed only where "
            "currencies match. Estimate for management/analyst review, not an audited accounting figure.",
        ),
    }


def _alerts_section(db: Session, user: User, filters: ReportFilterValues) -> dict:
    result = list_alerts(
        severity=filters.alert_severity, field_id=filters.field_id, facility_id=filters.facility_id,
        well_id=filters.well_id, equipment_id=filters.equipment_id,
        date_from=filters.date_from, date_to=filters.date_to,
        status_filter=None, page=1, page_size=200, db=db, current_user=user,
    )
    items = result.items
    by_severity: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for a in items:
        by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
        by_status[a.status] = by_status.get(a.status, 0) + 1
    open_statuses = {"new", "acknowledged", "investigating"}
    return {
        "total": result.total,
        "critical_count": by_severity.get("critical", 0),
        "high_count": by_severity.get("high", 0),
        "open_count": sum(n for s, n in by_status.items() if s in open_statuses),
        "resolved_count": by_status.get("resolved", 0),
        "by_severity": by_severity,
        "by_status": by_status,
        "recent": [a.model_dump(mode="json") for a in items[:10]],
        "_traceability": _traceability(
            "alerts.list_alerts",
            "Rule-based alert counts for the selected scope, severity, and date range - "
            "informational, never an automatically-executed action.",
            record_count=result.total,
        ),
    }


def _ai_insights_section(db: Session, user: User, filters: ReportFilterValues) -> dict:
    result = list_insights(
        field_id=filters.field_id, facility_id=filters.facility_id, well_id=filters.well_id,
        equipment_id=filters.equipment_id, date_from=filters.date_from, date_to=filters.date_to,
        status_filter=None, sort="severity", order="asc", page=1, page_size=200, db=db, current_user=user,
    )
    items = result.items
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}
    top = sorted(items, key=lambda i: severity_rank.get(i.severity, 5))[:10]
    return {
        "total": result.total,
        "highest_priority": [
            {
                "id": i.id, "title": i.title, "summary": i.summary, "severity": i.severity,
                "confidence_level": i.confidence_level, "category": i.category,
                "estimated_production_impact_value": i.estimated_production_impact_value,
                "estimated_production_impact_unit": i.estimated_production_impact_unit,
                "estimated_financial_impact_value": i.estimated_financial_impact_value,
                "estimated_financial_impact_currency": i.estimated_financial_impact_currency,
                "recommended_investigation": i.recommended_investigation,
                "evidence": [e.model_dump(mode="json") for e in i.evidence],
            }
            for i in top
        ],
        "_traceability": _traceability(
            "ai_insights.list_insights",
            "Evidence-cited, rule-based insights for the selected scope and date range, ranked by "
            "severity. Confidence is derived from independent evidence-category count, never a "
            "fabricated statistical score. Requires engineering/management review - not a "
            "confirmed root cause.",
            record_count=result.total,
        ),
    }


def _production_trend_section(db: Session, user: User, filters: ReportFilterValues) -> dict:
    trend = get_production_trends(
        metric="oil_gas_water", well_id=filters.well_id, field_id=filters.field_id,
        facility_id=filters.facility_id, date_from=filters.date_from, date_to=filters.date_to,
        db=db, current_user=user,
    )
    return {
        "points": trend.points,
        "_traceability": _traceability("production.get_production_trends", "Daily oil/gas/water totals for the selected scope and date range."),
    }


def _production_by_scope_section(db: Session, user: User, filters: ReportFilterValues) -> dict:
    by_field = get_production_by_scope(group_by="field", date_from=filters.date_from, date_to=filters.date_to, order="desc", limit=20, db=db, current_user=user)
    by_facility = get_production_by_scope(group_by="facility", date_from=filters.date_from, date_to=filters.date_to, order="desc", limit=20, db=db, current_user=user)
    by_well = get_production_by_scope(group_by="well", date_from=filters.date_from, date_to=filters.date_to, order="desc", limit=10, db=db, current_user=user)
    lowest_wells = get_production_by_scope(group_by="well", date_from=filters.date_from, date_to=filters.date_to, order="asc", limit=10, db=db, current_user=user)
    return {
        "by_field": [b.model_dump(mode="json") for b in by_field.bars],
        "by_facility": [b.model_dump(mode="json") for b in by_facility.bars],
        "top_wells": [b.model_dump(mode="json") for b in by_well.bars],
        "lowest_wells": [b.model_dump(mode="json") for b in lowest_wells.bars],
        "_traceability": _traceability("production.get_production_by_scope", "Total oil/gas/water/BOE per field, facility, and well for the selected date range."),
    }


def _actual_vs_target_section(db: Session, user: User, filters: ReportFilterValues) -> dict:
    result = get_actual_vs_target(
        well_id=filters.well_id, field_id=filters.field_id, facility_id=filters.facility_id,
        date_from=filters.date_from, date_to=filters.date_to, db=db, current_user=user,
    )
    return {
        "points": [p.model_dump(mode="json") for p in result.points],
        "_traceability": _traceability("production.get_actual_vs_target", "Daily actual oil production vs. the resolved ProductionTarget for the selected scope."),
    }


def _executive_summary_section(sections_computed: dict) -> dict:
    """Built entirely from sections already computed above — never a separate calculation or
    LLM call. See services/ai_providers/ usage in routers/reports.py for the optional narrative
    phrasing layered on top of this."""
    production = sections_computed.get("production", {}).get("kpis", {})
    alerts = sections_computed.get("alerts", {})
    losses = sections_computed.get("production_loss", {})
    economics = sections_computed.get("economics", {})
    insights = sections_computed.get("ai_insights", {})

    top_loss_events = losses.get("top_loss_events", [])
    top_insights = insights.get("highest_priority", [])

    return {
        "what_happened": (
            f"Oil production totaled {production.get('total_oil_bbl', 0):,.0f} bbl, "
            f"gas {production.get('total_gas_mscf', 0):,.0f} mscf, across "
            f"{production.get('producing_wells_count', 0)} producing well(s)."
        ),
        "why_it_matters": (
            f"Estimated operating margin: {economics.get('estimated_operating_margin', [])}. "
            "See the Economics section for the full currency breakdown."
        ),
        "biggest_risks": [
            f"{alerts.get('critical_count', 0)} critical alert(s) open."
            if alerts.get("critical_count") else "No critical alerts open this period.",
        ] + [f"Insight: {i['title']}" for i in top_insights[:3]],
        "biggest_opportunities": [
            f"Loss event ({e['well_code'] or e['equipment_tag'] or 'unscoped'}): estimated "
            f"{e['estimated_revenue_impact']} {e['currency']} potential recovery"
            for e in top_loss_events[:3]
            if e.get("estimated_revenue_impact")
        ],
        "recommended_investigations": [
            i["recommended_investigation"] for i in top_insights if i.get("recommended_investigation")
        ][:5],
    }


SECTION_BUILDERS = {
    "production": _production_section,
    "equipment": _equipment_section,
    "maintenance": _maintenance_section,
    "production_loss": _production_loss_section,
    "economics": _economics_section,
    "alerts": _alerts_section,
    "ai_insights": _ai_insights_section,
    "production_trend": _production_trend_section,
    "production_by_scope": _production_by_scope_section,
    "actual_vs_target": _actual_vs_target_section,
}


def build_report(db: Session, user: User, report_type: str, filters: ReportFilterValues, sections: list[str] | None) -> dict:
    if report_type == "what_if_scenario":
        return build_what_if_scenario_report(db, filters)

    requested = sections or default_sections(report_type)
    computed: dict[str, dict] = {}
    for key in requested:
        if key == "executive_summary":
            continue
        builder = SECTION_BUILDERS.get(key)
        if builder is None:
            continue
        computed[key] = builder(db, user, filters)

    if _wants(requested, "executive_summary"):
        computed["executive_summary"] = _executive_summary_section(computed)

    return {
        "report_type": report_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filters": filters.as_dict(),
        "sections": computed,
        "disclaimer_text": REPORT_DISCLAIMER,
        "synthetic_data_disclaimer": SYNTHETIC_DATA_DISCLAIMER,
    }


def build_what_if_scenario_report(db: Session, filters: ReportFilterValues) -> dict:
    if not filters.scenario_id:
        return {
            "report_type": "what_if_scenario",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filters": filters.as_dict(),
            "sections": {},
            "data_sufficient": False,
            "missing_data_note": "Select a saved What-If scenario to include in this report.",
            "disclaimer_text": REPORT_DISCLAIMER,
            "synthetic_data_disclaimer": SYNTHETIC_DATA_DISCLAIMER,
        }
    scenario = _get_scenario_or_404(db, filters.scenario_id)
    results = _results_json_to_schema(scenario.results)
    return {
        "report_type": "what_if_scenario",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filters": filters.as_dict(),
        "sections": {
            "scenario": {
                "scenario_id": scenario.id,
                "scenario_name": scenario.name,
                "assumptions": scenario.assumptions,
                "results": results.model_dump(mode="json") if results else None,
                "label": "Scenario Estimate",
                "_traceability": _traceability(
                    "what_if.get_scenario",
                    "Baseline computed from recorded production/cost/maintenance data for the "
                    "scenario's saved scope and period; scenario figures are deterministic "
                    "calculations from the saved assumptions - a planning estimate, never a "
                    "guaranteed outcome or forecast.",
                ),
            }
        },
        "disclaimer_text": REPORT_DISCLAIMER,
        "synthetic_data_disclaimer": SYNTHETIC_DATA_DISCLAIMER,
    }
