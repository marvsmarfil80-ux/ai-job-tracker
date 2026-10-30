from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ApplicationStatus = Literal[
    "applied",
    "under_review",
    "assessment",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
]

MAX_ID = 9223372036854775807
MAX_NOTES_LENGTH = 2000


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    job_id: int = Field(strict=True, ge=1, le=MAX_ID)
    applied_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=MAX_NOTES_LENGTH)

    @field_validator("applied_at")
    @classmethod
    def check_applied_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("applied_at must include a timezone")
        if value > datetime.now(timezone.utc) + timedelta(days=1):
            raise ValueError("applied_at must not be more than 1 day in the future")
        return value


class ApplicationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: ApplicationStatus | None = None
    notes: str | None = Field(default=None, max_length=MAX_NOTES_LENGTH)

    @model_validator(mode="after")
    def check_fields(self) -> "ApplicationUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str | None
    url: str
    source: str


class ApplicationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: str | None
    to_status: str
    changed_at: datetime


class ApplicationOut(BaseModel):
    id: int
    job_id: int
    status: str
    applied_at: datetime | None
    notes: str | None
    job: JobSummary


class ApplicationDetail(ApplicationOut):
    events: list[ApplicationEventOut]


class ApplicationList(BaseModel):
    items: list[ApplicationOut]
    total: int
    limit: int
    offset: int



