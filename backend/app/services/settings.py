import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

DESCRIPTIONS = {
    "daily_score_cap": "Maximum Groq scoring calls per day (UTC day).",
    "apply_threshold": "Scores at or above this value get the apply verdict.",
    "maybe_threshold": "Scores from this value up to apply_threshold get the maybe verdict; lower is skip.",
    "title_exclude_regex": "Case-insensitive regex; matching titles are filtered out before scoring.",
    "title_include_keywords": "A title must contain at least one of these keywords (except priority 1 jobs).",
    "scheduler_enabled": "Whether hunts and scoring run automatically.",
    "hunt_interval_hours": "Hours between automatic hunts (per-source daily limits still apply).",
    "score_interval_minutes": "Minutes between automatic scoring runs.",
    "score_batch_limit": "Maximum Groq calls per automatic scoring run.",
    "followup_reminders_enabled": "Whether overdue follow-up reminders are created (runs even when scheduler_enabled is false).",
    "email_auto_status_enabled": "Whether an email may automatically change an application status (false means notification only).",
    "email_auto_status_min_confidence": "Minimum classifier confidence (50 to 100) required for an automatic status change.",
    "email_classify_daily_cap": "Maximum Groq email classification calls per day (UTC day), separate from daily_score_cap.",
}

DEFAULTS = {
    "daily_score_cap": 150,
    "apply_threshold": 70,
    "maybe_threshold": 40,
    "scheduler_enabled": False,
    "hunt_interval_hours": 6,
    "score_interval_minutes": 30,
    "score_batch_limit": 10,
    "followup_reminders_enabled": True,
    "email_auto_status_enabled": True,
    "email_auto_status_min_confidence": 85,
    "email_classify_daily_cap": 30,
}

KEYS = tuple(DESCRIPTIONS)

SELECT_VALUES = "select key, value from settings where key = any(cast(:keys as text[]))"
UPSERT_VALUE = (
    "insert into settings (key, value) values (:key, cast(:value as jsonb)) "
    "on conflict (key) do update set value = excluded.value"
)


def read_values(db: Session, lock: bool = False) -> dict[str, Any]:
    query = SELECT_VALUES + (" for update" if lock else "")
    rows = db.execute(text(query), {"keys": list(KEYS)}).all()
    stored = {key: value for key, value in rows}
    values = {}
    for key in KEYS:
        if key in stored:
            values[key] = stored[key]
        elif key in DEFAULTS:
            values[key] = DEFAULTS[key]
        else:
            raise HTTPException(status_code=500, detail=f"Setting {key} is missing")
    return values


def present(values: dict[str, Any]) -> dict:
    return {
        "settings": {
            key: {"value": values[key], "description": DESCRIPTIONS[key]} for key in KEYS
        }
    }


def update_settings(db: Session, changes: dict[str, Any]) -> dict[str, Any]:
    current = read_values(db, lock=True)
    final = {**current, **changes}
    if final["apply_threshold"] <= final["maybe_threshold"]:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="apply_threshold must be greater than maybe_threshold",
        )
    for key, value in changes.items():
        db.execute(text(UPSERT_VALUE), {"key": key, "value": json.dumps(value)})
    db.commit()
    return final