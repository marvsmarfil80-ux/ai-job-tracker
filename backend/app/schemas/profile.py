from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_CONTENT_CHARS = 2000


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(strict=True)

    @field_validator("content")
    @classmethod
    def check_content(cls, value):
        if "\x00" in value:
            raise ValueError("content must not contain NUL characters")
        stripped = value.strip()
        if not 1 <= len(stripped) <= MAX_CONTENT_CHARS:
            raise ValueError(f"content must be 1 to {MAX_CONTENT_CHARS} characters")
        return stripped


class Redactions(BaseModel):
    emails: int
    phones: int
    lines: int


class ProfileOut(BaseModel):
    content: str
    updated_at: datetime | None
    char_count: int
    groq_view: str
    redactions: Redactions
    warnings: list[str]
