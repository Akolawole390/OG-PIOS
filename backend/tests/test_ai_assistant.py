from datetime import date, timedelta

from app.models.economics import ProductionLoss
from app.models.equipment import DowntimeEvent
from app.services.ai_assistant import _extract_well_code, answer_question
from app.services.ai_providers.base import AIInterpretation, AIProvider, StructuredPrompt
from app.services.ai_providers.null_provider import NullProvider


def test_extract_well_code_finds_a_matching_code():
    assert _extract_well_code("Why is well PBF-03-003 underperforming?") == "PBF-03-003"


def test_extract_well_code_returns_none_when_absent():
    assert _extract_well_code("What are the biggest production problems today?") is None


def test_production_problems_question_reports_down_wells(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="AS-01")
    from datetime import datetime, timezone

    db_session.add(DowntimeEvent(well_id=well.id, start_time=datetime.now(timezone.utc), end_time=None))
    db_session.commit()

    answer = answer_question(db_session, "What are the biggest production problems today?", NullProvider())
    assert "AS-01" in answer.answer
    assert answer.answered_by == "deterministic"
    assert len(answer.sources) == 1


def test_no_production_problems_gives_a_clean_negative_answer(db_session):
    answer = answer_question(db_session, "What are the biggest production problems today?", NullProvider())
    assert "no active production outages" in answer.answer.lower()


def test_wells_lost_most_production_question(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="AS-02")
    db_session.add(ProductionLoss(loss_date=date.today(), well_id=well.id, estimated_bopd_lost=500.0))
    db_session.commit()

    answer = answer_question(db_session, "Which wells lost the most production this month?", NullProvider())
    assert "AS-02" in answer.answer
    assert "500.0" in answer.answer


def test_equipment_requires_attention_question(db_session, make_equipment):
    equipment = make_equipment(equipment_tag="AS-EQ-01", status="failed")
    answer = answer_question(db_session, "Which equipment requires attention?", NullProvider())
    assert "AS-EQ-01" in answer.answer


def test_why_underperforming_question_with_well_code(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="AS-03-001")
    answer = answer_question(db_session, "Why is well AS-03-001 underperforming?", NullProvider())
    assert "AS-03-001" in answer.answer


def test_why_underperforming_question_unknown_well_code(db_session):
    answer = answer_question(db_session, "Why is well ZZ-99-999 underperforming?", NullProvider())
    assert "no well" in answer.answer.lower()


def test_highest_cost_per_barrel_never_blends_currencies(db_session, make_field_facility_well):
    """The single most important test for this template: currencies must be reported
    independently, never compared by raw numeric magnitude across NGN and USD."""
    from app.models.economics import CommodityPrice, OperatingCost
    from app.models.production import ProductionRecord

    field_a, _facility_a, well_a = make_field_facility_well(well_id="AS-04")
    field_b, facility_b, well_b = make_field_facility_well(well_id="AS-05")

    today = date.today().replace(day=1)
    db_session.add(ProductionRecord(well_id=well_a.id, record_date=today, oil_bopd=10.0, gas_mscfd=0.0))
    db_session.add(ProductionRecord(well_id=well_b.id, record_date=today, oil_bopd=10.0, gas_mscfd=0.0))
    db_session.add(OperatingCost(cost_date=today, category="Energy", amount=1000.0, currency="NGN", field_id=field_a.id))
    db_session.add(OperatingCost(cost_date=today, category="Energy", amount=5.0, currency="USD", field_id=field_b.id))
    db_session.commit()

    answer = answer_question(db_session, "Which field has the highest cost per barrel?", NullProvider())
    assert "NGN" in answer.answer
    assert "USD" in answer.answer
    assert "never blended across currencies" in answer.answer.lower()


def test_unmatched_question_falls_back_to_ai_when_provider_configured(db_session):
    class FakeProvider(AIProvider):
        provider_name = "fake"

        def interpret(self, prompt: StructuredPrompt) -> AIInterpretation:
            return AIInterpretation(text="AI-generated open-ended answer.", provider="fake", model="fake-model")

        @property
        def is_configured(self) -> bool:
            return True

    answer = answer_question(db_session, "Tell me a joke about drilling rigs.", FakeProvider())
    assert answer.answered_by == "ai"
    assert answer.answer == "AI-generated open-ended answer."


def test_unmatched_question_with_no_provider_lists_known_patterns(db_session):
    answer = answer_question(db_session, "Tell me a joke about drilling rigs.", NullProvider())
    assert answer.answered_by == "deterministic"
    assert "biggest production problems" in answer.answer.lower()


def test_maintenance_overdue_question_reports_past_due_work_orders(db_session, make_equipment):
    from app.models.equipment import MaintenanceRecord

    equipment = make_equipment(equipment_tag="AS-EQ-OVERDUE")
    db_session.add(
        MaintenanceRecord(
            equipment_id=equipment.id,
            maintenance_type="preventive",
            status="scheduled",
            planned_completion_date=date.today() - timedelta(days=5),
        )
    )
    db_session.commit()

    answer = answer_question(db_session, "What maintenance is overdue?", NullProvider())
    assert "AS-EQ-OVERDUE" in answer.answer
    assert "1 maintenance work order" in answer.answer


def test_no_overdue_maintenance_gives_a_clean_negative_answer(db_session):
    answer = answer_question(db_session, "What maintenance is overdue?", NullProvider())
    assert "no maintenance work orders are currently overdue" in answer.answer.lower()


def test_completed_work_order_past_due_date_is_not_counted_as_overdue(db_session, make_equipment):
    """A completed/cancelled record keeps its old planned_completion_date forever — it must never
    be counted as overdue just because that date is in the past."""
    from app.models.equipment import MaintenanceRecord

    equipment = make_equipment(equipment_tag="AS-EQ-DONE")
    db_session.add(
        MaintenanceRecord(
            equipment_id=equipment.id,
            maintenance_type="preventive",
            status="completed",
            planned_completion_date=date.today() - timedelta(days=5),
        )
    )
    db_session.commit()

    answer = answer_question(db_session, "What maintenance is overdue?", NullProvider())
    assert "no maintenance work orders are currently overdue" in answer.answer.lower()


def test_equipment_reliability_question_reports_weakest_equipment(db_session, make_equipment):
    from datetime import datetime, timezone

    equipment = make_equipment(equipment_tag="AS-EQ-RELY")
    now = datetime.now(timezone.utc)
    db_session.add(DowntimeEvent(equipment_id=equipment.id, start_time=now - timedelta(days=200), end_time=now - timedelta(days=199)))
    db_session.add(DowntimeEvent(equipment_id=equipment.id, start_time=now - timedelta(days=100), end_time=now - timedelta(days=99)))
    db_session.commit()

    answer = answer_question(db_session, "Which equipment has the weakest reliability/integrity?", NullProvider())
    assert "AS-EQ-RELY" in answer.answer
    assert "availability" in answer.answer.lower()
    assert "MTBF" in answer.answer


def test_reliability_question_with_no_downtime_history_says_so(db_session, make_equipment):
    make_equipment(equipment_tag="AS-EQ-NODATA")
    answer = answer_question(db_session, "What is our maintenance integrity like?", NullProvider())
    assert "not enough recorded downtime history" in answer.answer.lower()
