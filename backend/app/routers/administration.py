"""Administration module — Administrator-only end to end, including reads (see
`services/permissions.py` for why every other module's reads stay open to all roles while this
one doesn't: this module surfaces user PII, system configuration, and the full audit trail).

Role and permission management are read-only here by design — see `services/permissions.py`'s
module docstring. User *creation/editing/role-assignment* is fully functional and lives in
`routers/users.py`, not here.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.database import get_db
from app.deps import require_role
from app.models.reporting import AuditLog
from app.models.role import Role
from app.models.user import User
from app.schemas.administration import (
    AdminDashboard,
    AIConfig,
    AuditLogEntry,
    AuditLogListResponse,
    PermissionMatrixEntry,
    RecentAuditEvent,
    RoleCount,
    RoleRead,
    SystemHealth,
)
from app.schemas.user import UserListResponse, UserRead
from app.services.ai_providers.factory import get_ai_provider
from app.services.permissions import PERMISSION_MATRIX

router = APIRouter(
    prefix="/administration", tags=["administration"], dependencies=[Depends(require_role("Administrator"))]
)


@router.get("/dashboard", response_model=AdminDashboard)
def get_dashboard(db: Session = Depends(get_db)) -> AdminDashboard:
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0

    role_counts = (
        db.query(Role.name, func.count(User.id))
        .outerjoin(User, User.role_id == Role.id)
        .group_by(Role.name)
        .order_by(Role.name)
        .all()
    )

    recent = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
        .limit(5)
        .all()
    )

    settings = get_settings()
    ai_provider = get_ai_provider(settings)

    return AdminDashboard(
        total_users=total_users,
        active_users=active_users,
        inactive_users=total_users - active_users,
        roles=[RoleCount(role_name=name, user_count=count) for name, count in role_counts],
        recent_activity=[
            RecentAuditEvent(
                id=event.id,
                action=event.action,
                entity_type=event.entity_type,
                user_email=event.user.email if event.user else None,
                status=event.status,
                created_at=event.created_at,
            )
            for event in recent
        ],
        system_status="operational",
        configuration_status="ok",
        ai_provider_configured=ai_provider.is_configured,
    )


@router.get("/roles", response_model=list[RoleRead])
def list_roles(db: Session = Depends(get_db)) -> list[RoleRead]:
    rows = (
        db.query(Role.id, Role.name, Role.description, func.count(User.id))
        .outerjoin(User, User.role_id == Role.id)
        .group_by(Role.id, Role.name, Role.description)
        .order_by(Role.name)
        .all()
    )
    return [
        RoleRead(id=id_, name=name, description=description, user_count=count)
        for id_, name, description, count in rows
    ]


@router.get("/permissions", response_model=list[PermissionMatrixEntry])
def list_permissions() -> list[PermissionMatrixEntry]:
    return [
        PermissionMatrixEntry(module=e.module, action=e.action, roles=list(e.roles), note=e.note)
        for e in PERMISSION_MATRIX
    ]


@router.get("/users", response_model=UserListResponse)
def list_administration_users(
    search: str | None = Query(None, description="Match against email or full name"),
    role_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> UserListResponse:
    """The Administration module's own paginated, fully-filterable user list — separate from
    the unpaginated `GET /users` used by the Maintenance technician dropdown, which is
    deliberately left untouched by this module."""
    query = db.query(User).options(joinedload(User.role))
    if search:
        like = f"%{search}%"
        query = query.filter((User.email.ilike(like)) | (User.full_name.ilike(like)))
    if role_id is not None:
        query = query.filter(User.role_id == role_id)
    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))

    total = query.with_entities(func.count(User.id)).scalar() or 0
    rows = (
        query.order_by(User.full_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return UserListResponse(
        items=[UserRead.model_validate(u) for u in rows], total=total, page=page, page_size=page_size
    )


@router.get("/audit-log", response_model=AuditLogListResponse)
def list_audit_log(
    search: str | None = Query(None, description="Match against action or details"),
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    resource: str | None = Query(None, description="Matches entity_type"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    query = db.query(AuditLog).options(joinedload(AuditLog.user))
    if search:
        like = f"%{search}%"
        query = query.filter((AuditLog.action.ilike(like)) | (AuditLog.details.ilike(like)))
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource:
        query = query.filter(AuditLog.entity_type == resource)
    if date_from is not None:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to is not None:
        query = query.filter(AuditLog.created_at <= date_to)

    total = query.with_entities(func.count(AuditLog.id)).scalar() or 0
    rows = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AuditLogListResponse(
        items=[
            AuditLogEntry(
                id=e.id,
                action=e.action,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                details=e.details,
                status=e.status,
                metadata_json=e.metadata_json,
                user_id=e.user_id,
                user_email=e.user.email if e.user else None,
                created_at=e.created_at,
            )
            for e in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/audit-log/{id}", response_model=AuditLogEntry)
def get_audit_log_entry(id: int, db: Session = Depends(get_db)) -> AuditLogEntry:
    entry = db.query(AuditLog).options(joinedload(AuditLog.user)).filter(AuditLog.id == id).first()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit log entry not found")
    return AuditLogEntry(
        id=entry.id,
        action=entry.action,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        details=entry.details,
        status=entry.status,
        metadata_json=entry.metadata_json,
        user_id=entry.user_id,
        user_email=entry.user.email if entry.user else None,
        created_at=entry.created_at,
    )


@router.get("/system-health", response_model=SystemHealth)
def get_system_health(db: Session = Depends(get_db)) -> SystemHealth:
    settings = get_settings()

    try:
        db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception:
        database_status = "unavailable"

    ai_provider = get_ai_provider(settings)
    ai_status = "configured" if ai_provider.is_configured else "not configured (using deterministic fallback)"

    return SystemHealth(
        backend_status="running",
        database_status=database_status,
        api_status="ok",
        ai_provider_status=ai_status,
        app_version="0.1.0",
        environment=settings.environment,
    )


@router.get("/ai-config", response_model=AIConfig)
def get_ai_config(db: Session = Depends(get_db)) -> AIConfig:
    """Never touches `settings.openai_api_key` etc. — only the already-safe
    `provider_name`/`model`/`is_configured` surface of the resolved provider instance."""
    settings = get_settings()
    provider = get_ai_provider(settings)
    return AIConfig(
        provider=provider.provider_name,
        model=getattr(provider, "model", None),
        is_configured=provider.is_configured,
        status="configured" if provider.is_configured else "not configured — deterministic fallback active",
    )
