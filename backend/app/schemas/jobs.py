from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Source = Literal["weworkremotely", "remoteok", "remotive", "linkedin_email", "extension", "manual"]
CreatableSource = Literal["manual", "extension"]
WorkMode = Literal["remote", "hybrid", "on_site"]
PipelineStatus = Literal["new", "filtered_out", "scored", "error"]
Verdict = Literal["apply", "maybe", "skip"]


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source: CreatableSource
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2000)
    description: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=200)
    work_mode: WorkMode | None = None
    published: datetime | None = None

    @field_validator("url")
    @classmethod
    def check_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
            raise ValueError("URL must start with http:// or https:// and include a host")
        return value


class JobUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    company: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=200)
    work_mode: WorkMode | None = None

    @model_validator(mode="after")
    def check_fields(self) -> "JobUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for name in ("title", "company"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    title: str
    company: str | None
    url: str
    url_normalized: str
    description: str | None
    location: str | None
    work_mode: str | None
    published: datetime | None
    priority: int
    pipeline_status: str
    filter_reason: str | None
    opened_at: datetime | None
    created_at: datetime
    score: int | None = None
    verdict: Verdict | None = None


class JobList(BaseModel):
    items: list[JobOut]
    total: int
    limit: int
    offset: int
