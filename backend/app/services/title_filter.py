import re
from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

EXCLUDE_REASON = "title matched exclude pattern"
NO_INCLUDE_REASON = "no include keyword in title"


@dataclass(frozen=True)
class FilterSettings:
    exclude: re.Pattern[str]
    include_keywords: tuple[str, ...]


def title_filter_reason(
    title: str,
    priority: int,
    settings: FilterSettings,
    extra_keywords: Sequence[str] = (),
) -> str | None:
    if priority >= 1:
        return None
    if settings.exclude.search(title):
        return EXCLUDE_REASON
    lowered = title.lower()
    extras = tuple(keyword.strip().lower() for keyword in extra_keywords if keyword.strip())
    if any(keyword in lowered for keyword in settings.include_keywords + extras):
        return None
    return NO_INCLUDE_REASON


def load_filter_settings(db: Session) -> FilterSettings:
    rows = db.execute(
        text(
            "select key, value from settings "
            "where key in ('title_exclude_regex', 'title_include_keywords')"
        )
    ).all()
    values = {key: value for key, value in rows}

    pattern = values.get("title_exclude_regex")
    if not isinstance(pattern, str) or not pattern.strip():
        raise HTTPException(
            status_code=500, detail="Setting title_exclude_regex is missing or invalid"
        )
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error:
        raise HTTPException(
            status_code=500,
            detail="Setting title_exclude_regex is not a valid regular expression",
        )

    keywords = values.get("title_include_keywords")
    if not isinstance(keywords, list) or not all(isinstance(item, str) for item in keywords):
        raise HTTPException(
            status_code=500, detail="Setting title_include_keywords must be a list of strings"
        )
    cleaned = tuple(item.strip().lower() for item in keywords if item.strip())
    if not cleaned:
        raise HTTPException(
            status_code=500,
            detail="Setting title_include_keywords must contain at least one keyword",
        )
    return FilterSettings(exclude=compiled, include_keywords=cleaned)


def apply_title_filter(db: Session) -> dict[str, int]:
    settings = load_filter_settings(db)
    rows = db.execute(
        text(
            "select j.id, j.title, j.priority, "
            "coalesce(s.keywords, array[]::text[]) as keywords "
            "from jobs j left join sources s on s.name = j.source "
            "where j.pipeline_status = 'new'"
        )
    ).all()

    updates = []
    for job_id, title, priority, keywords in rows:
        reason = title_filter_reason(title, priority, settings, keywords)
        if reason is not None:
            updates.append({"id": job_id, "reason": reason})

    if updates:
        db.execute(
            text(
                "update jobs set pipeline_status = 'filtered_out', filter_reason = :reason "
                "where id = :id and pipeline_status = 'new'"
            ),
            updates,
        )
    db.commit()
    return {
        "checked": len(rows),
        "filtered_out": len(updates),
        "passed": len(rows) - len(updates),
    }