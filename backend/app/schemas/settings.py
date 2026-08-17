from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    description: str | None = None
    updated_at: datetime


class SettingUpdate(BaseModel):
    value: str
