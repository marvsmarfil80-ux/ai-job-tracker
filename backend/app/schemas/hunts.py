from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FeedSource = Literal["weworkremotely", "remoteok", "remotive"]


class HuntCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[FeedSource] | None = Field(default=None, min_length=1, max_length=3)

    @field_validator("sources")
    @classmethod
    def unique_sources(cls, value):
        if value is None:
            return None
        return list(dict.fromkeys(value))


class HuntStepOut(BaseModel):
    source: str
    status: str
    found: int
    new: int
    message: str | None


class HuntOut(BaseModel):
    id: int
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    total_new: int
    steps: list[HuntStepOut]


class HuntList(BaseModel):
    items: list[HuntOut]
    total: int
    limit: int
    offset: int