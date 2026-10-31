import re
from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.applications import MAX_ID
from app.services.clock import manila_today

FollowUpStatus = Literal["pending", "completed"]

MAX_TITLE_LENGTH = 200
MIN_DUE_DATE = date(2020, 1, 1)
MAX_DUE_DAYS = 5 * 365 + 1
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FollowUpInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("due_date", mode="before", check_fields=False)
    @classmethod
    def require_iso_string(cls, value):
        if value is None:
            return value
        if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
            raise ValueError("due_date must be a date string in YYYY-MM-DD format")
        return value

    @field_validator("due_date", check_fields=False)
    @classmethod
    def check_range(cls, value):
        if value is None:
            return value
        if value < MIN_DUE_DATE:
            raise ValueError("due_date must not be before 2020-01-01")
        if value > manila_today() + timedelta(days=MAX_DUE_DAYS):
            raise ValueError("due_date must not be more than 5 years from today")
        return value


class FollowUpCreate(FollowUpInput):
    application_id: int = Field(strict=True, ge=1, le=MAX_ID)
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    due_date: date | None = None


class FollowUpUpdate(FollowUpInput):
    title: str | None = Field(default=None, min_length=1, max_length=MAX_TITLE_LENGTH)
    due_date: date | None = None
    status: FollowUpStatus | None = None

    @model_validator(mode="after")
    def check_fields(self) -> "FollowUpUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title cannot be null")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


class FollowUpOut(BaseModel):
    id: int
    application_id: int
    title: str
    due_date: date | None
    status: str
    completed_at: datetime | None
    created_at: datetime
    is_overdue: bool


class ApplicationSummary(BaseModel):
    application_id: int
    application_status: str
    job_title: str
    job_company: str | None


class FollowUpDetail(FollowUpOut):
    application: ApplicationSummary


class FollowUpList(BaseModel):
    items: list[FollowUpDetail]
    total: int
    limit: int
    offset: int