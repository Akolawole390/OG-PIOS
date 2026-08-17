"""Transparent, rule-based equipment health scoring.

`compute_health()` is a pure function (plain values in, no DB/ORM/FastAPI imports) so the
formula is directly unit-testable (backend/tests/test_equipment_health.py) and reusable from
both the API and the synthetic data seeder (backend/app/db/seed_wells.py) — the seed script's
"problem equipment" must score low *because* compute_health() says so given bad underlying
data, not via an independently faked number.

`recompute_equipment_health()` (bottom of this file) is the DB-querying orchestration wrapper
around it — gathers real inputs for one Equipment row and persists the score. It is not pure
and is not unit-tested directly (covered instead via backend/tests/test_equipment.py and
test_maintenance.py's API-level tests); it is imported by both routers/equipment.py and
routers/maintenance.py (the Maintenance module's create/update/delete of a MaintenanceRecord
also affects the equipment health score) rather than being duplicated in each.

IMPORTANT: this is a decision-support indicator, not a certified safety or reliability
engineering system. See HEALTH_SCORE_DISCLAIMER — it must accompany every score shown to a
user (mirrors the AIRecommendation.disclaimer_text guardrail in backend/app/models/ai.py, as
a response field here rather than a DB column since a health score is computed fresh per
request, not a persisted entity with its own lifecycle).
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

HEALTH_SCORE_DISCLAIMER = (
    "Rule-based health indicator computed from available operating data; not a failure "
    "prediction or certified safety assessment. Requires engineering review before acting "
    "on it."
)

DEFAULT_OPERATING_HOURS_THRESHOLD = 40000.0

BAND_EXCELLENT = "Excellent"
BAND_GOOD = "Good"
BAND_MONITOR = "Monitor"
BAND_MAINTENANCE_REQUIRED = "Maintenance Required"
BAND_CRITICAL = "Critical"


def band_for(score: float) -> str:
    if score >= 90:
        return BAND_EXCELLENT
    if score >= 75:
        return BAND_GOOD
    if score >= 50:
        return BAND_MONITOR
    if score >= 25:
        return BAND_MAINTENANCE_REQUIRED
    return BAND_CRITICAL


@dataclass
class HealthFactor:
    factor: str
    deduction: float
    detail: str


@dataclass
class HealthReadingSeries:
    """Chronologically ordered (oldest first) readings for one parameter, last 30 days."""

    values: list[float] = field(default_factory=list)


@dataclass
class HealthInputs:
    status: str
    operating_hours: float | None = None
    operating_hours_threshold: float = DEFAULT_OPERATING_HOURS_THRESHOLD
    temperature_readings: list[float] = field(default_factory=list)  # last 30 days, oldest first
    vibration_readings: list[float] = field(default_factory=list)
    current_readings: list[float] = field(default_factory=list)  # trailing window, oldest first
    flow_readings: list[float] = field(default_factory=list)
    corrective_maintenance_count_180d: int = 0
    downtime_hours_90d: float = 0.0
    recent_alert_count_30d: int = 0


@dataclass
class HealthResult:
    score: float
    band: str
    starting_score: float
    factors: list[HealthFactor]
    disclaimer_text: str
    computed_at: datetime


def _pct_change(values: list[float]) -> float | None:
    """First-vs-last percent change for a >=5-point series. None if too little data or a
    zero/negative baseline (can't compute a meaningful percent change)."""
    if len(values) < 5:
        return None
    first = values[0]
    last = values[-1]
    if first <= 0:
        return None
    return (last - first) / first * 100


def _zscore_anomaly(values: list[float]) -> bool:
    """True if the latest value is >2 standard deviations from the trailing mean of the
    rest of the series. Simple statistical check, not machine learning."""
    if len(values) < 5:
        return False
    *history, latest = values
    mean = sum(history) / len(history)
    variance = sum((v - mean) ** 2 for v in history) / len(history)
    std_dev = variance**0.5
    if std_dev == 0:
        return False
    return abs(latest - mean) / std_dev > 2


def compute_health(inputs: HealthInputs) -> HealthResult:
    factors: list[HealthFactor] = []

    if inputs.operating_hours is not None and inputs.operating_hours > inputs.operating_hours_threshold:
        excess_ratio = (inputs.operating_hours - inputs.operating_hours_threshold) / inputs.operating_hours_threshold
        deduction = min(excess_ratio * 15, 15)
        factors.append(
            HealthFactor(
                "operating_hours",
                round(deduction, 2),
                f"{inputs.operating_hours:.0f} operating hours exceeds the "
                f"{inputs.operating_hours_threshold:.0f}-hour reference threshold.",
            )
        )

    temp_change = _pct_change(inputs.temperature_readings)
    if temp_change is not None and temp_change > 10:
        deduction = min(temp_change * 0.5, 15)
        factors.append(
            HealthFactor(
                "temperature_trend",
                round(deduction, 2),
                f"Temperature readings trended up {temp_change:.1f}% over the last 30 days.",
            )
        )

    vib_change = _pct_change(inputs.vibration_readings)
    if vib_change is not None and vib_change > 10:
        deduction = min(vib_change * 0.6, 15)
        factors.append(
            HealthFactor(
                "vibration_trend",
                round(deduction, 2),
                f"Vibration readings trended up {vib_change:.1f}% over the last 30 days.",
            )
        )

    if _zscore_anomaly(inputs.current_readings) or _zscore_anomaly(inputs.flow_readings):
        factors.append(
            HealthFactor(
                "current_flow_anomaly",
                8.0,
                "Latest current/flow reading deviates more than 2 standard deviations from "
                "its recent trailing average.",
            )
        )

    if inputs.corrective_maintenance_count_180d > 0:
        deduction = min(inputs.corrective_maintenance_count_180d * 5, 20)
        factors.append(
            HealthFactor(
                "maintenance_history",
                round(deduction, 2),
                f"{inputs.corrective_maintenance_count_180d} corrective maintenance event(s) "
                "in the last 180 days.",
            )
        )

    if inputs.status == "failed":
        factors.append(HealthFactor("status", 30.0, "Equipment status is currently Failed."))
    elif inputs.status == "maintenance":
        factors.append(HealthFactor("status", 10.0, "Equipment status is currently Maintenance."))

    if inputs.downtime_hours_90d > 0:
        deduction = min(inputs.downtime_hours_90d / 24 * 2, 15)
        factors.append(
            HealthFactor(
                "downtime",
                round(deduction, 2),
                f"{inputs.downtime_hours_90d:.1f} downtime hours in the last 90 days.",
            )
        )

    if inputs.recent_alert_count_30d > 0:
        deduction = min(inputs.recent_alert_count_30d * 3, 10)
        factors.append(
            HealthFactor(
                "alarm_frequency",
                round(deduction, 2),
                f"{inputs.recent_alert_count_30d} alert(s) in the last 30 days.",
            )
        )

    total_deduction = sum(f.deduction for f in factors)
    score = max(0.0, min(100.0, 100.0 - total_deduction))

    return HealthResult(
        score=round(score, 1),
        band=band_for(score),
        starting_score=100.0,
        factors=factors,
        disclaimer_text=HEALTH_SCORE_DISCLAIMER,
        computed_at=datetime.now(timezone.utc),
    )


def recompute_equipment_health(db: Session, equipment) -> HealthResult:
    """Gathers this equipment's real readings/maintenance/downtime/alert data, scores it via
    compute_health(), stores the result on equipment.health_score, and returns the full
    breakdown. Called on equipment create/update (routers/equipment.py) and on maintenance
    create/update/delete (routers/maintenance.py) — imported by both rather than duplicated.
    """
    from app.models.ai import Alert
    from app.models.equipment import DowntimeEvent, EquipmentReading, MaintenanceRecord
    from app.services.reliability_metrics import _merge_intervals
    from app.services.system_settings import get_equipment_health_hours_threshold

    threshold = get_equipment_health_hours_threshold(db)
    now = datetime.now(timezone.utc)
    window_30d = now - timedelta(days=30)
    window_90d = now - timedelta(days=90)
    window_180d = date.today() - timedelta(days=180)

    def readings_for(parameter: str) -> list[float]:
        rows = (
            db.query(EquipmentReading)
            .filter(
                EquipmentReading.equipment_id == equipment.id,
                EquipmentReading.parameter == parameter,
                EquipmentReading.reading_at >= window_30d,
            )
            .order_by(EquipmentReading.reading_at)
            .all()
        )
        return [r.value for r in rows]

    # Counts corrective AND emergency maintenance — both represent unplanned/reactive work,
    # and an emergency repair is at least as strong a negative reliability signal as a
    # routine corrective one.
    corrective_count = (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.equipment_id == equipment.id,
            MaintenanceRecord.maintenance_type.in_(["corrective", "emergency"]),
            MaintenanceRecord.start_date.isnot(None),
            MaintenanceRecord.start_date >= window_180d,
        )
        .count()
    )

    downtime_events = (
        db.query(DowntimeEvent)
        .filter(
            DowntimeEvent.equipment_id == equipment.id,
            DowntimeEvent.start_time < now,
            or_(DowntimeEvent.end_time.is_(None), DowntimeEvent.end_time > window_90d),
        )
        .all()
    )
    # Overlapping DowntimeEvent rows for the same equipment (nothing in the write path
    # prevents this today — see docs/data-model.md) are merged before summing, so overlapping
    # wall-clock downtime isn't double-counted. See reliability_metrics._merge_intervals for
    # the shared algorithm and its dedicated test coverage.
    clipped_spans: list[tuple[datetime, datetime]] = []
    for event in downtime_events:
        end = min(event.end_time or now, now)
        start = max(event.start_time, window_90d)
        if end > start:
            clipped_spans.append((start, end))
    downtime_hours = sum(
        (end - start).total_seconds() / 3600 for start, end in _merge_intervals(clipped_spans)
    )

    alert_count = (
        db.query(Alert)
        .filter(Alert.equipment_id == equipment.id, Alert.triggered_at >= window_30d)
        .count()
    )

    inputs = HealthInputs(
        status=equipment.status,
        operating_hours=equipment.operating_hours,
        operating_hours_threshold=threshold,
        temperature_readings=readings_for("temperature"),
        vibration_readings=readings_for("vibration"),
        current_readings=readings_for("current"),
        flow_readings=readings_for("flow"),
        corrective_maintenance_count_180d=corrective_count,
        downtime_hours_90d=round(downtime_hours, 2),
        recent_alert_count_30d=alert_count,
    )
    result = compute_health(inputs)
    equipment.health_score = result.score
    return result
