from html.parser import HTMLParser

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import JobScore

MAX_STORED_DESCRIPTION = 1500

PRIORITY_BY_SOURCE = {
    "linkedin_email": 1,
    "extension": 1,
    "manual": 1,
    "weworkremotely": 0,
    "remoteok": 0,
    "remotive": 0,
}

BLOCK_TAGS = {
    "p", "br", "div", "li", "ul", "ol", "tr", "td", "th", "table",
    "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
}
SKIP_TAGS = {"script", "style"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        elif tag in BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            if self.skip_depth > 0:
                self.skip_depth -= 1
        elif tag in BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data):
        if self.skip_depth == 0:
            self.parts.append(data)


def strip_html(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return " ".join("".join(parser.parts).split())


def clean_description(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = strip_html(value)[:MAX_STORED_DESCRIPTION].strip()
    return cleaned or None


def priority_for_source(source: str) -> int:
    return PRIORITY_BY_SOURCE[source]


def get_thresholds(db: Session) -> tuple[int, int]:
    rows = db.execute(
        text("select key, value from settings where key in ('apply_threshold', 'maybe_threshold')")
    ).all()
    values = {key: value for key, value in rows}
    apply_threshold = values.get("apply_threshold")
    maybe_threshold = values.get("maybe_threshold")
    valid = all(
        isinstance(item, int) and not isinstance(item, bool)
        for item in (apply_threshold, maybe_threshold)
    )
    if not valid:
        raise HTTPException(status_code=500, detail="Verdict thresholds are not configured")
    return apply_threshold, maybe_threshold


def verdict_for(score: int | None, apply_threshold: int, maybe_threshold: int) -> str | None:
    if score is None:
        return None
    if score >= apply_threshold:
        return "apply"
    if score >= maybe_threshold:
        return "maybe"
    return "skip"


def latest_scores():
    ranked = select(
        JobScore.job_id.label("job_id"),
        JobScore.score.label("score"),
        func.row_number()
        .over(
            partition_by=JobScore.job_id,
            order_by=(JobScore.scored_at.desc(), JobScore.id.desc()),
        )
        .label("rn"),
    ).subquery()
    return select(ranked.c.job_id, ranked.c.score).where(ranked.c.rn == 1).subquery()


def latest_score_for_job(db: Session, job_id: int) -> int | None:
    return db.scalar(
        select(JobScore.score)
        .where(JobScore.job_id == job_id)
        .order_by(JobScore.scored_at.desc(), JobScore.id.desc())
        .limit(1)
    )
