from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

MAX_KEYWORDS = 20
MAX_KEYWORD_LENGTH = 50


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    badge: str
    enabled: bool
    keywords: list[str]
    max_runs_per_day: int | None
    last_run_at: datetime | None
    effective_max_runs_per_day: int = 4
    runs_today: int = 0


class SourceList(BaseModel):
    items: list[SourceOut]
    total: int


class SourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool | None = None
    max_runs_per_day: StrictInt | None = Field(default=None, ge=1, le=4)
    keywords: list[str] | None = Field(default=None, max_length=MAX_KEYWORDS)

    @field_validator("keywords")
    @classmethod
    def check_keywords(cls, value):
        if value is None:
            return None
        cleaned: list[str] = []
        for item in value:
            keyword = item.strip()
            if not keyword or len(keyword) > MAX_KEYWORD_LENGTH or "\x00" in keyword:
                raise ValueError("Each keyword must be 1 to 50 characters")
            if keyword not in cleaned:
                cleaned.append(keyword)
        return cleaned

    @model_validator(mode="after")
    def check_fields(self) -> "SourceUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self