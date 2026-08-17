from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RoleCount(BaseModel):
    role_name: str
    user_count: int


class RecentAuditEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    entity_type: str | None
    user_email: str | None
    status: str
    created_at: datetime


class AdminDashboard(BaseModel):
    total_users: int
    active_users: int
    inactive_users: int
    roles: list[RoleCount]
    recent_activity: list[RecentAuditEvent]
    system_status: str
    configuration_status: str
    ai_provider_configured: bool


class RoleRead(BaseModel):
    id: int
    name: str
    description: str | None
    user_count: int


class PermissionMatrixEntry(BaseModel):
    module: str
    action: str
    roles: list[str]
    note: str | None = None


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    entity_type: str | None
    entity_id: int | None
    details: str | None
    status: str
    metadata_json: dict | None
    user_id: int | None
    user_email: str | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int


class SystemHealth(BaseModel):
    backend_status: str
    database_status: str
    api_status: str
    ai_provider_status: str
    app_version: str
    environment: str


class AIConfig(BaseModel):
    provider: str
    model: str | None
    is_configured: bool
    status: str
