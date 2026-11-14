from pydantic import BaseModel, ConfigDict, Field


class ResumeRedactions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emails: int = Field(ge=0)
    phones: int = Field(ge=0)
    lines: int = Field(ge=0)
    urls: int = Field(ge=0)
    address_lines: int = Field(ge=0)


class ResumeDraftOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skills: list[str]
    draft_content: str
    pages: int = Field(ge=0)
    extracted_chars: int = Field(ge=0)
    truncated: bool
    redactions: ResumeRedactions
    dropped_skills: list[str]
    warnings: list[str]