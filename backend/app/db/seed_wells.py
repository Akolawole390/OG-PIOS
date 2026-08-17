"""Synthetic demo data for the Wells, Production, Equipment, Maintenance, Production Loss,
Cost & Revenue, Alerts, and AI Insights modules: fields, facilities, wells, 365 days of daily
production/pressure/temperature history, production targets, downtime events, well- and
facility-level equipment with sensor readings, maintenance work orders (technicians, cost
breakdown, scheduling, failure/corrective-action detail) across preventive/corrective/
emergency/inspection/calibration/routine/predictive types, commodity prices, production-loss
records tied to real synthetic incidents, operating cost records spanning all 11 cost
categories with a deliberate USD/NGN currency split by field, and finally a real run of both the
Alerts module's rule engine and the AI Insights module's evidence-based insight engine against
all of the above (never a disconnected, independently invented alert or insight).

Run after `python -m app.db.seed` (roles + demo admin) and after migrations are applied:
    docker compose exec backend python -m app.db.seed_wells

Additive and idempotent (skips if data already exists) — does not touch app/db/seed.py.
Uses stdlib random/datetime only, per this module's minimal-dependency scope. This is a
scoped implementation of the fuller synthetic generator originally planned in
scripts/seed/README.md.

ALL data in this module is synthetic/demo data for development and testing — never real
operational data, per this project's data-handling rule (see root CLAUDE.md).

A few wells are seeded with a deliberately sharper production/pressure/water-cut decline and
a guaranteed downtime event in the final two weeks of the window — this is a synthetic *data
pattern* only, to give a future anomaly-detection module something real to find. No detection
logic is implemented here.
"""

import random
from datetime import date, datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.economics import CommodityPrice, OperatingCost, ProductionLoss
from app.models.equipment import DowntimeEvent, Equipment, EquipmentReading, MaintenanceRecord
from app.models.field import Facility, Field, Well
from app.services.alert_rules import run_alert_rules
from app.services.insight_engine import run_insight_engine
from app.models.production import (
    PressureRecord,
    ProductionRecord,
    ProductionTarget,
    TemperatureRecord,
)
from app.models.role import Role
from app.models.user import User
from app.routers.production_loss import _compute_derived_fields
from app.services.equipment_health import DEFAULT_OPERATING_HOURS_THRESHOLD, HealthInputs, compute_health

random.seed(42)

PRODUCTION_DAYS = 365
READING_DAYS = 90
WELLS_TOTAL = 25
FACILITIES_PER_FIELD = (2, 3)

FIELD_DEFS = [
    {"name": "Niger Delta Field", "country": "Nigeria", "code": "NDF", "base_lat": 4.8, "base_lon": 6.3},
    {"name": "Permian Basin Field", "country": "United States", "code": "PBF", "base_lat": 31.9, "base_lon": -102.3},
    {"name": "North Sea Field", "country": "United Kingdom", "code": "NSF", "base_lat": 58.4, "base_lon": 1.9},
]

FACILITY_KINDS = ["Flow Station", "Gathering Manifold", "Platform"]
FACILITY_TYPES = ["flow_station", "manifold", "platform"]
WELL_TYPES = ["oil_producer", "gas_producer", "water_injector"]
LIFT_TYPES = ["ESP", "gas_lift", "rod_pump", "natural_flow", None]
COMPLETION_TYPES = ["cased_hole", "open_hole", "gravel_pack"]
EQUIPMENT_MANUFACTURERS = ["Baker Hughes", "Schlumberger", "Halliburton", "Weatherford"]
DOWNTIME_REASONS = [
    "scheduled workover",
    "ESP failure",
    "pipeline tie-in",
    "flowline leak",
    "reservoir shut-in",
    "wellhead repair",
]

FACILITY_EQUIPMENT_TYPES = [
    "compressor",
    "generator",
    "separator",
    "heat_exchanger",
    "valve",
    "instrumentation",
]
FACILITY_EQUIPMENT_WEIGHTS = {
    "flow_station": [30, 10, 25, 15, 15, 5],
    "manifold": [10, 5, 10, 5, 40, 30],
    "platform": [25, 20, 20, 20, 10, 5],
}
READING_PARAMETERS_BY_TYPE = {
    "ESP": ["temperature", "vibration", "current"],
    "gas_lift": ["temperature", "flow"],
    "rod_pump": ["temperature", "vibration", "current"],
    "compressor": ["temperature", "vibration", "current", "flow"],
    "generator": ["temperature", "vibration", "current"],
    "separator": ["temperature", "flow"],
    "heat_exchanger": ["temperature", "flow"],
    "valve": ["flow"],
    "instrumentation": [],
}
READING_BASELINE_RANGES = {
    # parameter: (low, high, unit)
    "temperature": (150.0, 220.0, "°F"),
    "vibration": (0.1, 0.4, "in/s"),
    "current": (20.0, 80.0, "A"),
    "flow": (100.0, 2000.0, "bbl/d"),
}
PROBLEM_PATTERNS = [
    "increasing_temperature",
    "increasing_vibration",
    "excessive_operating_hours",
    "repeated_maintenance",
    "failure_event",
]

# ----- Maintenance module (work orders, technicians, cost/downtime detail) -----

TECHNICIAN_NAMES = [
    "Demo Technician — Ada Chukwu",
    "Demo Technician — Sam Whitfield",
    "Demo Technician — Priya Nair",
]

# Routine-mix types (a genuine "emergency" work order is only ever created by the
# failure_event problem pattern below, since it should always accompany a real failure).
ROUTINE_MAINTENANCE_TYPES = ["preventive", "corrective", "inspection", "calibration", "routine", "predictive"]
ROUTINE_MAINTENANCE_WEIGHTS = [35, 25, 12, 8, 10, 10]

# Health-affecting maintenance types — kept in sync with services/equipment_health.py's
# recompute_equipment_health(), which counts these same two types toward the
# maintenance_history factor.
DISRUPTIVE_MAINTENANCE_TYPES = ("corrective", "emergency")

FAILURE_CAUSES = [
    "Excessive vibration due to bearing wear",
    "Overheating from restricted flow",
    "Electrical fault in control panel",
    "Seal failure causing fluid leak",
    "Corrosion-related component degradation",
    "Sand ingress damaging internal components",
]
CORRECTIVE_ACTIONS = [
    "Replaced worn bearing assembly",
    "Cleared flow restriction and inspected cooling system",
    "Repaired electrical connection and tested control panel",
    "Replaced seal and refilled fluid",
    "Treated corrosion and applied protective coating",
    "Installed sand screen and flushed system",
]


def _priority_for_type(maintenance_type: str) -> str:
    if maintenance_type == "emergency":
        return "critical"
    if maintenance_type == "corrective":
        return random.choices(["high", "medium"], weights=[70, 30])[0]
    if maintenance_type == "preventive":
        return random.choices(["low", "medium"], weights=[70, 30])[0]
    return random.choices(["medium", "low"], weights=[50, 50])[0]


def _sum_costs(*values: float | None) -> float | None:
    if all(v is None for v in values):
        return None
    return round(sum(v or 0 for v in values), 2)


def _seed_technicians(db) -> list[User]:
    """A handful of demo Maintenance Engineer users to assign as technicians — additive to
    this seed script (not app/db/seed.py, which stays reserved for roles + the one demo
    admin). Idempotent by email. Returns [] (technician_id stays unassigned) if the
    Maintenance Engineer role hasn't been seeded yet, rather than crashing."""
    role = db.query(Role).filter(Role.name == "Maintenance Engineer").first()
    if role is None:
        return []

    technicians = []
    for index, name in enumerate(TECHNICIAN_NAMES, start=1):
        email = f"demo-technician-{index}@ogpios.dev"
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                email=email,
                full_name=name,
                hashed_password=hash_password("ChangeMe123!"),
                role_id=role.id,
            )
            db.add(user)
            db.flush()
        technicians.append(user)
    return technicians


# ----- Production Loss module (commodity prices, loss records) -----

COMMODITY_PRICE_RANGES = {
    "oil": (65.0, 85.0),  # USD/bbl
    "gas": (2.50, 4.00),  # USD/mscf
}
LOSS_CATEGORIES_GENERAL = ["weather", "operational", "reservoir", "scheduled_maintenance"]


def _seed_commodity_prices(db, today: date) -> int:
    """Monthly synthetic oil/gas price points across the production window — CommodityPrice
    is otherwise unused, so this is purely additive demo data, not app config."""
    count = 0
    for commodity, (low, high) in COMMODITY_PRICE_RANGES.items():
        for months_ago in range(12, -1, -1):
            db.add(
                CommodityPrice(
                    effective_date=today - timedelta(days=months_ago * 30),
                    commodity=commodity,
                    price=round(random.uniform(low, high), 2),
                    currency="USD",
                )
            )
            count += 1
    return count


# ----- Cost & Revenue module (operating costs) -----

# Currency split by field — the actual thing that exercises the Cost & Revenue module's
# "never blend currencies" guardrail in the demo, not a hypothetical. Chosen independently per
# field/currency below; NGN amounts are plausible standalone figures, never derived from the
# USD ranges via any coded exchange rate ("do not invent exchange rates").
FIELD_CURRENCY = {"NDF": "NGN", "PBF": "USD", "NSF": "USD"}

OPERATING_COST_RANGES_USD = {
    "Production": (8000.0, 25000.0),
    "Maintenance": (5000.0, 20000.0),
    "Energy": (6000.0, 30000.0),
    "Chemicals": (2000.0, 10000.0),
    "Labour": (20000.0, 60000.0),
    "Contractor": (8000.0, 40000.0),
    "Logistics": (3000.0, 15000.0),
    "Utilities": (1500.0, 8000.0),
    "Facility": (4000.0, 18000.0),
    "Equipment": (3000.0, 15000.0),
    "Other": (500.0, 5000.0),
}
OPERATING_COST_RANGES_NGN = {
    "Production": (9_000_000.0, 30_000_000.0),
    "Maintenance": (6_000_000.0, 22_000_000.0),
    "Energy": (7_000_000.0, 35_000_000.0),
    "Chemicals": (2_500_000.0, 12_000_000.0),
    "Labour": (25_000_000.0, 70_000_000.0),
    "Contractor": (9_000_000.0, 45_000_000.0),
    "Logistics": (3_500_000.0, 18_000_000.0),
    "Utilities": (1_800_000.0, 9_000_000.0),
    "Facility": (4_500_000.0, 20_000_000.0),
    "Equipment": (3_500_000.0, 17_000_000.0),
    "Other": (600_000.0, 6_000_000.0),
}
COST_SOURCES = ["invoice", "estimate", "manual_entry"]


def _jitter(base: float, spread: float) -> float:
    return round(base + random.uniform(-spread, spread), 4)


def _generate_readings_for_equipment(
    db, equipment: Equipment, parameters: list[str], problem_pattern: str | None
) -> dict[str, list[float]]:
    """READING_DAYS of daily readings per parameter. Returns {parameter: [values, oldest
    first]} for immediate reuse in the health-score computation below — avoids a second DB
    round-trip for data generated in this same transaction."""
    series_by_param: dict[str, list[float]] = {}
    for parameter in parameters:
        low, high, unit = READING_BASELINE_RANGES[parameter]
        baseline = random.uniform(low, high)
        values: list[float] = []
        for day_index in range(READING_DAYS, -1, -1):
            reading_at = datetime.now(timezone.utc) - timedelta(days=day_index)
            noise = random.uniform(0.95, 1.05)
            trend_factor = 1.0
            if problem_pattern == "increasing_temperature" and parameter == "temperature" and day_index <= 30:
                trend_factor = 1.0 + (0.35 * (30 - day_index) / 30)
            if problem_pattern == "increasing_vibration" and parameter == "vibration" and day_index <= 30:
                trend_factor = 1.0 + (0.4 * (30 - day_index) / 30)
            value = max(baseline * noise * trend_factor, 0)
            db.add(
                EquipmentReading(
                    reading_at=reading_at,
                    parameter=parameter,
                    value=round(value, 2),
                    unit=unit,
                    equipment_id=equipment.id,
                )
            )
            values.append(value)
        series_by_param[parameter] = values
    return series_by_param


def _generate_maintenance_for_equipment(
    db, equipment: Equipment, today: date, technicians: list[User], corrective_count_recent: int | None
) -> int:
    """1-3 routine records normally; forces `corrective_count_recent` recent corrective
    records for the "repeated_maintenance" problem pattern. Returns the count of
    corrective/emergency records within the last 180 days, for the health-score computation.
    Generates a real work_order_number for every record (mirrors routers/maintenance.py's
    own generation, since this script inserts directly via the ORM, bypassing that API)."""
    records_to_create = random.randint(1, 3)
    if corrective_count_recent is not None:
        records_to_create = max(records_to_create, corrective_count_recent)

    corrective_recent = 0
    created: list[MaintenanceRecord] = []
    for i in range(records_to_create):
        force_recent_corrective = corrective_count_recent is not None and i < corrective_count_recent
        if force_recent_corrective:
            maintenance_type = "corrective"
        else:
            maintenance_type = random.choices(ROUTINE_MAINTENANCE_TYPES, weights=ROUTINE_MAINTENANCE_WEIGHTS)[0]

        start = (
            today - timedelta(days=random.randint(1, 170))
            if force_recent_corrective
            else today - timedelta(days=random.randint(1, READING_DAYS))
        )
        completed = random.random() > 0.15
        completion = start + timedelta(days=random.randint(0, 3)) if completed else None
        disruptive = maintenance_type in DISRUPTIVE_MAINTENANCE_TYPES

        labor_cost = round(random.uniform(200, 6000), 2)
        parts_cost = round(random.uniform(500, 8000), 2) if disruptive else round(random.uniform(0, 1500), 2)
        contractor_cost = round(random.uniform(200, 4000), 2) if random.random() > 0.6 else None
        other_cost = round(random.uniform(50, 500), 2) if random.random() > 0.7 else None

        record = MaintenanceRecord(
            maintenance_type=maintenance_type,
            priority=_priority_for_type(maintenance_type),
            status="completed" if completed else "in_progress",
            description=f"{'Routine' if not disruptive else 'Corrective'} service on {equipment.equipment_tag}",
            planned_start_date=start - timedelta(days=random.randint(0, 2)),
            planned_completion_date=completion or (start + timedelta(days=random.randint(1, 5))),
            start_date=start,
            completion_date=completion,
            labor_cost=labor_cost,
            parts_cost=parts_cost,
            contractor_cost=contractor_cost,
            other_cost=other_cost,
            downtime_hours=round(random.uniform(2, 24), 1) if disruptive and completed else None,
            failure_cause=random.choice(FAILURE_CAUSES) if disruptive else None,
            corrective_action=random.choice(CORRECTIVE_ACTIONS) if disruptive and completed else None,
            notes="Synthetic demo maintenance record." if random.random() > 0.5 else None,
            technician_id=random.choice(technicians).id if technicians and random.random() < 0.7 else None,
            equipment_id=equipment.id,
        )
        record.cost = _sum_costs(labor_cost, parts_cost, contractor_cost, other_cost)
        db.add(record)
        created.append(record)
        if maintenance_type in DISRUPTIVE_MAINTENANCE_TYPES and (today - start).days <= 180:
            corrective_recent += 1

    db.flush()
    for record in created:
        record.work_order_number = f"WO-{record.id:06d}"

    return corrective_recent


def seed_wells() -> None:
    db = SessionLocal()
    try:
        if db.query(Field).count() > 0:
            print("Wells demo data already present — skipping (idempotent guard).")
            return

        fields = []
        for field_def in FIELD_DEFS:
            field = Field(name=field_def["name"], country=field_def["country"])
            db.add(field)
            db.flush()
            fields.append((field, field_def))

        facilities = []
        for field, field_def in fields:
            for i in range(random.randint(*FACILITIES_PER_FIELD)):
                facility = Facility(
                    name=f"{field_def['code']} {random.choice(FACILITY_KINDS)} {chr(65 + i)}",
                    facility_type=random.choice(FACILITY_TYPES),
                    field_id=field.id,
                )
                db.add(facility)
                db.flush()
                facilities.append((facility, field_def))

        wells = []
        for seq in range(1, WELLS_TOTAL + 1):
            facility, field_def = random.choice(facilities)
            status = random.choices(["active", "shut_in", "suspended"], weights=[80, 12, 8])[0]

            well = Well(
                well_id=f"{field_def['code']}-{facility.id:02d}-{seq:03d}",
                name=f"{field_def['code']} Well {seq:03d}",
                well_type=random.choice(WELL_TYPES),
                status=status,
                artificial_lift_type=random.choice(LIFT_TYPES),
                latitude=_jitter(field_def["base_lat"], 0.5),
                longitude=_jitter(field_def["base_lon"], 0.5),
                completion_date=date.today() - timedelta(days=random.randint(200, 2500)),
                completion_type=random.choice(COMPLETION_TYPES),
                total_depth_ft=round(random.uniform(6000, 14000), 1),
                facility_id=facility.id,
            )
            db.add(well)
            db.flush()
            wells.append(well)

        anomaly_well_ids = set(random.sample([w.id for w in wells], k=min(3, len(wells))))
        today = date.today()

        for well in wells:
            base_oil = random.uniform(200, 2000)
            gor_scf_per_bbl = random.uniform(300, 1200)
            base_water_cut = random.uniform(5, 25)
            base_wellhead_pressure = random.uniform(800, 2200)
            base_temperature = random.uniform(120, 220)
            declining_hard = well.id in anomaly_well_ids

            for day_index in range(PRODUCTION_DAYS, -1, -1):
                record_date = today - timedelta(days=day_index)
                age_factor = 0.999 ** (PRODUCTION_DAYS - day_index)
                noise = random.uniform(0.94, 1.06)

                anomaly_factor = 1.0
                water_cut_anomaly = 1.0
                if declining_hard and day_index <= 14:
                    anomaly_factor = max(1.0 - (0.03 * (14 - day_index)), 0.4)
                    water_cut_anomaly = 1.0 + (0.02 * (14 - day_index))

                if well.status == "active":
                    oil = max(base_oil * age_factor * noise * anomaly_factor, 0)
                    water_cut = min(
                        (base_water_cut + (PRODUCTION_DAYS - day_index) * 0.05) * water_cut_anomaly, 92
                    )
                    water = oil * water_cut / (100 - water_cut) if oil > 0 else 0
                    gas = oil * gor_scf_per_bbl / 1000
                else:
                    oil = water = gas = 0
                    water_cut = None

                db.add(
                    ProductionRecord(
                        record_date=record_date,
                        oil_bopd=round(oil, 1),
                        gas_mscfd=round(gas, 2),
                        water_bwpd=round(water, 1),
                        water_cut_pct=round(water_cut, 2) if water_cut is not None else None,
                        gor=round(gor_scf_per_bbl, 1),
                        choke_size=round(random.uniform(24, 64), 1),
                        well_id=well.id,
                    )
                )

                pressure_noise = random.uniform(0.97, 1.03)
                pressure_anomaly = 1.0
                if declining_hard and day_index <= 14:
                    pressure_anomaly = max(1.0 - (0.02 * (14 - day_index)), 0.6)
                wellhead_pressure = base_wellhead_pressure * age_factor * pressure_noise * pressure_anomaly

                db.add(
                    PressureRecord(
                        record_date=record_date,
                        wellhead_pressure=round(wellhead_pressure, 1),
                        tubing_pressure=round(wellhead_pressure * 1.15, 1),
                        casing_pressure=round(wellhead_pressure * 0.6, 1),
                        flowline_pressure=round(wellhead_pressure * 0.85, 1),
                        well_id=well.id,
                    )
                )

                if well.status == "active":
                    temperature_noise = random.uniform(0.97, 1.03)
                    wellhead_temperature = base_temperature * age_factor * temperature_noise
                    db.add(
                        TemperatureRecord(
                            record_date=record_date,
                            wellhead_temperature=round(wellhead_temperature, 1),
                            well_id=well.id,
                        )
                    )

            db.flush()

            # One target per active well only — a shut-in/suspended well was deliberately
            # taken offline by the operator, so comparing its (expected) zero production
            # against a target would just be a distortion, not a real shortfall.
            if well.status != "active":
                continue

            target_effective = max(well.completion_date, today - timedelta(days=PRODUCTION_DAYS))
            db.add(
                ProductionTarget(
                    well_id=well.id,
                    effective_date=target_effective,
                    oil_target_bopd=round(base_oil * random.uniform(1.05, 1.15), 1),
                    gas_target_mscfd=round(base_oil * gor_scf_per_bbl / 1000 * random.uniform(1.05, 1.15), 2),
                    water_target_bwpd=round(base_oil * (base_water_cut / (100 - base_water_cut)) * 1.1, 1)
                    if base_water_cut < 100
                    else None,
                )
            )

        # Retained (not just added) so the Production Loss section below can tie loss records
        # to these same real downtime events rather than fabricating independent ones.
        general_downtime_events: list[tuple[int, DowntimeEvent]] = []
        for _ in range(random.randint(8, 12)):
            well = random.choice(wells)
            start = datetime.now(timezone.utc) - timedelta(
                days=random.randint(1, PRODUCTION_DAYS), hours=random.randint(0, 23)
            )
            end = start + timedelta(hours=random.uniform(2, 72)) if random.random() > 0.1 else None
            event = DowntimeEvent(
                start_time=start,
                end_time=end,
                reason=random.choice(DOWNTIME_REASONS),
                well_id=well.id,
            )
            db.add(event)
            general_downtime_events.append((well.id, event))

        # Guarantee each anomaly well has at least one downtime event inside its own
        # final-14-day decline window, so the "active issues" panel and downtime summaries
        # have something concrete to show for the wells with the intentional anomaly.
        anomaly_downtime_events: list[tuple[int, DowntimeEvent]] = []
        for well_id in anomaly_well_ids:
            start = datetime.now(timezone.utc) - timedelta(
                days=random.randint(1, 13), hours=random.randint(0, 23)
            )
            end = start + timedelta(hours=random.uniform(4, 48)) if random.random() > 0.3 else None
            event = DowntimeEvent(
                start_time=start,
                end_time=end,
                reason=random.choice(DOWNTIME_REASONS),
                well_id=well_id,
            )
            db.add(event)
            anomaly_downtime_events.append((well_id, event))

        # ----- Equipment (Equipment module) -----
        equipment_list: list[Equipment] = []

        # ----- Maintenance module: demo technicians (additive, idempotent) -----
        technicians = _seed_technicians(db)

        # Well-level lift equipment (existing concept, status vocabulary fixed to the
        # Equipment module's spec: operating/standby/maintenance/failed/decommissioned/
        # unknown — was operational/degraded/down).
        for well in wells:
            if well.artificial_lift_type in (None, "natural_flow"):
                continue

            equipment = Equipment(
                equipment_tag=f"{well.artificial_lift_type}-{well.well_id}",
                name=f"{well.artificial_lift_type} — {well.well_id}",
                equipment_type=well.artificial_lift_type,
                manufacturer=random.choice(EQUIPMENT_MANUFACTURERS),
                model=f"Model-{random.randint(100, 999)}",
                serial_number=f"SN-{random.randint(100000, 999999)}",
                installation_date=well.completion_date,
                commissioning_date=well.completion_date + timedelta(days=random.randint(0, 30)),
                description=f"Synthetic demo equipment record for {well.artificial_lift_type}.",
                status=random.choices(
                    ["operating", "standby", "maintenance", "failed"], weights=[75, 10, 10, 5]
                )[0],
                operating_hours=round(random.uniform(500, 55000), 1),
                next_maintenance_due=today + timedelta(days=random.randint(-10, 120)),
                well_id=well.id,
            )
            db.add(equipment)
            db.flush()
            equipment_list.append(equipment)

        # Facility-level equipment (new): compressors/generators/separators/heat exchangers/
        # valves/instrumentation not tied to any specific well.
        for facility, field_def in facilities:
            weights = FACILITY_EQUIPMENT_WEIGHTS.get(facility.facility_type, [1] * len(FACILITY_EQUIPMENT_TYPES))
            for i in range(random.randint(1, 3)):
                equipment_type = random.choices(FACILITY_EQUIPMENT_TYPES, weights=weights)[0]
                install_date = today - timedelta(days=random.randint(200, 3000))
                equipment = Equipment(
                    equipment_tag=f"{equipment_type.upper()[:4]}-{facility.id:02d}-{i + 1:02d}",
                    name=f"{equipment_type.replace('_', ' ').title()} {i + 1} — {facility.name}",
                    equipment_type=equipment_type,
                    manufacturer=random.choice(EQUIPMENT_MANUFACTURERS),
                    model=f"Model-{random.randint(100, 999)}",
                    serial_number=f"SN-{random.randint(100000, 999999)}",
                    installation_date=install_date,
                    commissioning_date=install_date + timedelta(days=random.randint(0, 30)),
                    description=f"Synthetic demo equipment record for {equipment_type}.",
                    status=random.choices(
                        ["operating", "standby", "maintenance", "failed"], weights=[75, 10, 10, 5]
                    )[0],
                    operating_hours=round(random.uniform(500, 55000), 1),
                    next_maintenance_due=today + timedelta(days=random.randint(-10, 120)),
                    facility_id=facility.id,
                )
                db.add(equipment)
                db.flush()
                equipment_list.append(equipment)

        # Hand-picked examples so the UI has at least one of each vocabulary value the
        # random weights above don't otherwise favor.
        if len(equipment_list) >= 2:
            equipment_list[-1].status = "decommissioned"
            equipment_list[-2].status = "unknown"

        # Five problem-equipment items, one pattern each — mirrors anomaly_well_ids. The
        # resulting health_score is never set directly here: it always comes from
        # compute_health() below, given the deliberately-bad data these patterns produce.
        decommissioned_or_unknown_ids = {equipment_list[-1].id, equipment_list[-2].id} if len(equipment_list) >= 2 else set()
        problem_pool = [e for e in equipment_list if e.id not in decommissioned_or_unknown_ids]
        problem_equipment = random.sample(problem_pool, k=min(5, len(problem_pool)))
        pattern_by_equipment_id = {
            equipment.id: pattern for equipment, pattern in zip(problem_equipment, PROBLEM_PATTERNS)
        }

        # Retained so the Production Loss section below can link a real loss record to the
        # same failure incident (its equipment, downtime event, and emergency work order).
        failure_event_incidents: list[tuple[Equipment, DowntimeEvent, MaintenanceRecord]] = []

        for equipment in equipment_list:
            pattern = pattern_by_equipment_id.get(equipment.id)
            parameters = READING_PARAMETERS_BY_TYPE.get(equipment.equipment_type, [])

            readings_by_param = _generate_readings_for_equipment(
                db,
                equipment,
                parameters,
                problem_pattern=pattern if pattern in ("increasing_temperature", "increasing_vibration") else None,
            )

            corrective_recent = _generate_maintenance_for_equipment(
                db,
                equipment,
                today,
                technicians,
                corrective_count_recent=random.randint(3, 5) if pattern == "repeated_maintenance" else None,
            )

            downtime_hours_90d = 0.0
            if pattern == "excessive_operating_hours":
                equipment.operating_hours = round(random.uniform(45000, 60000), 1)
            if pattern == "failure_event":
                equipment.status = "failed"
                failure_start = datetime.now(timezone.utc) - timedelta(
                    days=random.randint(1, 5), hours=random.randint(0, 23)
                )
                failure_downtime_event = DowntimeEvent(
                    start_time=failure_start,
                    end_time=None,
                    reason="equipment failure",
                    well_id=equipment.well_id,
                    equipment_id=equipment.id,
                )
                db.add(failure_downtime_event)
                downtime_hours_90d = (datetime.now(timezone.utc) - failure_start).total_seconds() / 3600

                labor_cost = round(random.uniform(1000, 8000), 2)
                parts_cost = round(random.uniform(500, 12000), 2)
                contractor_cost = round(random.uniform(500, 5000), 2) if random.random() > 0.5 else None
                emergency_record = MaintenanceRecord(
                    maintenance_type="emergency",
                    priority="critical",
                    status="in_progress",
                    description=f"Emergency repair on {equipment.equipment_tag}",
                    planned_start_date=today,
                    planned_completion_date=today + timedelta(days=random.randint(1, 4)),
                    start_date=today,
                    labor_cost=labor_cost,
                    parts_cost=parts_cost,
                    contractor_cost=contractor_cost,
                    failure_cause=random.choice(FAILURE_CAUSES),
                    notes="Synthetic demo emergency work order — still open at seed time.",
                    technician_id=random.choice(technicians).id if technicians else None,
                    equipment_id=equipment.id,
                )
                emergency_record.cost = _sum_costs(labor_cost, parts_cost, contractor_cost)
                db.add(emergency_record)
                db.flush()
                emergency_record.work_order_number = f"WO-{emergency_record.id:06d}"
                corrective_recent += 1
                failure_event_incidents.append((equipment, failure_downtime_event, emergency_record))

            db.flush()

            health_inputs = HealthInputs(
                status=equipment.status,
                operating_hours=equipment.operating_hours,
                operating_hours_threshold=DEFAULT_OPERATING_HOURS_THRESHOLD,
                temperature_readings=readings_by_param.get("temperature", [])[-30:],
                vibration_readings=readings_by_param.get("vibration", [])[-30:],
                current_readings=readings_by_param.get("current", [])[-30:],
                flow_readings=readings_by_param.get("flow", [])[-30:],
                corrective_maintenance_count_180d=corrective_recent,
                downtime_hours_90d=round(downtime_hours_90d, 2),
                recent_alert_count_30d=0,
            )
            equipment.health_score = compute_health(health_inputs).score

        # Explicit status-variety pass: the per-equipment loop above naturally produces
        # mostly completed/in_progress work, so the Schedule/Overdue/Work-Orders views
        # wouldn't otherwise have real scheduled/waiting/cancelled examples to show.
        extra_status_examples = [("scheduled", 4), ("waiting_for_parts", 2), ("cancelled", 2)]
        extra_work_orders = 0
        for status_value, count in extra_status_examples:
            for _ in range(count):
                equipment = random.choice(equipment_list)
                planned_start = today + timedelta(days=random.randint(1, 45))
                maintenance_type = random.choice(["preventive", "inspection", "calibration", "routine"])
                record = MaintenanceRecord(
                    maintenance_type=maintenance_type,
                    priority=_priority_for_type(maintenance_type),
                    status=status_value,
                    description=f"Scheduled {maintenance_type} for {equipment.equipment_tag}",
                    planned_start_date=planned_start,
                    planned_completion_date=planned_start + timedelta(days=random.randint(1, 5)),
                    notes=(
                        "Synthetic demo — cancelled before work began."
                        if status_value == "cancelled"
                        else "Synthetic demo work order, not yet started."
                    ),
                    technician_id=random.choice(technicians).id if technicians and random.random() < 0.5 else None,
                    equipment_id=equipment.id,
                )
                db.add(record)
                db.flush()
                record.work_order_number = f"WO-{record.id:06d}"
                extra_work_orders += 1

        # Ensure at least a few equipment show a genuinely overdue next_maintenance_due (no
        # offsetting recent completed work), so the Overdue view has real content.
        overdue_equipment = random.sample(equipment_list, k=min(3, len(equipment_list)))
        for equipment in overdue_equipment:
            equipment.next_maintenance_due = today - timedelta(days=random.randint(3, 45))

        # ----- Production Loss module -----
        # Every ProductionLoss row below is tied to a real incident already generated above
        # (a failure_event equipment's downtime+emergency work order, an anomaly well's
        # guaranteed downtime event, or a sampled general downtime event) — never an
        # independently fabricated record. The lost-volume/revenue-impact figures are always
        # produced by calling the real _compute_derived_fields() (the exact function
        # routers/production_loss.py's API uses), from each incident's actual well_id/
        # loss_date resolved against real ProductionTarget/ProductionRecord/CommodityPrice
        # data — same "never fake it independently" principle already applied to equipment
        # health scoring above.
        commodity_price_count = _seed_commodity_prices(db, today)
        db.flush()

        production_loss_records: list[ProductionLoss] = []

        for equipment, downtime_event, maintenance_record in failure_event_incidents:
            loss = ProductionLoss(
                loss_date=downtime_event.start_time.date(),
                category="equipment_failure",
                cause=f"{equipment.equipment_tag}: {maintenance_record.failure_cause}",
                well_id=equipment.well_id,
                equipment_id=equipment.id,
                downtime_event_id=downtime_event.id,
                maintenance_record_id=maintenance_record.id,
            )
            _compute_derived_fields(db, loss, downtime_event, maintenance_record)
            db.add(loss)
            production_loss_records.append(loss)

        for well_id, event in anomaly_downtime_events:
            loss = ProductionLoss(
                loss_date=event.start_time.date(),
                category="reservoir",
                cause="Sharp production decline with an associated downtime event.",
                well_id=well_id,
                downtime_event_id=event.id,
            )
            _compute_derived_fields(db, loss, event, None)
            db.add(loss)
            production_loss_records.append(loss)

        general_loss_sample = random.sample(general_downtime_events, k=min(6, len(general_downtime_events)))
        for well_id, event in general_loss_sample:
            loss = ProductionLoss(
                loss_date=event.start_time.date(),
                category=random.choice(LOSS_CATEGORIES_GENERAL),
                cause=f"{event.reason.capitalize()} affecting well output." if event.reason else None,
                well_id=well_id,
                downtime_event_id=event.id,
            )
            _compute_derived_fields(db, loss, event, None)
            db.add(loss)
            production_loss_records.append(loss)

        # ----- Cost & Revenue module -----
        # Field/facility-level costs dominate (per the spec's own "don't require well/
        # equipment for field/facility-level costs"); a handful of well- and equipment-level
        # entries demonstrate the new equipment_id link. Currency is deliberately split by
        # field (Niger Delta Field -> NGN, Permian Basin/North Sea Field -> USD) so the
        # currency-mismatch guardrail in the Cost & Revenue module's margin calculations is
        # exercised by real seeded data, not just a hypothetical.
        facility_currency: dict[int, str] = {}
        operating_cost_count = 0
        for facility, field_def in facilities:
            currency = FIELD_CURRENCY.get(field_def["code"], "USD")
            facility_currency[facility.id] = currency
            ranges = OPERATING_COST_RANGES_USD if currency == "USD" else OPERATING_COST_RANGES_NGN
            for months_ago in range(11, -1, -1):
                month_date = today - timedelta(days=months_ago * 30)
                categories_this_month = random.sample(list(ranges.keys()), k=random.randint(2, 5))
                for category in categories_this_month:
                    low, high = ranges[category]
                    db.add(
                        OperatingCost(
                            cost_date=month_date,
                            category=category,
                            amount=round(random.uniform(low, high), 2),
                            currency=currency,
                            description=f"Synthetic demo {category.lower()} cost — {facility.name}",
                            cost_period="monthly",
                            source=random.choice(COST_SOURCES),
                            notes="Synthetic/demo data — not a real operational cost record.",
                            facility_id=facility.id,
                        )
                    )
                    operating_cost_count += 1

        def _equipment_currency(equipment: Equipment) -> str:
            if equipment.facility_id:
                return facility_currency.get(equipment.facility_id, "USD")
            if equipment.well_id and equipment.well:
                return facility_currency.get(equipment.well.facility_id, "USD")
            return "USD"

        well_level_sample = random.sample(wells, k=min(6, len(wells)))
        for well in well_level_sample:
            currency = facility_currency.get(well.facility_id, "USD")
            ranges = OPERATING_COST_RANGES_USD if currency == "USD" else OPERATING_COST_RANGES_NGN
            category = random.choice(["Contractor", "Production", "Logistics"])
            low, high = ranges[category]
            db.add(
                OperatingCost(
                    cost_date=today - timedelta(days=random.randint(1, 60)),
                    category=category,
                    amount=round(random.uniform(low, high) * 0.3, 2),
                    currency=currency,
                    description=f"Synthetic demo {category.lower()} cost — {well.well_id}",
                    cost_period="one_time",
                    source="invoice",
                    notes="Synthetic/demo data — not a real operational cost record.",
                    well_id=well.id,
                )
            )
            operating_cost_count += 1

        equipment_cost_sample = random.sample(equipment_list, k=min(8, len(equipment_list)))
        for equipment in equipment_cost_sample:
            currency = _equipment_currency(equipment)
            ranges = OPERATING_COST_RANGES_USD if currency == "USD" else OPERATING_COST_RANGES_NGN
            category = random.choice(["Energy", "Equipment", "Maintenance"])
            low, high = ranges[category]
            db.add(
                OperatingCost(
                    cost_date=today - timedelta(days=random.randint(1, 60)),
                    category=category,
                    amount=round(random.uniform(low, high) * 0.2, 2),
                    currency=currency,
                    description=f"Synthetic demo {category.lower()} cost — {equipment.equipment_tag}",
                    cost_period="one_time",
                    source="estimate",
                    notes="Synthetic/demo data — not a real operational cost record.",
                    equipment_id=equipment.id,
                )
            )
            operating_cost_count += 1

        db.commit()
        print(f"Seeded {len(fields)} fields, {len(facilities)} facilities, {len(wells)} wells,")
        print(
            f"{PRODUCTION_DAYS} days of production/pressure/temperature history per well, "
            "one production target per active well, plus downtime and maintenance records."
        )
        print(
            f"Seeded {len(equipment_list)} equipment items with {READING_DAYS} days of readings "
            f"each (where applicable); {len(problem_equipment)} deliberately show a health issue "
            "via their real computed health score."
        )
        print(
            f"Seeded {len(technicians)} demo maintenance technicians, {extra_work_orders} extra "
            f"scheduled/waiting/cancelled work orders, and {len(overdue_equipment)} equipment "
            "items with an intentionally overdue next maintenance date."
        )
        print(
            f"Seeded {commodity_price_count} commodity price points and "
            f"{len(production_loss_records)} production-loss records, each tied to a real "
            "synthetic downtime/failure/maintenance incident with its estimate computed by "
            "the real calculation service."
        )
        print(
            f"Seeded {operating_cost_count} operating cost records across all 11 categories "
            "(field/facility-level, mostly, plus a handful of well- and equipment-level "
            "entries), with Niger Delta Field costs in NGN and Permian Basin/North Sea Field "
            "costs in USD."
        )

        # Alerts module: run the real rule engine against everything just seeded — every
        # generated alert therefore references a real well/equipment/maintenance-record/
        # production-loss-event, never an independently invented one.
        alert_run = run_alert_rules(db)
        print(
            f"Ran the Alerts rule engine: {alert_run.created} alerts created, "
            f"{alert_run.updated} reaffirmed (deduplicated), {alert_run.auto_resolved} "
            "auto-resolved, by category: "
            + ", ".join(f"{cat} {counts['created']}" for cat, counts in alert_run.by_category.items())
        )

        # AI Insights module: run the real (100% deterministic) insight engine against
        # everything just seeded, including the alerts generated above — every insight
        # therefore references a real well/equipment/maintenance-record/production-loss-event,
        # never a disconnected, independently invented one.
        insight_run = run_insight_engine(db)
        print(
            f"Ran the AI Insights engine: {insight_run.created} insights created, "
            f"{insight_run.updated} reaffirmed (deduplicated), by category: "
            + ", ".join(f"{cat} {counts['created']}" for cat, counts in insight_run.by_category.items())
        )

        print("All data is synthetic/demo data — not real operational data.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_wells()
