from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationOut(BaseModel):
    id: int
    type: str
    message: str
    link: str | None
    is_read: bool
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int
    limit: int
    offset: int


class NotificationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_read: bool = Field(strict=True)