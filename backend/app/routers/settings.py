from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.settings import SystemSetting
from app.models.user import User
from app.schemas.settings import SettingRead, SettingUpdate
from app.services.audit import AuditAction, record_audit_event

router = APIRouter(prefix="/settings", tags=["settings"])

NUMERIC_SETTING_KEYS = {
    "boe_gas_factor_scf_per_bbl",
    "equipment_health_operating_hours_threshold",
    "maintenance_schedule_lookahead_days",
    "alert_production_below_target_pct",
    "alert_production_decline_pct",
    "alert_production_unusual_change_pct",
    "alert_equipment_health_attention_threshold",
    "alert_equipment_health_critical_threshold",
    "alert_maintenance_repeated_events_count",
    "alert_maintenance_repeated_events_window_days",
    "alert_production_loss_high_threshold_bbl",
    "alert_production_loss_repeated_events_count",
    "alert_production_loss_repeated_events_window_days",
    "alert_downtime_high_threshold_hours",
    "alert_high_lost_revenue_threshold_usd",
    "alert_high_operating_cost_threshold_usd",
    "alert_high_operating_cost_threshold_ngn",
    "alert_cost_per_bbl_increase_pct",
    "alert_cost_per_boe_increase_pct",
    "alert_margin_decline_pct",
    "alert_high_maintenance_cost_multiplier",
    "alert_high_financial_impact_threshold_usd",
    "insight_production_increase_pct",
    "insight_trend_window_months",
    "insight_well_comparison_ratio_threshold",
    "insight_maintenance_frequency_increase_multiplier",
    "insight_high_maintenance_cost_vs_production_threshold_usd",
    "insight_cross_domain_lookback_days",
    "insight_stale_after_days",
    "whatif_reasonable_change_pct_bound",
}

# Non-numeric settings that must still not accept "obviously invalid values" — a closed set of
# allowed strings for the ones with a natural enumeration; company_name/timezone/*_unit stay
# free text (validated only for non-blank, matching the codebase's general open-vocabulary
# convention for e.g. maintenance_type/category fields elsewhere) rather than inventing a closed
# IANA-timezone or unit vocabulary this project has no other use for yet.
ALLOWED_VALUES: dict[str, set[str]] = {
    "default_currency": {"USD", "NGN"},
    "unit_system": {"imperial", "metric"},
}

FREE_TEXT_SETTING_KEYS = {
    "company_name",
    "timezone",
    "date_format",
    "default_production_unit",
    "default_gas_unit",
    "default_volume_unit",
}


@router.get("", response_model=list[SettingRead])
def list_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SystemSetting]:
    return db.query(SystemSetting).order_by(SystemSetting.key).all()


@router.put("/{key}", response_model=SettingRead)
def update_setting(
    key: str,
    payload: SettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator")),
) -> SystemSetting:
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")

    if key in NUMERIC_SETTING_KEYS:
        try:
            parsed = float(payload.value)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Value must be numeric"
            ) from exc
        if parsed <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Value must be positive")
    elif key in ALLOWED_VALUES:
        if payload.value not in ALLOWED_VALUES[key]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Value must be one of: {', '.join(sorted(ALLOWED_VALUES[key]))}",
            )
    elif key in FREE_TEXT_SETTING_KEYS:
        if not payload.value.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Value must not be blank")

    old_value = setting.value
    setting.value = payload.value
    db.commit()
    db.refresh(setting)
    record_audit_event(
        db, current_user, AuditAction.SYSTEM_SETTING_CHANGED, "system_setting", resource_id=None,
        details=f"Changed setting '{key}'",
        metadata={"key": key, "from_value": old_value, "to_value": payload.value},
    )
    return setting
