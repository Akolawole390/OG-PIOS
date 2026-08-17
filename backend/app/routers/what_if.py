"""What-If Simulator — a planning/decision-support tool that compares a computed baseline
against a hypothetical scenario. Never modifies production/cost/maintenance records, never
controls equipment or SCADA/DCS, never presents a scenario as a guaranteed outcome — see the
standing AI/analytics-output guardrail in root CLAUDE.md, which explicitly names this module.

Deterministic calculation always happens first (services/whatif_calculations.py, pure, no AI
involved) — the optional `/interpret` endpoint only ever phrases already-computed figures,
exactly like AI Insights' `/interpret`, reusing the same services/ai_providers/ +
services/rate_limit.py infrastructure (a 4th consumer of the private cost_revenue.py scope
helpers, after alert_rules.py/insight_engine.py/ai_assistant.py).

A saved Scenario's `results` is a FROZEN SNAPSHOT computed at save/run time (see
models/simulation.py's docstring) — GET never recomputes; only POST /rerun does.
"""

import dataclasses
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.field import Facility, Field, Well
from app.models.equipment import Equipment
from app.models.simulation import Scenario
from app.models.user import User
from app.routers.cost_revenue import (
    MAINTENANCE_COST_CURRENCY,
    _combine_money,
    _compute_scope_totals,
    _load_price_series,
    _margin_by_currency,
    _price_on,
)
from app.schemas.economics import MoneyByCurrency
from app.schemas.whatif import (
    BaselineConfigSchema,
    BaselineMetricsRead,
    ComparisonRowRead,
    CompareRequest,
    CompareResponse,
    GuardrailFlagRead,
    InterpretResponse,
    PreviewRequest,
    PreviewResponse,
    ScenarioAssumptionsSchema,
    ScenarioCompareEntry,
    ScenarioCreate,
    ScenarioListItem,
    ScenarioListResponse,
    ScenarioMetricsRead,
    ScenarioRead,
    ScenarioResultsRead,
    ScenarioUpdate,
    SensitivityPointRead,
    SensitivityRequest,
    SensitivityResponse,
)
from app.services.ai_providers.base import AIProvider, StructuredPrompt
from app.services.ai_providers.factory import get_ai_provider_dependency
from app.services.audit import AuditAction, record_audit_event
from app.services.rate_limit import rate_limiter
from app.services.system_settings import get_boe_gas_factor, get_whatif_reasonable_change_pct_bound
from app.services.whatif_calculations import (
    CALCULATION_VERSION,
    WHATIF_DISCLAIMER,
    BaselineMetrics,
    ComparisonRow,
    GuardrailFlag,
    ScenarioAssumptions,
    ScenarioMetrics,
    build_comparison,
    compute_scenario_metrics,
    run_sensitivity,
    validate_assumptions,
)

router = APIRouter(prefix="/what-if", tags=["what-if"])

NON_VIEWER_ROLES = (
    "Administrator",
    "Production Operator",
    "Production Engineer",
    "Maintenance Engineer",
    "Management",
    "Analyst",
)

SORTABLE_FIELDS = {
    "name": Scenario.name,
    "created_at": Scenario.created_at,
    "updated_at": Scenario.updated_at,
    "last_run_at": Scenario.last_run_at,
}


# ----- Reference validation -----


def _validate_scope(db: Session, baseline: BaselineConfigSchema) -> None:
    if baseline.date_from > baseline.date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date_from must be on or before date_to")
    if baseline.field_id is not None and db.get(Field, baseline.field_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    if baseline.facility_id is not None and db.get(Facility, baseline.facility_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    if baseline.well_id is not None and db.get(Well, baseline.well_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Well not found")
    if baseline.equipment_id is not None and db.get(Equipment, baseline.equipment_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")


# ----- Baseline resolution -----


def _resolve_baseline(db: Session, baseline: BaselineConfigSchema) -> BaselineMetrics:
    boe_gas_factor = get_boe_gas_factor(db)
    price_series = _load_price_series(db)

    totals = _compute_scope_totals(
        db,
        baseline.date_from,
        baseline.date_to,
        price_series,
        boe_gas_factor,
        field_id=baseline.field_id,
        facility_id=baseline.facility_id,
        well_id=baseline.well_id,
        equipment_id=baseline.equipment_id,
    )

    maintenance_dict = (
        {MAINTENANCE_COST_CURRENCY: totals["maintenance_total"]} if totals["maintenance_total"] else {}
    )
    total_cost_dict = _combine_money(totals["operating_dict"], maintenance_dict)
    margin_dict, margin_mismatch = _margin_by_currency(totals["revenue_total"], total_cost_dict)

    oil_price = _price_on(price_series.get("oil", []), baseline.date_to)
    gas_price = _price_on(price_series.get("gas", []), baseline.date_to)

    period_days = (baseline.date_to - baseline.date_from).days + 1

    data_sufficient = True
    missing_data_note = None
    if totals["oil_total"] == 0 and totals["gas_total"] == 0:
        data_sufficient = False
        missing_data_note = (
            "No production records found for the selected scope and period. Baseline cannot "
            "be calculated reliably — choose a different date range or scope."
        )

    return BaselineMetrics(
        period_start=baseline.date_from,
        period_end=baseline.date_to,
        period_days=period_days,
        oil_bbl=totals["oil_total"],
        gas_mscf=totals["gas_total"],
        boe=totals["boe_total"],
        oil_price=oil_price[0] if oil_price else None,
        oil_price_currency=oil_price[1] if oil_price else None,
        gas_price=gas_price[0] if gas_price else None,
        gas_price_currency=gas_price[1] if gas_price else None,
        revenue_dict=totals["revenue_total"],
        oil_revenue_dict=totals["oil_revenue_dict"],
        gas_revenue_dict=totals["gas_revenue_dict"],
        operating_cost_dict=totals["operating_dict"],
        energy_cost_dict=totals["energy_dict"],
        other_cost_dict=totals["other_dict"],
        maintenance_cost_dict=maintenance_dict,
        total_cost_dict=total_cost_dict,
        lost_oil_bbl=totals["lost_oil_total"],
        lost_gas_mscf=totals["lost_gas_total"],
        production_loss_revenue_dict=totals["loss_revenue_dict"],
        downtime_hours=totals["downtime_hours_total"],
        margin_dict=margin_dict,
        margin_currency_mismatch=margin_mismatch,
        data_sufficient=data_sufficient,
        missing_data_note=missing_data_note,
    )


def _run_scenario(
    db: Session, baseline_config: BaselineConfigSchema, assumptions: ScenarioAssumptions
) -> tuple[BaselineMetrics, ScenarioMetrics, list[ComparisonRow], list[GuardrailFlag]]:
    """Shared core for preview/create/update/rerun: validate guardrails (422 on any hard-fail,
    never a silent rejection of the merely unusual), resolve the baseline from real data, then
    run the deterministic calculation exactly once."""
    reasonable_bound = get_whatif_reasonable_change_pct_bound(db)
    flags = validate_assumptions(assumptions, reasonable_bound)
    errors = [f for f in flags if f.severity == "error"]
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[dataclasses.asdict(f) for f in errors],
        )

    baseline = _resolve_baseline(db, baseline_config)
    if not baseline.data_sufficient:
        return baseline, ScenarioMetrics(), [], flags

    boe_gas_factor = get_boe_gas_factor(db)
    scenario = compute_scenario_metrics(baseline, assumptions, boe_gas_factor)
    comparison = build_comparison(baseline, scenario)
    return baseline, scenario, comparison, flags


# ----- JSON <-> dataclass/schema conversion (Scenario.results is a frozen JSON snapshot) -----


def _money_list(amounts: dict) -> list[MoneyByCurrency]:
    return [MoneyByCurrency(currency=c, amount=a) for c, a in sorted((amounts or {}).items())]


def _baseline_to_read(b: BaselineMetrics) -> BaselineMetricsRead:
    return BaselineMetricsRead(
        period_start=b.period_start,
        period_end=b.period_end,
        period_days=b.period_days,
        oil_bbl=b.oil_bbl,
        gas_mscf=b.gas_mscf,
        boe=b.boe,
        oil_price=b.oil_price,
        oil_price_currency=b.oil_price_currency,
        gas_price=b.gas_price,
        gas_price_currency=b.gas_price_currency,
        revenue=_money_list(b.revenue_dict),
        operating_cost=_money_list(b.operating_cost_dict),
        maintenance_cost=_money_list(b.maintenance_cost_dict),
        total_cost=_money_list(b.total_cost_dict),
        lost_oil_bbl=b.lost_oil_bbl,
        lost_gas_mscf=b.lost_gas_mscf,
        production_loss_revenue=_money_list(b.production_loss_revenue_dict),
        downtime_hours=b.downtime_hours,
        margin=_money_list(b.margin_dict),
        margin_currency_mismatch=b.margin_currency_mismatch,
        data_sufficient=b.data_sufficient,
        missing_data_note=b.missing_data_note,
    )


def _scenario_to_read(s: ScenarioMetrics) -> ScenarioMetricsRead:
    return ScenarioMetricsRead(
        oil_bbl=s.oil_bbl,
        gas_mscf=s.gas_mscf,
        boe=s.boe,
        oil_price=s.oil_price,
        oil_price_currency=s.oil_price_currency,
        gas_price=s.gas_price,
        gas_price_currency=s.gas_price_currency,
        revenue=_money_list(s.revenue_dict),
        operating_cost=_money_list(s.operating_cost_dict),
        maintenance_cost=_money_list(s.maintenance_cost_dict),
        total_cost=_money_list(s.total_cost_dict),
        lost_oil_bbl=s.lost_oil_bbl,
        lost_gas_mscf=s.lost_gas_mscf,
        production_loss_revenue=_money_list(s.production_loss_revenue_dict),
        downtime_hours=s.downtime_hours,
        margin=_money_list(s.margin_dict),
        margin_currency_mismatch=s.margin_currency_mismatch,
        recovered_downtime_hours=s.recovered_downtime_hours,
        recovered_production_bbl=s.recovered_production_bbl,
        potential_loss_reduction_oil_bbl=s.potential_loss_reduction_oil_bbl,
        potential_loss_reduction_gas_mscf=s.potential_loss_reduction_gas_mscf,
        potential_loss_reduction_revenue=_money_list(s.potential_loss_reduction_revenue_dict),
        potential_cost_saving=_money_list(s.potential_cost_saving_dict),
    )


def _results_to_json(
    baseline: BaselineMetrics, scenario: ScenarioMetrics, comparison: list[ComparisonRow], flags: list[GuardrailFlag]
) -> dict:
    baseline_dict = dataclasses.asdict(baseline)
    baseline_dict["period_start"] = baseline.period_start.isoformat()
    baseline_dict["period_end"] = baseline.period_end.isoformat()
    return {
        "baseline": baseline_dict,
        "scenario": dataclasses.asdict(scenario),
        "comparison": [dataclasses.asdict(row) for row in comparison],
        "guardrail_flags": [dataclasses.asdict(f) for f in flags],
    }


def _results_json_to_schema(results: dict | None) -> ScenarioResultsRead | None:
    if not results:
        return None
    b = results["baseline"]
    s = results["scenario"]
    return ScenarioResultsRead(
        baseline=BaselineMetricsRead(
            period_start=b["period_start"],
            period_end=b["period_end"],
            period_days=b["period_days"],
            oil_bbl=b["oil_bbl"],
            gas_mscf=b["gas_mscf"],
            boe=b["boe"],
            oil_price=b["oil_price"],
            oil_price_currency=b["oil_price_currency"],
            gas_price=b["gas_price"],
            gas_price_currency=b["gas_price_currency"],
            revenue=_money_list(b["revenue_dict"]),
            operating_cost=_money_list(b["operating_cost_dict"]),
            maintenance_cost=_money_list(b["maintenance_cost_dict"]),
            total_cost=_money_list(b["total_cost_dict"]),
            lost_oil_bbl=b["lost_oil_bbl"],
            lost_gas_mscf=b["lost_gas_mscf"],
            production_loss_revenue=_money_list(b["production_loss_revenue_dict"]),
            downtime_hours=b["downtime_hours"],
            margin=_money_list(b["margin_dict"]),
            margin_currency_mismatch=b["margin_currency_mismatch"],
            data_sufficient=b["data_sufficient"],
            missing_data_note=b["missing_data_note"],
        ),
        scenario=ScenarioMetricsRead(
            oil_bbl=s["oil_bbl"],
            gas_mscf=s["gas_mscf"],
            boe=s["boe"],
            oil_price=s["oil_price"],
            oil_price_currency=s["oil_price_currency"],
            gas_price=s["gas_price"],
            gas_price_currency=s["gas_price_currency"],
            revenue=_money_list(s["revenue_dict"]),
            operating_cost=_money_list(s["operating_cost_dict"]),
            maintenance_cost=_money_list(s["maintenance_cost_dict"]),
            total_cost=_money_list(s["total_cost_dict"]),
            lost_oil_bbl=s["lost_oil_bbl"],
            lost_gas_mscf=s["lost_gas_mscf"],
            production_loss_revenue=_money_list(s["production_loss_revenue_dict"]),
            downtime_hours=s["downtime_hours"],
            margin=_money_list(s["margin_dict"]),
            margin_currency_mismatch=s["margin_currency_mismatch"],
            recovered_downtime_hours=s["recovered_downtime_hours"],
            recovered_production_bbl=s["recovered_production_bbl"],
            potential_loss_reduction_oil_bbl=s["potential_loss_reduction_oil_bbl"],
            potential_loss_reduction_gas_mscf=s["potential_loss_reduction_gas_mscf"],
            potential_loss_reduction_revenue=_money_list(s["potential_loss_reduction_revenue_dict"]),
            potential_cost_saving=_money_list(s["potential_cost_saving_dict"]),
        ),
        comparison=[ComparisonRowRead(**row) for row in results["comparison"]],
        guardrail_flags=[GuardrailFlagRead(**f) for f in results["guardrail_flags"]],
    )


# ----- Scenario CRUD helpers -----


def _scenario_query(db: Session):
    return db.query(Scenario).options(
        joinedload(Scenario.created_by),
        joinedload(Scenario.field),
        joinedload(Scenario.facility),
        joinedload(Scenario.well),
        joinedload(Scenario.equipment),
    )


def _get_scenario_or_404(db: Session, id: int) -> Scenario:
    scenario = _scenario_query(db).filter(Scenario.id == id).first()
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return scenario


def _build_list_item(scenario: Scenario) -> ScenarioListItem:
    return ScenarioListItem(
        id=scenario.id,
        name=scenario.name,
        description=scenario.description,
        created_by_id=scenario.created_by_id,
        created_by_name=scenario.created_by.full_name if scenario.created_by else None,
        baseline_date_from=scenario.baseline_date_from,
        baseline_date_to=scenario.baseline_date_to,
        field_id=scenario.field_id,
        field_name=scenario.field.name if scenario.field else None,
        facility_id=scenario.facility_id,
        facility_name=scenario.facility.name if scenario.facility else None,
        well_id=scenario.well_id,
        well_code=scenario.well.well_id if scenario.well else None,
        equipment_id=scenario.equipment_id,
        equipment_tag=scenario.equipment.equipment_tag if scenario.equipment else None,
        calculation_version=scenario.calculation_version,
        last_run_at=scenario.last_run_at,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
        has_results=scenario.results is not None,
    )


def _build_read(scenario: Scenario) -> ScenarioRead:
    item = _build_list_item(scenario)
    return ScenarioRead(
        **item.model_dump(),
        assumptions=ScenarioAssumptionsSchema(**(scenario.assumptions or {})),
        results=_results_json_to_schema(scenario.results),
        disclaimer_text=WHATIF_DISCLAIMER,
    )


# ----- List / detail (must come before /{id}) -----


@router.get("/scenarios", response_model=ScenarioListResponse)
def list_scenarios(
    search: str | None = None,
    created_by_id: int | None = None,
    field_id: int | None = None,
    well_id: int | None = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScenarioListResponse:
    query = _scenario_query(db)

    if search:
        query = query.filter(Scenario.name.ilike(f"%{search}%"))
    if created_by_id:
        query = query.filter(Scenario.created_by_id == created_by_id)
    if field_id:
        query = query.filter(Scenario.field_id == field_id)
    if well_id:
        query = query.filter(Scenario.well_id == well_id)

    total = query.count()

    sort_column = SORTABLE_FIELDS.get(sort, Scenario.created_at)
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()
    query = query.order_by(sort_column)

    records = query.offset((page - 1) * page_size).limit(page_size).all()
    return ScenarioListResponse(
        items=[_build_list_item(r) for r in records], total=total, page=page, page_size=page_size
    )


@router.get("/scenarios/{id}", response_model=ScenarioRead)
def get_scenario(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScenarioRead:
    return _build_read(_get_scenario_or_404(db, id))


@router.post("/scenarios", response_model=ScenarioRead, status_code=status.HTTP_201_CREATED)
def create_scenario(
    payload: ScenarioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> ScenarioRead:
    _validate_scope(db, payload.baseline)
    assumptions = ScenarioAssumptions.from_dict(payload.assumptions.model_dump(exclude_none=True))

    baseline, scenario, comparison, flags = _run_scenario(db, payload.baseline, assumptions)
    now = datetime.now(timezone.utc)

    record = Scenario(
        name=payload.name,
        description=payload.description,
        created_by_id=current_user.id,
        baseline_date_from=payload.baseline.date_from,
        baseline_date_to=payload.baseline.date_to,
        field_id=payload.baseline.field_id,
        facility_id=payload.baseline.facility_id,
        well_id=payload.baseline.well_id,
        equipment_id=payload.baseline.equipment_id,
        assumptions=assumptions.as_dict(),
        results=_results_to_json(baseline, scenario, comparison, flags),
        calculation_version=CALCULATION_VERSION,
        last_run_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    record_audit_event(
        db, current_user, AuditAction.WHATIF_SCENARIO_CREATED, "scenario", resource_id=record.id,
        details=f"Created what-if scenario '{record.name}'",
    )
    return _build_read(_get_scenario_or_404(db, record.id))


@router.put("/scenarios/{id}", response_model=ScenarioRead)
def update_scenario(
    id: int,
    payload: ScenarioUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> ScenarioRead:
    record = _get_scenario_or_404(db, id)

    if payload.name is not None:
        record.name = payload.name
    if payload.description is not None:
        record.description = payload.description

    baseline_config = BaselineConfigSchema(
        date_from=payload.baseline.date_from if payload.baseline else record.baseline_date_from,
        date_to=payload.baseline.date_to if payload.baseline else record.baseline_date_to,
        field_id=payload.baseline.field_id if payload.baseline else record.field_id,
        facility_id=payload.baseline.facility_id if payload.baseline else record.facility_id,
        well_id=payload.baseline.well_id if payload.baseline else record.well_id,
        equipment_id=payload.baseline.equipment_id if payload.baseline else record.equipment_id,
    )
    assumptions_schema = (
        payload.assumptions if payload.assumptions is not None else ScenarioAssumptionsSchema(**(record.assumptions or {}))
    )
    _validate_scope(db, baseline_config)
    assumptions = ScenarioAssumptions.from_dict(assumptions_schema.model_dump(exclude_none=True))

    baseline, scenario, comparison, flags = _run_scenario(db, baseline_config, assumptions)
    now = datetime.now(timezone.utc)

    record.baseline_date_from = baseline_config.date_from
    record.baseline_date_to = baseline_config.date_to
    record.field_id = baseline_config.field_id
    record.facility_id = baseline_config.facility_id
    record.well_id = baseline_config.well_id
    record.equipment_id = baseline_config.equipment_id
    record.assumptions = assumptions.as_dict()
    record.results = _results_to_json(baseline, scenario, comparison, flags)
    record.calculation_version = CALCULATION_VERSION
    record.last_run_at = now

    db.commit()
    db.refresh(record)
    return _build_read(_get_scenario_or_404(db, record.id))


@router.delete("/scenarios/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> None:
    record = _get_scenario_or_404(db, id)
    db.delete(record)
    db.commit()


@router.post("/scenarios/{id}/rerun", response_model=ScenarioRead)
def rerun_scenario(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> ScenarioRead:
    """Recomputes against CURRENT data without changing name/description/assumptions — the only
    way a saved scenario's frozen `results` snapshot ever changes (a plain GET never does)."""
    record = _get_scenario_or_404(db, id)
    baseline_config = BaselineConfigSchema(
        date_from=record.baseline_date_from,
        date_to=record.baseline_date_to,
        field_id=record.field_id,
        facility_id=record.facility_id,
        well_id=record.well_id,
        equipment_id=record.equipment_id,
    )
    assumptions = ScenarioAssumptions.from_dict(record.assumptions or {})

    baseline, scenario, comparison, flags = _run_scenario(db, baseline_config, assumptions)
    record.results = _results_to_json(baseline, scenario, comparison, flags)
    record.calculation_version = CALCULATION_VERSION
    record.last_run_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(record)
    return _build_read(_get_scenario_or_404(db, record.id))


# ----- Preview / Compare / Sensitivity -----


@router.post("/preview", response_model=PreviewResponse)
def preview_scenario(
    payload: PreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PreviewResponse:
    """Ad-hoc baseline+assumptions run — nothing persisted. The Scenario Builder's live-preview
    step before the user chooses to save."""
    _validate_scope(db, payload.baseline)
    assumptions = ScenarioAssumptions.from_dict(payload.assumptions.model_dump(exclude_none=True))
    baseline, scenario, comparison, flags = _run_scenario(db, payload.baseline, assumptions)
    return PreviewResponse(
        results=ScenarioResultsRead(
            baseline=_baseline_to_read(baseline),
            scenario=_scenario_to_read(scenario),
            comparison=[ComparisonRowRead(**dataclasses.asdict(r)) for r in comparison],
            guardrail_flags=[GuardrailFlagRead(**dataclasses.asdict(f)) for f in flags],
        ),
        calculation_version=CALCULATION_VERSION,
        disclaimer_text=WHATIF_DISCLAIMER,
    )


@router.post("/compare", response_model=CompareResponse)
def compare_scenarios(
    payload: CompareRequest,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider_dependency),
    current_user: User = Depends(get_current_user),
) -> CompareResponse:
    """Compares each scenario's STORED results — never recomputes (a scenario must be /rerun
    explicitly if the caller wants current-data figures)."""
    if len(payload.scenario_ids) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide at least 2 scenario_ids")

    records = _scenario_query(db).filter(Scenario.id.in_(payload.scenario_ids)).all()
    found_ids = {r.id for r in records}
    missing = [i for i in payload.scenario_ids if i not in found_ids]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scenario(s) not found: {missing}")

    by_id = {r.id: r for r in records}
    ordered = [by_id[i] for i in payload.scenario_ids]
    entries = [
        ScenarioCompareEntry(id=r.id, name=r.name, results=_results_json_to_schema(r.results)) for r in ordered
    ]

    narrative = None
    if payload.narrative:
        prompt = StructuredPrompt(
            task="Compare these already-computed What-If scenarios for an engineering/management audience.",
            data={
                e.name: {
                    "margin": [m.model_dump() for m in e.results.scenario.margin] if e.results else None,
                    "revenue": [m.model_dump() for m in e.results.scenario.revenue] if e.results else None,
                }
                for e in entries
            },
        )
        narrative = provider.interpret(prompt).text

    return CompareResponse(scenarios=entries, ai_narrative=narrative, disclaimer_text=WHATIF_DISCLAIMER)


@router.post("/sensitivity", response_model=SensitivityResponse)
def sensitivity_analysis(
    payload: SensitivityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SensitivityResponse:
    """Sweeps one assumption variable across a list of values (e.g. downtime_change_pct at
    0/-10/-20/-30/-40/-50), reusing the exact same deterministic formulas once per point — never
    a separate statistical model."""
    _validate_scope(db, payload.baseline)
    if payload.variable not in ScenarioAssumptions.__dataclass_fields__:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown variable: {payload.variable}")
    if not payload.values:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide at least one value to sweep")

    baseline = _resolve_baseline(db, payload.baseline)
    base_assumptions = ScenarioAssumptions.from_dict(payload.base_assumptions.model_dump(exclude_none=True))

    if not baseline.data_sufficient:
        return SensitivityResponse(
            baseline=_baseline_to_read(baseline), variable=payload.variable, points=[], disclaimer_text=WHATIF_DISCLAIMER
        )

    boe_gas_factor = get_boe_gas_factor(db)
    points = run_sensitivity(baseline, base_assumptions, payload.variable, payload.values, boe_gas_factor)

    return SensitivityResponse(
        baseline=_baseline_to_read(baseline),
        variable=payload.variable,
        points=[
            SensitivityPointRead(
                variable_value=p.variable_value,
                recovered_production_bbl=p.recovered_production_bbl,
                recovered_downtime_hours=p.recovered_downtime_hours,
                revenue_impact=_money_list(p.revenue_impact_dict),
                margin_impact=_money_list(p.margin_impact_dict),
            )
            for p in points
        ],
        disclaimer_text=WHATIF_DISCLAIMER,
    )


# ----- AI interpretation -----


@router.post("/scenarios/{id}/interpret", response_model=InterpretResponse)
def interpret_scenario(
    id: int,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider_dependency),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
    _rate_limited: User = Depends(rate_limiter("whatif-interpret", limit=10, window_seconds=60)),
) -> InterpretResponse:
    record = _get_scenario_or_404(db, id)
    if not record.results:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Scenario has no results yet — run it first")

    results = _results_json_to_schema(record.results)
    prompt = StructuredPrompt(
        task=f"Interpret this What-If scenario's already-computed results for an engineering/management audience: {record.name}",
        data={
            "assumptions": record.assumptions,
            "baseline_revenue": [m.model_dump() for m in results.baseline.revenue],
            "scenario_revenue": [m.model_dump() for m in results.scenario.revenue],
            "baseline_margin": [m.model_dump() for m in results.baseline.margin],
            "scenario_margin": [m.model_dump() for m in results.scenario.margin],
            "recovered_production_bbl": results.scenario.recovered_production_bbl,
            "guardrail_flags": [f.message for f in results.guardrail_flags],
        },
        time_period=f"{results.baseline.period_start} to {results.baseline.period_end}",
    )
    interpretation = provider.interpret(prompt)

    return InterpretResponse(
        scenario_id=record.id,
        interpretation=interpretation.text,
        provider=interpretation.provider,
        model=interpretation.model,
        disclaimer_text=WHATIF_DISCLAIMER,
    )
