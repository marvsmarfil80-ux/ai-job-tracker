from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.jobs import validate_http_url


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str = Field(min_length=1, max_length=2000)
    page_text: str = Field(min_length=1, max_length=4000)

    @field_validator("url")
    @classmethod
    def check_url(cls, value: str) -> str:
        return validate_http_url(value)


class ExtractResponse(BaseModel):
    title: str
    company: str | None
    description: str | None