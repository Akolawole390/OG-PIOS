from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.deps import get_current_user
from app.models.economics import CommodityPrice, OperatingCost, ProductionLoss
from app.models.equipment import Equipment, MaintenanceRecord
from app.models.field import Facility, Field, Well
from app.models.production import ProductionRecord
from app.models.user import User
from app.routers.equipment import _resolve_scope
from app.schemas.economics import (
    CostAlert,
    CostAlertsResponse,
    CostRevenueDashboardResponse,
    CostSection,
    CostTrendPoint,
    CostTrendResponse,
    EconomicsByScopeResponse,
    EconomicsScopeRow,
    EconomicsSection,
    MarginTrendPoint,
    MarginTrendResponse,
    MoneyByCurrency,
    ProductionLossSection,
    ProductionTotals,
    RevenueSection,
    RevenueTrendPoint,
    RevenueTrendResponse,
    UnitEconomicsResponse,
)
from app.services.economics_calculations import ECONOMICS_DISCLAIMER, compute_per_unit, estimate_operating_margin, estimate_revenue
from app.services.production_calculations import compute_boe
from app.services.system_settings import get_boe_gas_factor

router = APIRouter(prefix="/cost-revenue", tags=["cost-revenue"])

# Maintenance module's MaintenanceRecord.cost has no currency column — the whole rest of that
# module's UI displays it with an unconditional "$" prefix, so this module makes the same
# assumption explicit rather than silently guessing: maintenance cost is treated as USD.
MAINTENANCE_COST_CURRENCY = "USD"


# ----- Shared aggregation helpers -----


def _money_list(amounts_by_currency: dict[str, float]) -> list[MoneyByCurrency]:
    return [MoneyByCurrency(currency=c, amount=round(a, 2)) for c, a in sorted(amounts_by_currency.items())]


def _combine_money(*dicts: dict[str, float]) -> dict[str, float]:
    combined: dict[str, float] = {}
    for d in dicts:
        for currency, amount in d.items():
            combined[currency] = combined.get(currency, 0.0) + amount
    return combined


def _per_unit_by_currency(amounts: dict[str, float], volume: float | None) -> dict[str, float]:
    result: dict[str, float] = {}
    for currency, amount in amounts.items():
        value = compute_per_unit(amount, volume)
        if value is not None:
            result[currency] = value
    return result


def _margin_by_currency(revenue: dict[str, float], cost: dict[str, float]) -> tuple[dict[str, float], bool]:
    matched = set(revenue.keys()) & set(cost.keys())
    # A cost currency with no matching revenue currency means real cost data would be
    # silently excluded from the margin below — that's a mismatch even when some other
    # currency *does* match (e.g. NGN operating cost alongside USD-assumed maintenance
    # cost, netted only against USD revenue). Flagging only a *total* currency disjunction
    # would let a scope with mixed-currency costs show a margin that quietly omits part of
    # its real cost — the exact fabrication this module's currency rule forbids.
    unmatched_cost_currencies = set(cost.keys()) - set(revenue.keys())
    mismatch = bool(unmatched_cost_currencies)
    margins = {c: estimate_operating_margin(revenue[c], cost[c]) for c in matched}
    return {c: v for c, v in margins.items() if v is not None}, mismatch


def _load_price_series(db: Session) -> dict[str, list[tuple[date, float, str]]]:
    rows = db.query(CommodityPrice).order_by(CommodityPrice.effective_date).all()
    series: dict[str, list[tuple[date, float, str]]] = {}
    for r in rows:
        series.setdefault(r.commodity, []).append((r.effective_date, r.price, r.currency))
    return series


def _price_on(series: list[tuple[date, float, str]], on_date: date) -> tuple[float, str] | None:
    candidates = [p for p in series if p[0] <= on_date]
    if not candidates:
        return None
    _, price, currency = candidates[-1]
    return price, currency


def _revenue_dicts_for_records(
    records: list[ProductionRecord], price_series: dict[str, list[tuple[date, float, str]]]
) -> tuple[dict[str, float], dict[str, float]]:
    oil_series = price_series.get("oil", [])
    gas_series = price_series.get("gas", [])
    oil_by_currency: dict[str, float] = {}
    gas_by_currency: dict[str, float] = {}
    for r in records:
        oil_price = _price_on(oil_series, r.record_date)
        gas_price = _price_on(gas_series, r.record_date)
        oil_rev, gas_rev, _ = estimate_revenue(
            r.oil_bopd, r.gas_mscfd, oil_price[0] if oil_price else None, gas_price[0] if gas_price else None
        )
        if oil_rev is not None:
            oil_by_currency[oil_price[1]] = oil_by_currency.get(oil_price[1], 0.0) + oil_rev
        if gas_rev is not None:
            gas_by_currency[gas_price[1]] = gas_by_currency.get(gas_price[1], 0.0) + gas_rev
    return oil_by_currency, gas_by_currency


def _split_operating_costs(records: list[OperatingCost]) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    operating: dict[str, float] = {}
    energy: dict[str, float] = {}
    other: dict[str, float] = {}
    for r in records:
        operating[r.currency] = operating.get(r.currency, 0.0) + r.amount
        bucket = energy if r.category == "Energy" else other
        bucket[r.currency] = bucket.get(r.currency, 0.0) + r.amount
    return operating, energy, other


def _resolve_cost_field_id(cost: OperatingCost) -> int | None:
    if cost.field_id:
        return cost.field_id
    if cost.facility_id and cost.facility:
        return cost.facility.field_id
    if cost.well_id and cost.well:
        return cost.well.facility.field_id
    if cost.equipment_id and cost.equipment:
        field_id, _, _, _, _, _ = _resolve_scope(cost.equipment)
        return field_id
    return None


def _resolve_cost_well_id(cost: OperatingCost) -> int | None:
    if cost.well_id:
        return cost.well_id
    if cost.equipment_id and cost.equipment and cost.equipment.well_id:
        return cost.equipment.well_id
    return None


def _resolve_maintenance_field_id(record: MaintenanceRecord) -> int | None:
    field_id, _, _, _, _, _ = _resolve_scope(record.equipment)
    return field_id


def _resolve_maintenance_well_id(record: MaintenanceRecord) -> int | None:
    return record.equipment.well_id if record.equipment else None


def _production_query(db: Session, date_from: date, date_to: date, *, field_id=None, facility_id=None, well_id=None):
    query = db.query(ProductionRecord).filter(
        ProductionRecord.record_date >= date_from, ProductionRecord.record_date <= date_to
    )
    if well_id:
        query = query.filter(ProductionRecord.well_id == well_id)
    elif facility_id:
        query = query.filter(ProductionRecord.well.has(Well.facility_id == facility_id))
    elif field_id:
        query = query.filter(ProductionRecord.well.has(Well.facility.has(Facility.field_id == field_id)))
    return query


def _operating_cost_query(db: Session, date_from: date, date_to: date, *, field_id=None, facility_id=None, well_id=None):
    query = db.query(OperatingCost).options(
        joinedload(OperatingCost.facility),
        joinedload(OperatingCost.well).joinedload(Well.facility),
        joinedload(OperatingCost.equipment).joinedload(Equipment.well).joinedload(Well.facility),
        joinedload(OperatingCost.equipment).joinedload(Equipment.facility),
    ).filter(OperatingCost.cost_date >= date_from, OperatingCost.cost_date <= date_to)
    if well_id:
        query = query.filter(
            or_(OperatingCost.well_id == well_id, OperatingCost.equipment.has(Equipment.well_id == well_id))
        )
    elif facility_id:
        query = query.filter(
            or_(
                OperatingCost.facility_id == facility_id,
                OperatingCost.well.has(Well.facility_id == facility_id),
                OperatingCost.equipment.has(
                    or_(Equipment.facility_id == facility_id, Equipment.well.has(Well.facility_id == facility_id))
                ),
            )
        )
    elif field_id:
        query = query.filter(
            or_(
                OperatingCost.field_id == field_id,
                OperatingCost.facility.has(Facility.field_id == field_id),
                OperatingCost.well.has(Well.facility.has(Facility.field_id == field_id)),
                OperatingCost.equipment.has(
                    or_(
                        Equipment.facility.has(Facility.field_id == field_id),
                        Equipment.well.has(Well.facility.has(Facility.field_id == field_id)),
                    )
                ),
            )
        )
    return query


def _maintenance_cost_query(db: Session, date_from: date, date_to: date, *, field_id=None, facility_id=None, well_id=None, equipment_id=None):
    query = db.query(MaintenanceRecord).options(joinedload(MaintenanceRecord.equipment)).filter(
        MaintenanceRecord.start_date.isnot(None),
        MaintenanceRecord.start_date >= date_from,
        MaintenanceRecord.start_date <= date_to,
    )
    # equipment_id is the most specific scope this table can be filtered by — added for the
    # What-If Simulator's equipment-level baseline (maintenance cost is the one figure that
    # meaningfully scopes to a single piece of equipment); well/facility/field stay as the
    # existing broader fallbacks, unchanged for every pre-existing caller.
    if equipment_id:
        query = query.filter(MaintenanceRecord.equipment_id == equipment_id)
    elif well_id:
        query = query.filter(MaintenanceRecord.equipment.has(Equipment.well_id == well_id))
    elif facility_id:
        query = query.filter(
            MaintenanceRecord.equipment.has(
                or_(Equipment.facility_id == facility_id, Equipment.well.has(Well.facility_id == facility_id))
            )
        )
    elif field_id:
        query = query.filter(
            MaintenanceRecord.equipment.has(
                or_(
                    Equipment.facility.has(Facility.field_id == field_id),
                    Equipment.well.has(Well.facility.has(Facility.field_id == field_id)),
                )
            )
        )
    return query


def _production_loss_query(db: Session, date_from: date, date_to: date, *, field_id=None, facility_id=None, well_id=None):
    query = db.query(ProductionLoss).options(
        joinedload(ProductionLoss.well),
        joinedload(ProductionLoss.equipment).joinedload(Equipment.well).joinedload(Well.facility),
        joinedload(ProductionLoss.equipment).joinedload(Equipment.facility),
    ).filter(ProductionLoss.loss_date >= date_from, ProductionLoss.loss_date <= date_to)
    if well_id:
        query = query.filter(
            or_(ProductionLoss.well_id == well_id, ProductionLoss.equipment.has(Equipment.well_id == well_id))
        )
    elif facility_id:
        query = query.filter(
            or_(
                ProductionLoss.well.has(Well.facility_id == facility_id),
                ProductionLoss.equipment.has(
                    or_(Equipment.facility_id == facility_id, Equipment.well.has(Well.facility_id == facility_id))
                ),
            )
        )
    elif field_id:
        query = query.filter(
            or_(
                ProductionLoss.well.has(Well.facility.has(Facility.field_id == field_id)),
                ProductionLoss.equipment.has(
                    or_(
                        Equipment.facility.has(Facility.field_id == field_id),
                        Equipment.well.has(Well.facility.has(Facility.field_id == field_id)),
                    )
                ),
            )
        )
    return query


def _latest_period(db: Session) -> tuple[date, date]:
    latest = db.query(func.max(ProductionRecord.record_date)).scalar() or date.today()
    return latest.replace(day=1), latest


def _build_economics_section(
    revenue_total: dict[str, float], cost_total: dict[str, float], oil_total: float, gas_total: float, boe_total: float
) -> EconomicsSection:
    margin_dict, mismatch = _margin_by_currency(revenue_total, cost_total)
    return EconomicsSection(
        margin=_money_list(margin_dict),
        cost_per_bbl=_money_list(_per_unit_by_currency(cost_total, oil_total)),
        cost_per_boe=_money_list(_per_unit_by_currency(cost_total, boe_total)),
        revenue_per_bbl=_money_list(_per_unit_by_currency(revenue_total, oil_total)),
        revenue_per_boe=_money_list(_per_unit_by_currency(revenue_total, boe_total)),
        currency_mismatch=mismatch,
    )


def _compute_scope_totals(
    db: Session,
    period_start: date,
    period_end: date,
    price_series,
    boe_gas_factor,
    *,
    field_id=None,
    facility_id=None,
    well_id=None,
    equipment_id=None,
):
    records = _production_query(
        db, period_start, period_end, field_id=field_id, facility_id=facility_id, well_id=well_id
    ).all()
    oil_total = sum(r.oil_bopd for r in records)
    gas_total = sum(r.gas_mscfd for r in records)
    boe_total = compute_boe(oil_total, gas_total, boe_gas_factor)
    oil_rev, gas_rev = _revenue_dicts_for_records(records, price_series)
    revenue_total = _combine_money(oil_rev, gas_rev)

    costs = _operating_cost_query(
        db, period_start, period_end, field_id=field_id, facility_id=facility_id, well_id=well_id
    ).all()
    operating_dict, energy_dict, other_dict = _split_operating_costs(costs)

    maintenance_records = _maintenance_cost_query(
        db,
        period_start,
        period_end,
        field_id=field_id,
        facility_id=facility_id,
        well_id=well_id,
        equipment_id=equipment_id,
    ).all()
    maintenance_total = round(sum(r.cost or 0 for r in maintenance_records), 2)

    losses = _production_loss_query(
        db, period_start, period_end, field_id=field_id, facility_id=facility_id, well_id=well_id
    ).all()
    loss_revenue_dict: dict[str, float] = {}
    downtime_hours_total = 0.0
    lost_oil_total = 0.0
    lost_gas_total = 0.0
    for loss in losses:
        if loss.estimated_revenue_impact is not None and loss.currency:
            loss_revenue_dict[loss.currency] = loss_revenue_dict.get(loss.currency, 0.0) + loss.estimated_revenue_impact
        if loss.downtime_hours:
            downtime_hours_total += loss.downtime_hours
        if loss.estimated_bopd_lost:
            lost_oil_total += loss.estimated_bopd_lost
        if loss.estimated_mscf_lost:
            lost_gas_total += loss.estimated_mscf_lost

    return {
        "oil_total": oil_total,
        "gas_total": gas_total,
        "boe_total": boe_total,
        "revenue_total": revenue_total,
        "oil_revenue_dict": oil_rev,
        "gas_revenue_dict": gas_rev,
        "operating_dict": operating_dict,
        "energy_dict": energy_dict,
        "other_dict": other_dict,
        "maintenance_total": maintenance_total,
        "loss_revenue_dict": loss_revenue_dict,
        "downtime_hours_total": round(downtime_hours_total, 2),
        "lost_oil_total": round(lost_oil_total, 1),
        "lost_gas_total": round(lost_gas_total, 1),
    }


# ----- Dashboard -----


@router.get("/dashboard", response_model=CostRevenueDashboardResponse)
def get_cost_revenue_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CostRevenueDashboardResponse:
    period_start, period_end = _latest_period(db)
    boe_gas_factor = get_boe_gas_factor(db)
    price_series = _load_price_series(db)

    records = _production_query(db, period_start, period_end).all()
    oil_total = sum(r.oil_bopd for r in records)
    gas_total = sum(r.gas_mscfd for r in records)
    boe_total = compute_boe(oil_total, gas_total, boe_gas_factor)
    oil_rev, gas_rev = _revenue_dicts_for_records(records, price_series)
    revenue_total = _combine_money(oil_rev, gas_rev)

    costs = _operating_cost_query(db, period_start, period_end).all()
    operating_dict, energy_dict, other_dict = _split_operating_costs(costs)

    maintenance_records = _maintenance_cost_query(db, period_start, period_end).all()
    maintenance_total = round(sum(r.cost or 0 for r in maintenance_records), 2)
    maintenance_dict = {MAINTENANCE_COST_CURRENCY: maintenance_total} if maintenance_total else {}

    total_cost_dict = _combine_money(operating_dict, maintenance_dict)

    losses = _production_loss_query(db, period_start, period_end).all()
    lost_oil = round(sum(loss.estimated_bopd_lost or 0 for loss in losses), 1)
    lost_gas = round(sum(loss.estimated_mscf_lost or 0 for loss in losses), 2)
    downtime_total = round(sum(loss.downtime_hours or 0 for loss in losses), 1)
    loss_revenue_dict: dict[str, float] = {}
    for loss in losses:
        if loss.estimated_revenue_impact is not None and loss.currency:
            loss_revenue_dict[loss.currency] = loss_revenue_dict.get(loss.currency, 0.0) + loss.estimated_revenue_impact

    return CostRevenueDashboardResponse(
        period_start=period_start,
        period_end=period_end,
        production=ProductionTotals(oil_bbl=round(oil_total, 1), gas_mscf=round(gas_total, 2), boe=round(boe_total, 1)),
        revenue=RevenueSection(oil=_money_list(oil_rev), gas=_money_list(gas_rev), total=_money_list(revenue_total)),
        costs=CostSection(
            operating=_money_list(operating_dict),
            maintenance=_money_list(maintenance_dict),
            energy=_money_list(energy_dict),
            other=_money_list(other_dict),
            total=_money_list(total_cost_dict),
        ),
        economics=_build_economics_section(revenue_total, total_cost_dict, oil_total, gas_total, boe_total),
        production_loss=ProductionLossSection(
            estimated_lost_oil_bbl=lost_oil,
            estimated_lost_gas_mscf=lost_gas,
            estimated_lost_revenue=_money_list(loss_revenue_dict),
            downtime_hours=downtime_total,
        ),
        disclaimer_text=ECONOMICS_DISCLAIMER,
    )


# ----- Unit economics -----


@router.get("/unit-economics", response_model=UnitEconomicsResponse)
def get_unit_economics(
    field_id: int | None = None,
    facility_id: int | None = None,
    well_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnitEconomicsResponse:
    if date_from is None or date_to is None:
        default_start, default_end = _latest_period(db)
        date_from = date_from or default_start
        date_to = date_to or default_end

    boe_gas_factor = get_boe_gas_factor(db)
    price_series = _load_price_series(db)

    records = _production_query(db, date_from, date_to, field_id=field_id, facility_id=facility_id, well_id=well_id).all()
    oil_total = sum(r.oil_bopd for r in records)
    gas_total = sum(r.gas_mscfd for r in records)
    boe_total = compute_boe(oil_total, gas_total, boe_gas_factor)
    oil_rev, gas_rev = _revenue_dicts_for_records(records, price_series)
    revenue_total = _combine_money(oil_rev, gas_rev)

    costs = _operating_cost_query(db, date_from, date_to, field_id=field_id, facility_id=facility_id, well_id=well_id).all()
    operating_dict, energy_dict, other_dict = _split_operating_costs(costs)

    maintenance_records = _maintenance_cost_query(db, date_from, date_to, field_id=field_id, well_id=well_id).all()
    maintenance_total = round(sum(r.cost or 0 for r in maintenance_records), 2)
    maintenance_dict = {MAINTENANCE_COST_CURRENCY: maintenance_total} if maintenance_total else {}
    total_cost_dict = _combine_money(operating_dict, maintenance_dict)

    return UnitEconomicsResponse(
        period_start=date_from,
        period_end=date_to,
        production=ProductionTotals(oil_bbl=round(oil_total, 1), gas_mscf=round(gas_total, 2), boe=round(boe_total, 1)),
        revenue=RevenueSection(oil=_money_list(oil_rev), gas=_money_list(gas_rev), total=_money_list(revenue_total)),
        costs=CostSection(
            operating=_money_list(operating_dict),
            maintenance=_money_list(maintenance_dict),
            energy=_money_list(energy_dict),
            other=_money_list(other_dict),
            total=_money_list(total_cost_dict),
        ),
        economics=_build_economics_section(revenue_total, total_cost_dict, oil_total, gas_total, boe_total),
        disclaimer_text=ECONOMICS_DISCLAIMER,
    )


# ----- Field / Well economics -----


@router.get("/economics-by-scope", response_model=EconomicsByScopeResponse)
def get_economics_by_scope(
    scope: str = Query("field", pattern="^(field|well)$"),
    rank_by: str = Query("production", pattern="^(production|revenue|cost_efficiency|margin)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EconomicsByScopeResponse:
    period_start, period_end = _latest_period(db)
    boe_gas_factor = get_boe_gas_factor(db)
    price_series = _load_price_series(db)

    entities: list[tuple[str, str, dict]] = []
    if scope == "field":
        for field in db.query(Field).order_by(Field.name).all():
            totals = _compute_scope_totals(db, period_start, period_end, price_series, boe_gas_factor, field_id=field.id)
            entities.append((str(field.id), field.name, totals))
    else:
        for well in db.query(Well).order_by(Well.well_id).all():
            totals = _compute_scope_totals(db, period_start, period_end, price_series, boe_gas_factor, well_id=well.id)
            entities.append((str(well.id), well.well_id, totals))

    # Company-wide, per-currency averages (only over entities that actually produced this
    # period) — classification always compares like-currency to like-currency, never mixed.
    oil_values = [t["oil_total"] for _, _, t in entities if t["oil_total"] > 0]
    avg_oil = sum(oil_values) / len(oil_values) if oil_values else 0.0

    cost_per_bbl_by_currency: dict[str, list[float]] = {}
    margin_by_currency_samples: dict[str, list[float]] = {}
    for _, _, t in entities:
        total_cost = _combine_money(t["operating_dict"], {MAINTENANCE_COST_CURRENCY: t["maintenance_total"]} if t["maintenance_total"] else {})
        for currency, value in _per_unit_by_currency(total_cost, t["oil_total"]).items():
            cost_per_bbl_by_currency.setdefault(currency, []).append(value)
        margin_dict, _ = _margin_by_currency(t["revenue_total"], total_cost)
        for currency, value in margin_dict.items():
            margin_by_currency_samples.setdefault(currency, []).append(value)

    avg_cost_per_bbl = {c: sum(v) / len(v) for c, v in cost_per_bbl_by_currency.items() if v}
    avg_margin = {c: sum(v) / len(v) for c, v in margin_by_currency_samples.items() if v}

    rows: list[EconomicsScopeRow] = []
    for key, label, t in entities:
        total_cost = _combine_money(
            t["operating_dict"], {MAINTENANCE_COST_CURRENCY: t["maintenance_total"]} if t["maintenance_total"] else {}
        )
        margin_dict, currency_mismatch = _margin_by_currency(t["revenue_total"], total_cost)
        cost_per_bbl_dict = _per_unit_by_currency(total_cost, t["oil_total"])
        revenue_per_bbl_dict = _per_unit_by_currency(t["revenue_total"], t["oil_total"])

        has_data = t["oil_total"] > 0 or t["gas_total"] > 0
        high_production = high_cost = low_margin = high_loss = None
        review_note = None

        if scope == "well":
            if not has_data:
                review_note = "Requires further economic review — no production recorded this period."
            else:
                high_production = avg_oil > 0 and t["oil_total"] > avg_oil * 1.5
                high_cost = any(
                    value > avg_cost_per_bbl.get(currency, value) * 1.5
                    for currency, value in cost_per_bbl_dict.items()
                    if avg_cost_per_bbl.get(currency)
                )
                low_margin = any(
                    value < avg_margin.get(currency, value) * 0.5
                    for currency, value in margin_dict.items()
                    if avg_margin.get(currency) and avg_margin[currency] > 0
                ) or any(value < 0 for value in margin_dict.values())
                high_loss = bool(t["loss_revenue_dict"]) and sum(t["loss_revenue_dict"].values()) > 0
                if not cost_per_bbl_dict and not margin_dict:
                    review_note = "Requires further economic review — insufficient cost or price data to compute margin."

        if review_note is None and currency_mismatch:
            review_note = (
                "Requires further economic review — costs span more than one currency; margin and "
                "cost-per-barrel reflect only the currency that matches revenue, not the full cost."
            )

        rows.append(
            EconomicsScopeRow(
                scope=scope,
                key=key,
                label=label,
                oil_bbl=round(t["oil_total"], 1),
                gas_mscf=round(t["gas_total"], 2),
                boe=round(t["boe_total"], 1),
                revenue=_money_list(t["revenue_total"]),
                operating_cost=_money_list(t["operating_dict"]),
                maintenance_cost=t["maintenance_total"],
                production_loss_revenue=_money_list(t["loss_revenue_dict"]),
                margin=_money_list(margin_dict),
                cost_per_bbl=_money_list(cost_per_bbl_dict),
                revenue_per_bbl=_money_list(revenue_per_bbl_dict),
                currency_mismatch=currency_mismatch,
                high_production=high_production,
                high_cost=high_cost,
                low_margin=low_margin,
                high_loss=high_loss,
                review_note=review_note,
            )
        )

    def _rank_key(row: EconomicsScopeRow) -> float:
        if rank_by == "revenue":
            return sum(m.amount for m in row.revenue)
        if rank_by == "cost_efficiency":
            # Lower cost/bbl is "more efficient" — rank ascending by negating for reverse=True.
            values = [m.amount for m in row.cost_per_bbl]
            return -min(values) if values else float("-inf")
        if rank_by == "margin":
            return sum(m.amount for m in row.margin)
        return row.oil_bbl

    rows.sort(key=_rank_key, reverse=True)

    return EconomicsByScopeResponse(scope=scope, rank_by=rank_by, rows=rows, disclaimer_text=ECONOMICS_DISCLAIMER)


# ----- Trends -----


@router.get("/revenue-trend", response_model=RevenueTrendResponse)
def get_revenue_trend(
    field_id: int | None = None,
    facility_id: int | None = None,
    well_id: int | None = None,
    commodity: str | None = Query(None, pattern="^(oil|gas)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RevenueTrendResponse:
    records = _production_query(
        db, date(2000, 1, 1), date(2100, 1, 1), field_id=field_id, facility_id=facility_id, well_id=well_id
    ).all()
    price_series = _load_price_series(db)

    buckets: dict[str, dict] = {}
    for r in records:
        month_key = r.record_date.strftime("%Y-%m")
        bucket = buckets.setdefault(month_key, {"oil": {}, "gas": {}, "oil_bbl": 0.0})
        oil_price = _price_on(price_series.get("oil", []), r.record_date)
        gas_price = _price_on(price_series.get("gas", []), r.record_date)
        oil_rev, gas_rev, _ = estimate_revenue(
            r.oil_bopd, r.gas_mscfd, oil_price[0] if oil_price else None, gas_price[0] if gas_price else None
        )
        if oil_rev is not None and commodity in (None, "oil"):
            bucket["oil"][oil_price[1]] = bucket["oil"].get(oil_price[1], 0.0) + oil_rev
        if gas_rev is not None and commodity in (None, "gas"):
            bucket["gas"][gas_price[1]] = bucket["gas"].get(gas_price[1], 0.0) + gas_rev
        bucket["oil_bbl"] += r.oil_bopd

    points = []
    for month, b in sorted(buckets.items()):
        total = _combine_money(b["oil"], b["gas"])
        points.append(
            RevenueTrendPoint(
                month=month,
                oil_revenue=_money_list(b["oil"]),
                gas_revenue=_money_list(b["gas"]),
                total_revenue=_money_list(total),
                revenue_per_bbl=_money_list(_per_unit_by_currency(total, b["oil_bbl"])),
            )
        )
    return RevenueTrendResponse(points=points)


@router.get("/cost-trend", response_model=CostTrendResponse)
def get_cost_trend(
    field_id: int | None = None,
    facility_id: int | None = None,
    well_id: int | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CostTrendResponse:
    costs = _operating_cost_query(
        db, date(2000, 1, 1), date(2100, 1, 1), field_id=field_id, facility_id=facility_id, well_id=well_id
    ).all()
    if category:
        costs = [c for c in costs if c.category == category]

    production_records = _production_query(
        db, date(2000, 1, 1), date(2100, 1, 1), field_id=field_id, facility_id=facility_id, well_id=well_id
    ).all()
    oil_by_month: dict[str, float] = {}
    for r in production_records:
        month_key = r.record_date.strftime("%Y-%m")
        oil_by_month[month_key] = oil_by_month.get(month_key, 0.0) + r.oil_bopd

    buckets: dict[str, dict[str, float]] = {}
    for c in costs:
        month_key = c.cost_date.strftime("%Y-%m")
        bucket = buckets.setdefault(month_key, {})
        bucket[c.currency] = bucket.get(c.currency, 0.0) + c.amount

    points = [
        CostTrendPoint(
            month=month,
            total_cost=_money_list(amounts),
            cost_per_bbl=_money_list(_per_unit_by_currency(amounts, oil_by_month.get(month))),
        )
        for month, amounts in sorted(buckets.items())
    ]
    return CostTrendResponse(points=points)


@router.get("/margin-trend", response_model=MarginTrendResponse)
def get_margin_trend(
    field_id: int | None = None,
    facility_id: int | None = None,
    well_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MarginTrendResponse:
    price_series = _load_price_series(db)
    records = _production_query(
        db, date(2000, 1, 1), date(2100, 1, 1), field_id=field_id, facility_id=facility_id, well_id=well_id
    ).all()
    revenue_by_month: dict[str, dict[str, float]] = {}
    for r in records:
        month_key = r.record_date.strftime("%Y-%m")
        oil_price = _price_on(price_series.get("oil", []), r.record_date)
        gas_price = _price_on(price_series.get("gas", []), r.record_date)
        oil_rev, gas_rev, _ = estimate_revenue(
            r.oil_bopd, r.gas_mscfd, oil_price[0] if oil_price else None, gas_price[0] if gas_price else None
        )
        bucket = revenue_by_month.setdefault(month_key, {})
        if oil_rev is not None:
            bucket[oil_price[1]] = bucket.get(oil_price[1], 0.0) + oil_rev
        if gas_rev is not None:
            bucket[gas_price[1]] = bucket.get(gas_price[1], 0.0) + gas_rev

    costs = _operating_cost_query(
        db, date(2000, 1, 1), date(2100, 1, 1), field_id=field_id, facility_id=facility_id, well_id=well_id
    ).all()
    cost_by_month: dict[str, dict[str, float]] = {}
    for c in costs:
        month_key = c.cost_date.strftime("%Y-%m")
        bucket = cost_by_month.setdefault(month_key, {})
        bucket[c.currency] = bucket.get(c.currency, 0.0) + c.amount

    months = sorted(set(revenue_by_month.keys()) | set(cost_by_month.keys()))
    points = []
    for month in months:
        margin_dict, _ = _margin_by_currency(revenue_by_month.get(month, {}), cost_by_month.get(month, {}))
        points.append(MarginTrendPoint(month=month, margin=_money_list(margin_dict)))
    return MarginTrendResponse(points=points)


# ----- Alerts -----


@router.get("/alerts", response_model=CostAlertsResponse)
def get_cost_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CostAlertsResponse:
    this_start, this_end = _latest_period(db)
    prev_end = this_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)

    alerts: list[CostAlert] = []

    # 1. Rapid cost increase — per field, per currency, month-over-month.
    for field in db.query(Field).all():
        this_costs = _operating_cost_query(db, this_start, this_end, field_id=field.id).all()
        prev_costs = _operating_cost_query(db, prev_start, prev_end, field_id=field.id).all()
        this_dict, _, _ = _split_operating_costs(this_costs)
        prev_dict, _, _ = _split_operating_costs(prev_costs)
        for currency, this_amount in this_dict.items():
            prev_amount = prev_dict.get(currency)
            if prev_amount and this_amount > prev_amount * 1.25:
                pct = (this_amount - prev_amount) / prev_amount * 100
                alerts.append(
                    CostAlert(
                        severity="warning",
                        category="rapid_cost_increase",
                        scope_label=field.name,
                        message=f"Operating cost up {pct:.0f}% month-over-month",
                        detail=f"{currency} {prev_amount:,.0f} -> {currency} {this_amount:,.0f}",
                    )
                )

    # 2. High maintenance cost — per equipment, trailing 90 days vs. fleet average.
    window_start = this_end - timedelta(days=90)
    maintenance_records = (
        db.query(MaintenanceRecord)
        .options(joinedload(MaintenanceRecord.equipment))
        .filter(MaintenanceRecord.start_date.isnot(None), MaintenanceRecord.start_date >= window_start)
        .all()
    )
    cost_by_equipment: dict[int, float] = {}
    tag_by_equipment: dict[int, str] = {}
    for r in maintenance_records:
        if r.equipment is None:
            continue
        cost_by_equipment[r.equipment_id] = cost_by_equipment.get(r.equipment_id, 0.0) + (r.cost or 0)
        tag_by_equipment[r.equipment_id] = r.equipment.equipment_tag
    if cost_by_equipment:
        fleet_avg = sum(cost_by_equipment.values()) / len(cost_by_equipment)
        for equipment_id, total in cost_by_equipment.items():
            if fleet_avg > 0 and total > fleet_avg * 2:
                alerts.append(
                    CostAlert(
                        severity="warning",
                        category="high_maintenance_cost",
                        scope_label=tag_by_equipment[equipment_id],
                        message="Maintenance cost more than 2x the fleet average (trailing 90 days)",
                        detail=f"${total:,.0f} vs. fleet average ${fleet_avg:,.0f}",
                    )
                )

    # 3. High cost per barrel — per field vs. company-wide average, currency-matched.
    boe_gas_factor = get_boe_gas_factor(db)
    price_series = _load_price_series(db)
    field_cost_per_bbl: dict[int, dict[str, float]] = {}
    field_names: dict[int, str] = {}
    for field in db.query(Field).all():
        field_names[field.id] = field.name
        totals = _compute_scope_totals(db, this_start, this_end, price_series, boe_gas_factor, field_id=field.id)
        total_cost = _combine_money(
            totals["operating_dict"],
            {MAINTENANCE_COST_CURRENCY: totals["maintenance_total"]} if totals["maintenance_total"] else {},
        )
        field_cost_per_bbl[field.id] = _per_unit_by_currency(total_cost, totals["oil_total"])
    for currency in {c for d in field_cost_per_bbl.values() for c in d}:
        values = [d[currency] for d in field_cost_per_bbl.values() if currency in d]
        if not values:
            continue
        avg = sum(values) / len(values)
        for field_id, d in field_cost_per_bbl.items():
            if currency in d and avg > 0 and d[currency] > avg * 1.5:
                alerts.append(
                    CostAlert(
                        severity="warning",
                        category="high_cost_per_barrel",
                        scope_label=field_names[field_id],
                        message="Cost per barrel more than 1.5x the company-wide average",
                        detail=f"{currency} {d[currency]:,.2f}/bbl vs. average {currency} {avg:,.2f}/bbl",
                    )
                )

    # 4. High production loss — per well, lost oil vs. that well's actual oil this period.
    losses = _production_loss_query(db, this_start, this_end).all()
    lost_oil_by_well: dict[int, float] = {}
    for loss in losses:
        if loss.well_id and loss.estimated_bopd_lost:
            lost_oil_by_well[loss.well_id] = lost_oil_by_well.get(loss.well_id, 0.0) + loss.estimated_bopd_lost
    for well_id, lost_oil in lost_oil_by_well.items():
        well = db.get(Well, well_id)
        if well is None:
            continue
        actual_records = _production_query(db, this_start, this_end, well_id=well_id).all()
        actual_oil = sum(r.oil_bopd for r in actual_records)
        if actual_oil > 0 and lost_oil > actual_oil * 0.15:
            alerts.append(
                CostAlert(
                    severity="critical",
                    category="high_production_loss",
                    scope_label=well.well_id,
                    message="Estimated lost oil exceeds 15% of this well's actual production this period",
                    detail=f"{lost_oil:,.1f} bbl lost vs. {actual_oil:,.1f} bbl actual",
                )
            )

    # 5. Declining margin — per field, month-over-month, currency-matched only.
    for field in db.query(Field).all():
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
        this_margin, _ = _margin_by_currency(this_totals["revenue_total"], this_cost)
        prev_margin, _ = _margin_by_currency(prev_totals["revenue_total"], prev_cost)
        for currency, this_value in this_margin.items():
            prev_value = prev_margin.get(currency)
            if prev_value and prev_value > 0 and this_value < prev_value * 0.75:
                pct = (prev_value - this_value) / prev_value * 100
                alerts.append(
                    CostAlert(
                        severity="warning",
                        category="declining_margin",
                        scope_label=field.name,
                        message=f"Estimated operating margin down {pct:.0f}% month-over-month",
                        detail=f"{currency} {prev_value:,.0f} -> {currency} {this_value:,.0f}",
                    )
                )

    # 6. Unusually high energy cost — per facility, this month vs. its own trailing 6-month average.
    trailing_start = (this_start - timedelta(days=180)).replace(day=1)
    for facility in db.query(Facility).all():
        this_costs = _operating_cost_query(db, this_start, this_end, facility_id=facility.id).all()
        this_energy = sum(c.amount for c in this_costs if c.category == "Energy")
        trailing_costs = _operating_cost_query(db, trailing_start, prev_end, facility_id=facility.id).all()
        trailing_energy = [c.amount for c in trailing_costs if c.category == "Energy"]
        if trailing_energy:
            avg = sum(trailing_energy) / len(trailing_energy)
            if avg > 0 and this_energy > avg * 2:
                alerts.append(
                    CostAlert(
                        severity="info",
                        category="unusually_high_energy_cost",
                        scope_label=facility.name,
                        message="Energy cost more than 2x this facility's own trailing average",
                        detail=f"${this_energy:,.0f} this month vs. trailing average ${avg:,.0f}",
                    )
                )

    return CostAlertsResponse(alerts=alerts, disclaimer_text=ECONOMICS_DISCLAIMER)
