from sqlalchemy.orm import Session

from app.models.settings import SystemSetting

BOE_GAS_FACTOR_KEY = "boe_gas_factor_scf_per_bbl"
DEFAULT_BOE_GAS_FACTOR = "6000"

EQUIPMENT_HEALTH_HOURS_THRESHOLD_KEY = "equipment_health_operating_hours_threshold"
DEFAULT_EQUIPMENT_HEALTH_HOURS_THRESHOLD = "40000"

MAINTENANCE_SCHEDULE_LOOKAHEAD_DAYS_KEY = "maintenance_schedule_lookahead_days"
DEFAULT_MAINTENANCE_SCHEDULE_LOOKAHEAD_DAYS = "30"

# ----- Alerts module thresholds -----
# One _KEY/DEFAULT_ pair + typed getter per configurable rule threshold, same pattern as the
# three settings above. Defaults are documented in docs/data-model.md's Alerts rule table.

ALERT_PRODUCTION_BELOW_TARGET_PCT_KEY = "alert_production_below_target_pct"
DEFAULT_ALERT_PRODUCTION_BELOW_TARGET_PCT = "10"

ALERT_PRODUCTION_DECLINE_PCT_KEY = "alert_production_decline_pct"
DEFAULT_ALERT_PRODUCTION_DECLINE_PCT = "15"

ALERT_PRODUCTION_UNUSUAL_CHANGE_PCT_KEY = "alert_production_unusual_change_pct"
DEFAULT_ALERT_PRODUCTION_UNUSUAL_CHANGE_PCT = "30"

ALERT_EQUIPMENT_HEALTH_ATTENTION_THRESHOLD_KEY = "alert_equipment_health_attention_threshold"
DEFAULT_ALERT_EQUIPMENT_HEALTH_ATTENTION_THRESHOLD = "50"

ALERT_EQUIPMENT_HEALTH_CRITICAL_THRESHOLD_KEY = "alert_equipment_health_critical_threshold"
DEFAULT_ALERT_EQUIPMENT_HEALTH_CRITICAL_THRESHOLD = "25"

ALERT_MAINTENANCE_REPEATED_EVENTS_COUNT_KEY = "alert_maintenance_repeated_events_count"
DEFAULT_ALERT_MAINTENANCE_REPEATED_EVENTS_COUNT = "3"

ALERT_MAINTENANCE_REPEATED_EVENTS_WINDOW_DAYS_KEY = "alert_maintenance_repeated_events_window_days"
DEFAULT_ALERT_MAINTENANCE_REPEATED_EVENTS_WINDOW_DAYS = "90"

ALERT_PRODUCTION_LOSS_HIGH_THRESHOLD_BBL_KEY = "alert_production_loss_high_threshold_bbl"
DEFAULT_ALERT_PRODUCTION_LOSS_HIGH_THRESHOLD_BBL = "50"

ALERT_PRODUCTION_LOSS_REPEATED_EVENTS_COUNT_KEY = "alert_production_loss_repeated_events_count"
DEFAULT_ALERT_PRODUCTION_LOSS_REPEATED_EVENTS_COUNT = "3"

ALERT_PRODUCTION_LOSS_REPEATED_EVENTS_WINDOW_DAYS_KEY = (
    "alert_production_loss_repeated_events_window_days"
)
DEFAULT_ALERT_PRODUCTION_LOSS_REPEATED_EVENTS_WINDOW_DAYS = "90"

ALERT_DOWNTIME_HIGH_THRESHOLD_HOURS_KEY = "alert_downtime_high_threshold_hours"
DEFAULT_ALERT_DOWNTIME_HIGH_THRESHOLD_HOURS = "24"

ALERT_HIGH_LOST_REVENUE_THRESHOLD_USD_KEY = "alert_high_lost_revenue_threshold_usd"
DEFAULT_ALERT_HIGH_LOST_REVENUE_THRESHOLD_USD = "10000"

ALERT_HIGH_OPERATING_COST_THRESHOLD_USD_KEY = "alert_high_operating_cost_threshold_usd"
DEFAULT_ALERT_HIGH_OPERATING_COST_THRESHOLD_USD = "100000"

ALERT_HIGH_OPERATING_COST_THRESHOLD_NGN_KEY = "alert_high_operating_cost_threshold_ngn"
DEFAULT_ALERT_HIGH_OPERATING_COST_THRESHOLD_NGN = "50000000"

ALERT_COST_PER_BBL_INCREASE_PCT_KEY = "alert_cost_per_bbl_increase_pct"
DEFAULT_ALERT_COST_PER_BBL_INCREASE_PCT = "20"

ALERT_COST_PER_BOE_INCREASE_PCT_KEY = "alert_cost_per_boe_increase_pct"
DEFAULT_ALERT_COST_PER_BOE_INCREASE_PCT = "20"

ALERT_MARGIN_DECLINE_PCT_KEY = "alert_margin_decline_pct"
DEFAULT_ALERT_MARGIN_DECLINE_PCT = "25"

ALERT_HIGH_MAINTENANCE_COST_MULTIPLIER_KEY = "alert_high_maintenance_cost_multiplier"
DEFAULT_ALERT_HIGH_MAINTENANCE_COST_MULTIPLIER = "2.0"

ALERT_HIGH_FINANCIAL_IMPACT_THRESHOLD_USD_KEY = "alert_high_financial_impact_threshold_usd"
DEFAULT_ALERT_HIGH_FINANCIAL_IMPACT_THRESHOLD_USD = "25000"

# ----- AI Insights module thresholds -----
# Same _KEY/DEFAULT_ + typed-getter pattern. Defaults documented in docs/data-model.md's
# AI Insights type table.

INSIGHT_PRODUCTION_INCREASE_PCT_KEY = "insight_production_increase_pct"
DEFAULT_INSIGHT_PRODUCTION_INCREASE_PCT = "15"

INSIGHT_TREND_WINDOW_MONTHS_KEY = "insight_trend_window_months"
DEFAULT_INSIGHT_TREND_WINDOW_MONTHS = "3"

INSIGHT_WELL_COMPARISON_RATIO_THRESHOLD_KEY = "insight_well_comparison_ratio_threshold"
DEFAULT_INSIGHT_WELL_COMPARISON_RATIO_THRESHOLD = "0.6"

INSIGHT_MAINTENANCE_FREQUENCY_INCREASE_MULTIPLIER_KEY = (
    "insight_maintenance_frequency_increase_multiplier"
)
DEFAULT_INSIGHT_MAINTENANCE_FREQUENCY_INCREASE_MULTIPLIER = "1.5"

INSIGHT_HIGH_MAINTENANCE_COST_VS_PRODUCTION_THRESHOLD_USD_KEY = (
    "insight_high_maintenance_cost_vs_production_threshold_usd"
)
DEFAULT_INSIGHT_HIGH_MAINTENANCE_COST_VS_PRODUCTION_THRESHOLD_USD = "5"

INSIGHT_CROSS_DOMAIN_LOOKBACK_DAYS_KEY = "insight_cross_domain_lookback_days"
DEFAULT_INSIGHT_CROSS_DOMAIN_LOOKBACK_DAYS = "90"

INSIGHT_STALE_AFTER_DAYS_KEY = "insight_stale_after_days"
DEFAULT_INSIGHT_STALE_AFTER_DAYS = "7"

# ----- What-If Simulator module thresholds -----
# Same _KEY/DEFAULT_ + typed-getter pattern. Bounds the "unusual but valid" soft-warn tier —
# see services/whatif_calculations.py's two-tier guardrail design.

WHATIF_REASONABLE_CHANGE_PCT_BOUND_KEY = "whatif_reasonable_change_pct_bound"
DEFAULT_WHATIF_REASONABLE_CHANGE_PCT_BOUND = "50"

# ----- Administration module: company/display settings -----
# Same _KEY/DEFAULT_ pattern, but these are string values (company name, currency, unit system,
# date format, timezone, default units) rather than numeric thresholds — read with
# get_setting() directly (no float/int cast), validated at the write boundary in
# routers/settings.py's ALLOWED_VALUES (for the enum-like ones) rather than here.

COMPANY_NAME_KEY = "company_name"
DEFAULT_COMPANY_NAME = "OG-PIOS"

DEFAULT_CURRENCY_KEY = "default_currency"
DEFAULT_DEFAULT_CURRENCY = "USD"

UNIT_SYSTEM_KEY = "unit_system"
DEFAULT_UNIT_SYSTEM = "imperial"

DATE_FORMAT_KEY = "date_format"
DEFAULT_DATE_FORMAT = "YYYY-MM-DD"

TIMEZONE_KEY = "timezone"
DEFAULT_TIMEZONE = "UTC"

DEFAULT_PRODUCTION_UNIT_KEY = "default_production_unit"
DEFAULT_DEFAULT_PRODUCTION_UNIT = "bopd"

DEFAULT_GAS_UNIT_KEY = "default_gas_unit"
DEFAULT_DEFAULT_GAS_UNIT = "mscfd"

DEFAULT_VOLUME_UNIT_KEY = "default_volume_unit"
DEFAULT_DEFAULT_VOLUME_UNIT = "bbl"


def get_setting(db: Session, key: str, default: str) -> str:
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return setting.value if setting is not None else default


def get_boe_gas_factor(db: Session) -> float:
    return float(get_setting(db, BOE_GAS_FACTOR_KEY, DEFAULT_BOE_GAS_FACTOR))


def get_equipment_health_hours_threshold(db: Session) -> float:
    return float(
        get_setting(
            db, EQUIPMENT_HEALTH_HOURS_THRESHOLD_KEY, DEFAULT_EQUIPMENT_HEALTH_HOURS_THRESHOLD
        )
    )


def get_maintenance_schedule_lookahead_days(db: Session) -> int:
    return int(
        float(
            get_setting(
                db,
                MAINTENANCE_SCHEDULE_LOOKAHEAD_DAYS_KEY,
                DEFAULT_MAINTENANCE_SCHEDULE_LOOKAHEAD_DAYS,
            )
        )
    )


def get_alert_production_below_target_pct(db: Session) -> float:
    return float(
        get_setting(db, ALERT_PRODUCTION_BELOW_TARGET_PCT_KEY, DEFAULT_ALERT_PRODUCTION_BELOW_TARGET_PCT)
    )


def get_alert_production_decline_pct(db: Session) -> float:
    return float(get_setting(db, ALERT_PRODUCTION_DECLINE_PCT_KEY, DEFAULT_ALERT_PRODUCTION_DECLINE_PCT))


def get_alert_production_unusual_change_pct(db: Session) -> float:
    return float(
        get_setting(
            db, ALERT_PRODUCTION_UNUSUAL_CHANGE_PCT_KEY, DEFAULT_ALERT_PRODUCTION_UNUSUAL_CHANGE_PCT
        )
    )


def get_alert_equipment_health_attention_threshold(db: Session) -> float:
    return float(
        get_setting(
            db,
            ALERT_EQUIPMENT_HEALTH_ATTENTION_THRESHOLD_KEY,
            DEFAULT_ALERT_EQUIPMENT_HEALTH_ATTENTION_THRESHOLD,
        )
    )


def get_alert_equipment_health_critical_threshold(db: Session) -> float:
    return float(
        get_setting(
            db,
            ALERT_EQUIPMENT_HEALTH_CRITICAL_THRESHOLD_KEY,
            DEFAULT_ALERT_EQUIPMENT_HEALTH_CRITICAL_THRESHOLD,
        )
    )


def get_alert_maintenance_repeated_events_count(db: Session) -> int:
    return int(
        float(
            get_setting(
                db,
                ALERT_MAINTENANCE_REPEATED_EVENTS_COUNT_KEY,
                DEFAULT_ALERT_MAINTENANCE_REPEATED_EVENTS_COUNT,
            )
        )
    )


def get_alert_maintenance_repeated_events_window_days(db: Session) -> int:
    return int(
        float(
            get_setting(
                db,
                ALERT_MAINTENANCE_REPEATED_EVENTS_WINDOW_DAYS_KEY,
                DEFAULT_ALERT_MAINTENANCE_REPEATED_EVENTS_WINDOW_DAYS,
            )
        )
    )


def get_alert_production_loss_high_threshold_bbl(db: Session) -> float:
    return float(
        get_setting(
            db,
            ALERT_PRODUCTION_LOSS_HIGH_THRESHOLD_BBL_KEY,
            DEFAULT_ALERT_PRODUCTION_LOSS_HIGH_THRESHOLD_BBL,
        )
    )


def get_alert_production_loss_repeated_events_count(db: Session) -> int:
    return int(
        float(
            get_setting(
                db,
                ALERT_PRODUCTION_LOSS_REPEATED_EVENTS_COUNT_KEY,
                DEFAULT_ALERT_PRODUCTION_LOSS_REPEATED_EVENTS_COUNT,
            )
        )
    )


def get_alert_production_loss_repeated_events_window_days(db: Session) -> int:
    return int(
        float(
            get_setting(
                db,
                ALERT_PRODUCTION_LOSS_REPEATED_EVENTS_WINDOW_DAYS_KEY,
                DEFAULT_ALERT_PRODUCTION_LOSS_REPEATED_EVENTS_WINDOW_DAYS,
            )
        )
    )


def get_alert_downtime_high_threshold_hours(db: Session) -> float:
    return float(
        get_setting(
            db, ALERT_DOWNTIME_HIGH_THRESHOLD_HOURS_KEY, DEFAULT_ALERT_DOWNTIME_HIGH_THRESHOLD_HOURS
        )
    )


def get_alert_high_lost_revenue_threshold_usd(db: Session) -> float:
    return float(
        get_setting(
            db,
            ALERT_HIGH_LOST_REVENUE_THRESHOLD_USD_KEY,
            DEFAULT_ALERT_HIGH_LOST_REVENUE_THRESHOLD_USD,
        )
    )


def get_alert_high_operating_cost_threshold_usd(db: Session) -> float:
    return float(
        get_setting(
            db,
            ALERT_HIGH_OPERATING_COST_THRESHOLD_USD_KEY,
            DEFAULT_ALERT_HIGH_OPERATING_COST_THRESHOLD_USD,
        )
    )


def get_alert_high_operating_cost_threshold_ngn(db: Session) -> float:
    return float(
        get_setting(
            db,
            ALERT_HIGH_OPERATING_COST_THRESHOLD_NGN_KEY,
            DEFAULT_ALERT_HIGH_OPERATING_COST_THRESHOLD_NGN,
        )
    )


def get_alert_cost_per_bbl_increase_pct(db: Session) -> float:
    return float(
        get_setting(db, ALERT_COST_PER_BBL_INCREASE_PCT_KEY, DEFAULT_ALERT_COST_PER_BBL_INCREASE_PCT)
    )


def get_alert_cost_per_boe_increase_pct(db: Session) -> float:
    return float(
        get_setting(db, ALERT_COST_PER_BOE_INCREASE_PCT_KEY, DEFAULT_ALERT_COST_PER_BOE_INCREASE_PCT)
    )


def get_alert_margin_decline_pct(db: Session) -> float:
    return float(get_setting(db, ALERT_MARGIN_DECLINE_PCT_KEY, DEFAULT_ALERT_MARGIN_DECLINE_PCT))


def get_alert_high_maintenance_cost_multiplier(db: Session) -> float:
    return float(
        get_setting(
            db,
            ALERT_HIGH_MAINTENANCE_COST_MULTIPLIER_KEY,
            DEFAULT_ALERT_HIGH_MAINTENANCE_COST_MULTIPLIER,
        )
    )


def get_alert_high_financial_impact_threshold_usd(db: Session) -> float:
    return float(
        get_setting(
            db,
            ALERT_HIGH_FINANCIAL_IMPACT_THRESHOLD_USD_KEY,
            DEFAULT_ALERT_HIGH_FINANCIAL_IMPACT_THRESHOLD_USD,
        )
    )


def get_insight_production_increase_pct(db: Session) -> float:
    return float(
        get_setting(db, INSIGHT_PRODUCTION_INCREASE_PCT_KEY, DEFAULT_INSIGHT_PRODUCTION_INCREASE_PCT)
    )


def get_insight_trend_window_months(db: Session) -> int:
    return int(
        float(get_setting(db, INSIGHT_TREND_WINDOW_MONTHS_KEY, DEFAULT_INSIGHT_TREND_WINDOW_MONTHS))
    )


def get_insight_well_comparison_ratio_threshold(db: Session) -> float:
    return float(
        get_setting(
            db,
            INSIGHT_WELL_COMPARISON_RATIO_THRESHOLD_KEY,
            DEFAULT_INSIGHT_WELL_COMPARISON_RATIO_THRESHOLD,
        )
    )


def get_insight_maintenance_frequency_increase_multiplier(db: Session) -> float:
    return float(
        get_setting(
            db,
            INSIGHT_MAINTENANCE_FREQUENCY_INCREASE_MULTIPLIER_KEY,
            DEFAULT_INSIGHT_MAINTENANCE_FREQUENCY_INCREASE_MULTIPLIER,
        )
    )


def get_insight_high_maintenance_cost_vs_production_threshold_usd(db: Session) -> float:
    return float(
        get_setting(
            db,
            INSIGHT_HIGH_MAINTENANCE_COST_VS_PRODUCTION_THRESHOLD_USD_KEY,
            DEFAULT_INSIGHT_HIGH_MAINTENANCE_COST_VS_PRODUCTION_THRESHOLD_USD,
        )
    )


def get_insight_cross_domain_lookback_days(db: Session) -> int:
    return int(
        float(
            get_setting(
                db, INSIGHT_CROSS_DOMAIN_LOOKBACK_DAYS_KEY, DEFAULT_INSIGHT_CROSS_DOMAIN_LOOKBACK_DAYS
            )
        )
    )


def get_insight_stale_after_days(db: Session) -> int:
    return int(
        float(get_setting(db, INSIGHT_STALE_AFTER_DAYS_KEY, DEFAULT_INSIGHT_STALE_AFTER_DAYS))
    )


def get_whatif_reasonable_change_pct_bound(db: Session) -> float:
    return float(
        get_setting(
            db, WHATIF_REASONABLE_CHANGE_PCT_BOUND_KEY, DEFAULT_WHATIF_REASONABLE_CHANGE_PCT_BOUND
        )
    )


def get_company_name(db: Session) -> str:
    return get_setting(db, COMPANY_NAME_KEY, DEFAULT_COMPANY_NAME)


def get_default_currency(db: Session) -> str:
    return get_setting(db, DEFAULT_CURRENCY_KEY, DEFAULT_DEFAULT_CURRENCY)


def get_unit_system(db: Session) -> str:
    return get_setting(db, UNIT_SYSTEM_KEY, DEFAULT_UNIT_SYSTEM)


def get_date_format(db: Session) -> str:
    return get_setting(db, DATE_FORMAT_KEY, DEFAULT_DATE_FORMAT)


def get_timezone(db: Session) -> str:
    return get_setting(db, TIMEZONE_KEY, DEFAULT_TIMEZONE)


def get_default_production_unit(db: Session) -> str:
    return get_setting(db, DEFAULT_PRODUCTION_UNIT_KEY, DEFAULT_DEFAULT_PRODUCTION_UNIT)


def get_default_gas_unit(db: Session) -> str:
    return get_setting(db, DEFAULT_GAS_UNIT_KEY, DEFAULT_DEFAULT_GAS_UNIT)


def get_default_volume_unit(db: Session) -> str:
    return get_setting(db, DEFAULT_VOLUME_UNIT_KEY, DEFAULT_DEFAULT_VOLUME_UNIT)
