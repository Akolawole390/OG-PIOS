from datetime import date, datetime, timedelta, timezone

from app.models.ai import AIRecommendation
from app.models.production import ProductionRecord, ProductionTarget
from app.services.rate_limit import reset_rate_limits

TODAY = date.today()


def _make_open_insight(db_session, *, title, severity):
    now = datetime.now(timezone.utc)
    insight = AIRecommendation(
        insight_type="production_below_target",
        category="production",
        severity=severity,
        status="new",
        title=title,
        summary=f"Test insight: {title}",
        confidence_level="medium",
        dedup_key=f"test:{title}",
        generated_at=now,
        last_confirmed_at=now,
    )
    db_session.add(insight)
    db_session.commit()
    return insight


def _seed_below_target_well(db_session, make_field_facility_well, well_id="ORC-01-001"):
    _field, _facility, well = make_field_facility_well(well_id=well_id)
    for i in range(29):
        db_session.add(ProductionRecord(well_id=well.id, record_date=TODAY - timedelta(days=29 - i), oil_bopd=100.0, gas_mscfd=50.0))
    db_session.add(ProductionRecord(well_id=well.id, record_date=TODAY, oil_bopd=50.0, gas_mscfd=50.0))
    db_session.add(ProductionTarget(well_id=well.id, effective_date=TODAY - timedelta(days=60), oil_target_bopd=100.0))
    db_session.commit()
    return well


def test_assistant_still_answers_known_patterns_via_orchestrator(client, auth_headers):
    reset_rate_limits()
    headers = auth_headers("Analyst")
    response = client.post(
        "/ai-insights/assistant", json={"question": "What are the biggest production problems today?"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["answered_by"] == "deterministic"


def test_broad_why_question_auto_investigates_top_issue(client, db_session, auth_headers, make_field_facility_well):
    reset_rate_limits()
    well = _seed_below_target_well(db_session, make_field_facility_well)
    admin_headers = auth_headers("Administrator")
    client.post("/ai-insights/run", headers=admin_headers)

    response = client.post("/ai-insights/assistant", json={"question": "Why is production down?"}, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert well.well_id in body["answer"] or well.well_id in " ".join(s["source_label"] for s in body["sources"])
    assert len(body["sources"]) >= 1


def test_broad_question_with_no_open_insights_says_so(client, auth_headers):
    reset_rate_limits()
    headers = auth_headers("Analyst")
    response = client.post("/ai-insights/assistant", json={"question": "What needs attention right now?"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "no open insights are currently flagged" in body["answer"].lower()


def test_question_matching_neither_pattern_falls_through_to_general_answer(client, auth_headers):
    """Covers orchestrator.py's fallback branch (neither a known deterministic pattern nor a
    broad why/what's-wrong question) — it must behave exactly like the pre-orchestrator
    ai_assistant.answer_question, not error and not claim "no open insights"."""
    reset_rate_limits()
    headers = auth_headers("Analyst")
    response = client.post("/ai-insights/assistant", json={"question": "What is the capital of France?"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "no open insights are currently flagged" not in body["answer"].lower()
    assert "I can answer questions matching these patterns" in body["answer"]


def test_broad_question_picks_highest_severity_open_insight(client, db_session, auth_headers):
    """Covers _find_highest_priority_open_insight's severity ranking: with both a medium and a
    critical insight open, the critical one must be the one investigated — proving selection is
    driven by SEVERITY_RANK, not insertion/row order."""
    reset_rate_limits()
    _make_open_insight(db_session, title="MEDIUM-TEST-INSIGHT", severity="medium")
    _make_open_insight(db_session, title="CRITICAL-TEST-INSIGHT", severity="critical")

    headers = auth_headers("Analyst")
    response = client.post("/ai-insights/assistant", json={"question": "Why is production down?"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "CRITICAL-TEST-INSIGHT" in body["answer"]
    assert "MEDIUM-TEST-INSIGHT" not in body["answer"]
    assert any(s["source_label"] == "CRITICAL-TEST-INSIGHT" for s in body["sources"])
