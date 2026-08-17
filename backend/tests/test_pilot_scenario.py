"""End-to-end coverage for the pilot demo's core narrative: a well's production decline should,
on its own, flow through the real Alerts and AI Insights engines into a real Alert and a real
AI Insight for that well — the same mechanism the pilot guide's "investigate the decline" walk
walks a user through (docs/OGPIOS_PILOT_GUIDE.md), proven here without depending on the seed
script's random data. Nothing about the scenario is hand-fed to the engines — the alert/insight
below are whatever the real rule/insight engines decide from raw production numbers, same as
the CLAUDE.md guardrail requires ("Do not artificially force modules to produce conclusions").
"""

from datetime import date, timedelta

from app.models.ai import AIRecommendation, Alert
from app.models.production import ProductionRecord
from app.services.alert_rules import run_alert_rules
from app.services.insight_engine import run_insight_engine

TODAY = date.today()


def test_declining_well_flows_through_alerts_and_insights_end_to_end(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="PILOT-DEMO-01")

    # 30 days of production: steady for the first 24, then a sustained drop for the last 6 —
    # mirrors the pilot guide's "Well X experienced a sustained production decline" scenario.
    for i in range(30):
        record_date = TODAY - timedelta(days=29 - i)
        oil = 100.0 if record_date < TODAY - timedelta(days=6) else 45.0
        db_session.add(
            ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=oil, gas_mscfd=50.0)
        )
    db_session.commit()

    alert_result = run_alert_rules(db_session)
    assert alert_result.created >= 1

    decline_alerts = (
        db_session.query(Alert)
        .filter(Alert.well_id == well.id, Alert.alert_type == "production_decline")
        .all()
    )
    assert len(decline_alerts) == 1
    assert decline_alerts[0].severity in ("medium", "high", "critical")

    insight_result = run_insight_engine(db_session)
    assert insight_result.created >= 1

    well_insights = db_session.query(AIRecommendation).filter(AIRecommendation.well_id == well.id).all()
    assert len(well_insights) >= 1
    for insight in well_insights:
        # The standing AI/analytics-output guardrail (CLAUDE.md): every insight must carry a
        # non-empty disclaimer framing it as an estimate requiring engineering review.
        assert insight.disclaimer_text
