import json
import time
from collections.abc import Callable
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine
from app.services.groq_client import (
    GroqAuthError,
    GroqRateLimited,
    GroqRequestError,
    GroqTransientError,
    call_groq,
)
from app.services.profile import get_profile_text
from app.services.scoring_prompt import (
    PROMPT_VERSION,
    ScoreValidationError,
    build_messages,
    parse_score_response,
)
from app.services.title_filter import apply_title_filter

LOCK_KEY = 5150001
COMPONENT = "scoring"
FAILED_PREFIX = "Groq call failed"
INVALID_OUTPUT_REASON = "scoring failed: invalid model output"
MAX_ATTEMPTS_PER_JOB = 2


def utc_day_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def load_daily_cap(db: Session) -> int:
    value = db.execute(
        text("select value from settings where key = 'daily_score_cap'")
    ).scalar_one_or_none()
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise HTTPException(
            status_code=500, detail="Setting daily_score_cap must be a positive integer"
        )
    return value


def count_used_today(db: Session) -> int:
    return db.execute(
        text(
            "select "
            "(select count(*) from job_scores where scored_at >= :start) "
            "+ (select count(*) from system_events "
            "where component = :component and starts_with(message, :prefix) "
            "and occurred_at >= :start)"
        ),
        {"start": utc_day_start(), "component": COMPONENT, "prefix": FAILED_PREFIX},
    ).scalar_one()


def log_event(db: Session, level: str, message: str) -> None:
    db.execute(
        text(
            "insert into system_events (component, level, message) "
            "values (:component, :level, :message)"
        ),
        {"component": COMPONENT, "level": level, "message": message},
    )
    db.commit()


def acquire_lock() -> Connection:
    connection = engine.connect()
    locked = connection.execute(
        text("select pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}
    ).scalar_one()
    if not locked:
        connection.close()
        raise HTTPException(status_code=409, detail="Scoring is already running")
    return connection


def release_lock(connection: Connection) -> None:
    try:
        connection.execute(text("select pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
        connection.commit()
    except Exception:
        connection.invalidate()
    else:
        connection.close()


def load_queue(db: Session, limit: int) -> list[dict]:
    rows = db.execute(
        text(
            "select id, title, company, location, work_mode, description "
            "from jobs where pipeline_status = 'new' "
            "order by priority desc, created_at desc, id desc limit :limit"
        ),
        {"limit": limit},
    ).mappings().all()
    return [dict(row) for row in rows]


def score_one(
    db: Session,
    client: httpx.Client,
    profile: str,
    job: dict,
    sleep: Callable[[float], None],
) -> str:
    messages = build_messages(profile, job)
    model = get_settings().groq_model
    for _ in range(MAX_ATTEMPTS_PER_JOB):
        try:
            content, tokens = call_groq(client, messages, sleep)
            result = parse_score_response(content)
        except ScoreValidationError:
            log_event(db, "warning", f"{FAILED_PREFIX}: invalid output job_id={job['id']}")
            continue
        db.execute(
            text(
                "insert into job_scores "
                "(job_id, score, reason, red_flags, model, prompt_version, total_tokens) "
                "values (:job_id, :score, :reason, cast(:red_flags as jsonb), "
                ":model, :prompt_version, :tokens) "
                "on conflict (job_id, prompt_version) do nothing"
            ),
            {
                "job_id": job["id"],
                "score": result.score,
                "reason": result.reason,
                "red_flags": json.dumps(result.red_flags),
                "model": model,
                "prompt_version": PROMPT_VERSION,
                "tokens": tokens,
            },
        )
        db.execute(
            text(
                "update jobs set pipeline_status = 'scored' "
                "where id = :id and pipeline_status = 'new'"
            ),
            {"id": job["id"]},
        )
        db.commit()
        return "scored"
    db.execute(
        text(
            "update jobs set pipeline_status = 'error', filter_reason = :reason "
            "where id = :id and pipeline_status = 'new'"
        ),
        {"id": job["id"], "reason": INVALID_OUTPUT_REASON},
    )
    db.commit()
    return "errored"


def execute_run(
    db: Session,
    client: httpx.Client,
    profile: str,
    limit: int,
    sleep: Callable[[float], None],
) -> dict:
    filter_summary = apply_title_filter(db)
    cap = load_daily_cap(db)
    used_before = count_used_today(db)
    remaining = max(cap - used_before, 0)

    attempted = scored = failed = errored = 0
    stopped_reason = None

    if remaining == 0:
        stopped_reason = "daily_cap_reached"
        jobs = []
    else:
        jobs = load_queue(db, min(limit, remaining))

    interval = get_settings().score_interval_seconds
    for index, job in enumerate(jobs):
        if index > 0 and interval > 0:
            sleep(interval)
        attempted += 1
        try:
            outcome = score_one(db, client, profile, job, sleep)
        except GroqRateLimited:
            failed += 1
            log_event(db, "warning", f"{FAILED_PREFIX}: rate_limited job_id={job['id']}")
            stopped_reason = "rate_limited"
            break
        except GroqTransientError:
            failed += 1
            log_event(db, "warning", f"{FAILED_PREFIX}: groq_unavailable job_id={job['id']}")
            stopped_reason = "groq_unavailable"
            break
        except GroqAuthError:
            failed += 1
            log_event(db, "error", f"{FAILED_PREFIX}: groq_auth_error job_id={job['id']}")
            stopped_reason = "groq_auth_error"
            break
        except GroqRequestError:
            failed += 1
            log_event(db, "warning", f"{FAILED_PREFIX}: request_error job_id={job['id']}")
            continue
        if outcome == "scored":
            scored += 1
        else:
            errored += 1

    used_after = count_used_today(db)
    return {
        "requested": limit,
        "attempted": attempted,
        "scored": scored,
        "failed": failed,
        "errored": errored,
        "stopped_reason": stopped_reason,
        "cap": {
            "limit": cap,
            "used_before": used_before,
            "remaining_after": max(cap - used_after, 0),
        },
        "title_filter": filter_summary,
    }


def run_scoring(
    db: Session,
    client: httpx.Client,
    limit: int,
    sleep: Callable[[float], None] | None = None,
) -> dict:
    sleep = sleep or time.sleep
    profile = get_profile_text(db)
    lock = acquire_lock()
    try:
        return execute_run(db, client, profile, limit, sleep)
    finally:
        release_lock(lock)