"""Reports — converts data already produced by every other OG-PIOS module into Daily/Weekly/
Monthly/What-If reports. Deterministic calculation always runs first
(services/report_calculations.py, which never imports an AI provider); the optional narrative
flag only ever phrases already-computed figures, exactly like AI Insights' daily brief/
management summary and What-If's `/compare?narrative=true`.

A saved `Report.results` is a **frozen snapshot** (see models/reporting.py's docstring) — GET
never recomputes; only `/regenerate` does.
"""

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.field import Facility, Field, Well
from app.models.equipment import Equipment
from app.models.reporting import Report
from app.models.user import User
from app.routers.what_if import _get_scenario_or_404
from app.schemas.reports import (
    ExportFormat,
    PreviewRequest,
    PreviewResponse,
    ReportCreate,
    ReportFilters,
    ReportListItem,
    ReportListResponse,
    ReportRead,
    ReportTypeInfo,
    ReportTypesResponse,
    ReportUpdate,
)
from app.services.ai_providers.base import AIProvider, StructuredPrompt
from app.services.ai_providers.factory import get_ai_provider_dependency
from app.services.audit import AuditAction, record_audit_event
from app.services.rate_limit import rate_limiter
from app.services.report_calculations import (
    REPORT_CALCULATION_VERSION,
    REPORT_DISCLAIMER,
    REPORT_TYPES,
    ReportFilterValues,
    build_report,
    default_sections,
)
from app.services.report_export import build_csv_export, build_pdf_export

router = APIRouter(prefix="/reports", tags=["reports"])

NON_VIEWER_ROLES = (
    "Administrator",
    "Production Operator",
    "Production Engineer",
    "Maintenance Engineer",
    "Management",
    "Analyst",
)

SORTABLE_FIELDS = {
    "name": Report.name,
    "created_at": Report.created_at,
    "updated_at": Report.updated_at,
    "last_generated_at": Report.last_generated_at,
}


def _to_datetime(d: date | None, *, end_of_day: bool = False) -> datetime | None:
    if d is None:
        return None
    t = time.max if end_of_day else time.min
    return datetime.combine(d, t, tzinfo=timezone.utc)


def _validate_scope(db: Session, filters: ReportFilters) -> None:
    if filters.date_from and filters.date_to and filters.date_from > filters.date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date_from must be on or before date_to")
    if filters.field_id is not None and db.get(Field, filters.field_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    if filters.facility_id is not None and db.get(Facility, filters.facility_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    if filters.well_id is not None and db.get(Well, filters.well_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Well not found")
    if filters.equipment_id is not None and db.get(Equipment, filters.equipment_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")
    if filters.scenario_id is not None:
        _get_scenario_or_404(db, filters.scenario_id)


def _run(
    db: Session,
    user: User,
    report_type: str,
    filters: ReportFilters,
    sections: list[str] | None,
    narrative: bool,
    provider: AIProvider,
) -> dict:
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown report_type: {report_type}")
    filter_values = ReportFilterValues.from_dict(filters.model_dump(exclude_none=True))
    results = build_report(db, user, report_type, filter_values, sections)

    if narrative and results.get("sections"):
        prompt = StructuredPrompt(
            task=f"Write a concise narrative summary of this {REPORT_TYPES[report_type]['label']} for a management/engineering audience.",
            data={key: section for key, section in results["sections"].items() if key != "_traceability"},
            time_period=f"{filters.date_from} to {filters.date_to}" if filters.date_from and filters.date_to else None,
        )
        interpretation = provider.interpret(prompt)
        results["ai_narrative"] = interpretation.text
        results["ai_narrative_provider"] = interpretation.provider

    return results


# ----- Query helpers -----


def _report_query(db: Session):
    return db.query(Report).options(joinedload(Report.generated_by))


def _get_report_or_404(db: Session, id: int) -> Report:
    report = _report_query(db).filter(Report.id == id).first()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


def _build_list_item(report: Report) -> ReportListItem:
    return ReportListItem(
        id=report.id,
        report_type=report.report_type,
        name=report.name,
        description=report.description,
        created_by_id=report.generated_by_id,
        created_by_name=report.generated_by.full_name if report.generated_by else None,
        period_start=report.period_start,
        period_end=report.period_end,
        calculation_version=report.calculation_version,
        status=report.status,
        last_generated_at=report.last_generated_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
        has_results=report.results is not None,
    )


def _build_read(report: Report) -> ReportRead:
    item = _build_list_item(report)
    return ReportRead(
        **item.model_dump(),
        filters=report.filters or {},
        sections=report.sections or [],
        results=report.results,
        disclaimer_text=REPORT_DISCLAIMER,
    )


# ----- Types / preview (must come before /{id}) -----


@router.get("/types", response_model=ReportTypesResponse)
def get_report_types(
    current_user: User = Depends(get_current_user),
) -> ReportTypesResponse:
    return ReportTypesResponse(
        types=[
            ReportTypeInfo(id=key, label=meta["label"], sections=meta["sections"])
            for key, meta in REPORT_TYPES.items()
        ]
    )


@router.post("/preview", response_model=PreviewResponse)
def preview_report(
    payload: PreviewRequest,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider_dependency),
    current_user: User = Depends(get_current_user),
) -> PreviewResponse:
    """Ad-hoc run — nothing persisted. The Report Builder's live-preview step before saving."""
    _validate_scope(db, payload.filters)
    results = _run(db, current_user, payload.report_type, payload.filters, payload.sections, payload.narrative, provider)
    return PreviewResponse(report_type=payload.report_type, calculation_version=REPORT_CALCULATION_VERSION, results=results)


# ----- List / detail -----


@router.get("", response_model=ReportListResponse)
def list_reports(
    search: str | None = None,
    report_type: str | None = None,
    created_by_id: int | None = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportListResponse:
    query = _report_query(db)

    if search:
        query = query.filter(Report.name.ilike(f"%{search}%"))
    if report_type:
        query = query.filter(Report.report_type == report_type)
    if created_by_id:
        query = query.filter(Report.generated_by_id == created_by_id)

    total = query.count()

    sort_column = SORTABLE_FIELDS.get(sort, Report.created_at)
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()
    query = query.order_by(sort_column)

    records = query.offset((page - 1) * page_size).limit(page_size).all()
    return ReportListResponse(items=[_build_list_item(r) for r in records], total=total, page=page, page_size=page_size)


@router.get("/{id}", response_model=ReportRead)
def get_report(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportRead:
    return _build_read(_get_report_or_404(db, id))


@router.post("", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider_dependency),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> ReportRead:
    _validate_scope(db, payload.filters)
    results = _run(db, current_user, payload.report_type, payload.filters, payload.sections, payload.narrative, provider)
    now = datetime.now(timezone.utc)

    record = Report(
        report_type=payload.report_type,
        name=payload.name,
        description=payload.description,
        period_start=_to_datetime(payload.filters.date_from),
        period_end=_to_datetime(payload.filters.date_to, end_of_day=True),
        filters=payload.filters.model_dump(mode="json", exclude_none=True),
        sections=payload.sections or default_sections(payload.report_type),
        results=results,
        calculation_version=REPORT_CALCULATION_VERSION,
        status="generated",
        last_generated_at=now,
        generated_by_id=current_user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    record_audit_event(
        db, current_user, AuditAction.REPORT_GENERATED, "report", resource_id=record.id,
        details=f"Generated report '{record.name}' ({record.report_type})",
    )
    return _build_read(_get_report_or_404(db, record.id))


@router.put("/{id}", response_model=ReportRead)
def update_report(
    id: int,
    payload: ReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> ReportRead:
    """Renames/updates description/filters/sections only — never silently recomputes `results`.
    Use `/regenerate` to explicitly recompute against current data."""
    record = _get_report_or_404(db, id)

    if payload.name is not None:
        record.name = payload.name
    if payload.description is not None:
        record.description = payload.description
    if payload.filters is not None:
        _validate_scope(db, payload.filters)
        record.filters = payload.filters.model_dump(mode="json", exclude_none=True)
        record.period_start = _to_datetime(payload.filters.date_from)
        record.period_end = _to_datetime(payload.filters.date_to, end_of_day=True)
    if payload.sections is not None:
        record.sections = payload.sections

    db.commit()
    db.refresh(record)
    return _build_read(_get_report_or_404(db, record.id))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> None:
    record = _get_report_or_404(db, id)
    db.delete(record)
    db.commit()


@router.post("/{id}/regenerate", response_model=ReportRead)
def regenerate_report(
    id: int,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider_dependency),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> ReportRead:
    record = _get_report_or_404(db, id)
    filters = ReportFilters(**(record.filters or {}))
    narrative = bool((record.results or {}).get("ai_narrative"))

    results = _run(db, current_user, record.report_type, filters, record.sections, narrative, provider)
    record.results = results
    record.calculation_version = REPORT_CALCULATION_VERSION
    record.status = "generated"
    record.last_generated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(record)
    return _build_read(_get_report_or_404(db, record.id))


# ----- Export -----


@router.get("/{id}/export")
def export_report(
    id: int,
    format: ExportFormat = Query("csv"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Streams from the report's STORED results only — never recomputes, matching the frozen-
    snapshot design; regenerate the report first if you want current-data figures exported."""
    record = _get_report_or_404(db, id)
    if record.results is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report has not been generated yet")

    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in record.name) or "report"

    if format == "pdf":
        pdf_bytes = build_pdf_export(record)
        return StreamingResponse(
            iter([pdf_bytes]), media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={safe_name}.pdf"},
        )

    return StreamingResponse(
        build_csv_export(record), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={safe_name}.csv"},
    )
