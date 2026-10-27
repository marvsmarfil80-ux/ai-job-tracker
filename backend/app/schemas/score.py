from pydantic import BaseModel


class TitleFilterSummary(BaseModel):
    checked: int
    filtered_out: int
    passed: int


class CapInfo(BaseModel):
    limit: int
    used_before: int
    remaining_after: int


class ScoreRunResponse(BaseModel):
    requested: int
    attempted: int
    scored: int
    failed: int
    errored: int
    stopped_reason: str | None
    cap: CapInfo
    title_filter: TitleFilterSummary