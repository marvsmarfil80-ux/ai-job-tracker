from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.applications import MAX_ID
from app.schemas.score import CapInfo

EmailClass = Literal[
    "confirmation",
    "interview",
    "assessment",
    "info_request",
    "rejection",
    "offer",
]
EmailKind = Literal["job_alert", "application"]
EmailStatus = Literal["unprocessed", "processed", "error"]


class LinkedApplication(BaseModel):
    id: int
    status: str
    job_title: str
    company: str | None


class EmailOut(BaseModel):
    id: int
    kind: str
    status: str
    email_class: str | None = Field(default=None, serialization_alias="class")
    received_at: datetime
    sender: str
    subject: str | None
    snippet: str | None
    application: LinkedApplication | None


class EmailList(BaseModel):
    items: list[EmailOut]
    total: int
    limit: int
    offset: int


class EmailUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: int | None = Field(default=None, strict=True, ge=1, le=MAX_ID)

    @model_validator(mode="after")
    def check_body(self) -> "EmailUpdate":
        if "application_id" not in self.model_fields_set:
            raise ValueError("application_id must be provided")
        return self


class EmailProcessResponse(BaseModel):
    requested: int
    processed: int
    jobs_created: int
    jobs_duplicate: int
    classified: int
    auto_status_changed: int
    needs_review: int
    errored: int
    skipped_by_cap: int
    stopped_reason: str | None
    cap: CapInfo