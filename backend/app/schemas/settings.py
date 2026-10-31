from typing import Any

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_REGEX_LENGTH = 500
MAX_KEYWORDS = 50
MAX_KEYWORD_LENGTH = 50


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_score_cap: int | None = Field(default=None, strict=True, ge=1, le=300)
    apply_threshold: int | None = Field(default=None, strict=True, ge=1, le=100)
    maybe_threshold: int | None = Field(default=None, strict=True, ge=0, le=99)
    title_exclude_regex: str | None = Field(default=None, strict=True)
    title_include_keywords: list[str] | None = Field(default=None, strict=True)
    scheduler_enabled: bool | None = Field(default=None, strict=True)
    hunt_interval_hours: int | None = Field(default=None, strict=True, ge=1, le=24)
    score_interval_minutes: int | None = Field(default=None, strict=True, ge=5, le=240)
    score_batch_limit: int | None = Field(default=None, strict=True, ge=1, le=20)
    followup_reminders_enabled: bool | None = Field(default=None, strict=True)

    @field_validator("title_exclude_regex")
    @classmethod
    def check_regex(cls, value):
        if value is None:
            return value
        if not value.strip() or len(value) > MAX_REGEX_LENGTH:
            raise ValueError(
                f"title_exclude_regex must be 1 to {MAX_REGEX_LENGTH} characters"
            )
        try:
            re.compile(value, re.IGNORECASE)
        except re.error:
            raise ValueError("title_exclude_regex is not a valid regular expression")
        return value

    @field_validator("title_include_keywords")
    @classmethod
    def check_keywords(cls, value):
        if value is None:
            return value
        if not 1 <= len(value) <= MAX_KEYWORDS:
            raise ValueError(
                f"title_include_keywords must contain 1 to {MAX_KEYWORDS} items"
            )
        cleaned = []
        seen = set()
        for item in value:
            stripped = item.strip()
            if not 1 <= len(stripped) <= MAX_KEYWORD_LENGTH:
                raise ValueError(
                    f"Each keyword must be 1 to {MAX_KEYWORD_LENGTH} characters"
                )
            lowered = stripped.lower()
            if lowered in seen:
                raise ValueError("title_include_keywords must not contain duplicates")
            seen.add(lowered)
            cleaned.append(stripped)
        return cleaned

    @model_validator(mode="after")
    def check_body(self):
        provided = self.model_fields_set
        if not provided:
            raise ValueError("Request body must contain at least one setting")
        for name in provided:
            if getattr(self, name) is None:
                raise ValueError(f"Setting {name} must not be null")
        return self


class SettingOut(BaseModel):
    value: Any
    description: str


class SettingsOut(BaseModel):
    settings: dict[str, SettingOut]