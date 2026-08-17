from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class SystemSetting(Base, TimestampMixin):
    """Generic admin-configurable key/value settings (e.g. BOE conversion factor).

    Deliberately generic rather than a dedicated column per setting, so future
    configuration values don't each require their own migration.
    """

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
