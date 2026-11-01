import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_SENDER_CHARS = 200
SENDER_PATTERN = re.compile(
    r"[a-z0-9][a-z0-9._%+\-]{0,63}@(?:[a-z0-9\-]{1,63}\.)+[a-z]{2,24}"
)


class AllowedSenderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sender: str = Field(strict=True, min_length=1, max_length=MAX_SENDER_CHARS)
    kind: Literal["job_alert", "application"]

    @field_validator("sender")
    @classmethod
    def check_sender(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) > MAX_SENDER_CHARS or not SENDER_PATTERN.fullmatch(cleaned):
            raise ValueError(
                "sender must be one email address without spaces or search operators"
            )
        return cleaned


class AllowedSenderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(strict=True)


class AllowedSenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender: str
    kind: str
    enabled: bool


class AllowedSenderList(BaseModel):
    items: list[AllowedSenderOut]
    total: int