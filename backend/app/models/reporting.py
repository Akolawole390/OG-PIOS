from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_path: Mapped[str | None] = mapped_column(String(500))
    generated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[int | None] = mapped_column()
    details: Mapped[str | None] = mapped_column(Text)

    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
