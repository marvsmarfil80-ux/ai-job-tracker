import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine
from app.models import Application
from app.services.applications import change_status
from app.services.email_classifier import build_messages, parse_classify_response
from app.services.email_matching import find_candidates, sender_is_allowed
from app.services.email_status_rules import decide
from app.services.follow_up_reminders import clean_part
from app.services.groq_client import (
    GroqAuthError,
    GroqRateLimited,
    GroqRequestError,
    GroqTransientError,
    call_groq,
)
from app.services.jobs import priority_for_source
from app.services.linkedin_parser import LinkedInParseError, parse_linkedin_alert
from app.services.notifications import insert_notification
from app.services.scoring import utc_day_start
from app.services.scoring_prompt import ScoreValidationError
from app.services.settings import read_values

LOCK_KEY = 5150002
COMPONENT = "email_processing"
FAILED_PREFIX = "Groq call failed"
MAX_ATTEMPTS_PER_EMAIL = 2
REASON_NO_MATCH = "No matching application"
REASON_MULTIPLE = "More than one matching application"
ERROR_INVALID_OUTPUT = "Classification failed: invalid model output"
ERROR_REQUEST = "Classification request failed"
ERROR_UNEXPECTED = "Processing failed unexpectedly"
STATUS_LABELS = {
    "applied": "Applied",
    "under_review": "Under Review",
    "assessment": "Assessment",
    "interview": "Interview",
    "offer": "Offer",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}

SELECT_EMAIL = text(
    "select id, kind, sender, subject, snippet, application_id, "
    "case when kind = 'job_alert' then body_html end as body_html "
    "from emails where id = :id and status = 'unprocessed'"
)
INSERT_JOB = text(
    "insert into jobs (source, title, company, url, url_normalized, location, "
    "work_mode, priority, pipeline_status) "
    "values ('linkedin_email', :title, :company, :url, :url, :location, "
    ":work_mode, :priority, 'new') "
    "on conflict (url_normalized) do nothing"
)
UPDATE_ALERT_DONE = text(
    "update emails set status = 'processed', body_html = null, error = null, "
    "processed_at = now() where id = :id"
)
UPDATE_ERROR = text(
    "update emails set status = 'error', error = :error, processed_at = now() "
    "where id = :id"
)
UPDATE_RESULT = text(
    "update emails set status = 'processed', \"class\" = :label, "
    "confidence = :confidence, application_id = :application_id, "
    "processed_at = now(), error = null where id = :id"
)
SELECT_JOB_INFO = text("select title, company from jobs where id = :id")


@dataclass(frozen=True)
class EmailSettings:
    auto_enabled: bool
    min_confidence: int
    daily_cap: int


def require_int(values: dict, key: str, low: int, high: int) -> int:
    value = values[key]
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise HTTPException(
            status_code=500,
            detail=f"Setting {key} must be an integer from {low} to {high}",
        )
    return value


def load_email_settings(db: Session) -> EmailSettings:
    values = read_values(db)
    enabled = values["email_auto_status_enabled"]
    if not isinstance(enabled, bool):
        raise HTTPException(
            status_code=500, detail="Setting email_auto_status_enabled must be a boolean"
        )
    return EmailSettings(
        auto_enabled=enabled,
        min_confidence=require_int(values, "email_auto_status_min_confidence", 50, 100),
        daily_cap=require_int(values, "email_classify_daily_cap", 1, 100),
    )


def count_used_today(db: Session) -> int:
    return db.execute(
        text(
            "select count(*) from emails "
            "where kind = 'application' and processed_at >= :start"
        ),
        {"start": utc_day_start()},
    ).scalar_one()


def count_waiting_applications(db: Session) -> int:
    return db.execute(
        text(
            "select count(*) from emails "
            "where kind = 'application' and status = 'unprocessed'"
        )
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
        raise HTTPException(status_code=409, detail="Email processing is already running")
    return connection


def release_lock(connection: Connection) -> None:
    try:
        connection.execute(text("select pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
        connection.commit()
    except Exception:
        connection.invalidate()
    else:
        connection.close()


def load_queue(db: Session, limit: int, alerts_only: bool) -> list[int]:
    kind_filter = "and kind = 'job_alert' " if alerts_only else ""
    rows = db.execute(
        text(
            "select id from emails where status = 'unprocessed' "
            + kind_filter
            + "order by received_at asc, id asc limit :limit"
        ),
        {"limit": limit},
    ).scalars().all()
    return list(rows)


def load_email(db: Session, email_id: int) -> dict | None:
    row = db.execute(SELECT_EMAIL, {"id": email_id}).mappings().first()
    return dict(row) if row is not None else None


def mark_error(db: Session, email_id: int, message: str) -> None:
    db.execute(UPDATE_ERROR, {"id": email_id, "error": message})
    db.commit()


def build_status_message(new_status: str, job_title: str | None, company: str | None) -> str:
    job = clean_part(job_title)
    firm = clean_part(company)
    if job and firm:
        where = f"{job} at {firm}"
    else:
        where = job or firm or "your application"
    return (
        f"Status changed to {STATUS_LABELS[new_status]} for {where} "
        "based on an email. You can undo this."
    )


def notify_review(db: Session, email_id: int, reason: str) -> None:
    insert_notification(
        db, "email_needs_review", f"Email needs review: {reason}", f"/emails/{email_id}"
    )


def process_job_alert(db: Session, email: dict) -> Counter:
    try:
        parsed = parse_linkedin_alert(email["body_html"] or "")
    except LinkedInParseError as exc:
        mark_error(db, email["id"], str(exc))
        return Counter(errored=1)
    priority = priority_for_source("linkedin_email")
    created = 0
    duplicate = 0
    for job in parsed.jobs:
        inserted = db.execute(
            INSERT_JOB,
            {
                "title": job.title,
                "company": job.company,
                "url": job.url,
                "location": job.location,
                "work_mode": job.work_mode,
                "priority": priority,
            },
        ).rowcount
        if inserted == 1:
            created += 1
        else:
            duplicate += 1
    db.execute(UPDATE_ALERT_DONE, {"id": email["id"]})
    db.commit()
    return Counter(processed=1, jobs_created=created, jobs_duplicate=duplicate)


def classify(
    db: Session,
    client: httpx.Client,
    email: dict,
    sleep: Callable[[float], None],
):
    messages = build_messages(email["sender"], email["subject"], email["snippet"])
    interval = get_settings().score_interval_seconds
    for attempt in range(MAX_ATTEMPTS_PER_EMAIL):
        if attempt > 0 and interval > 0:
            sleep(interval)
        try:
            content, _tokens = call_groq(client, messages, sleep)
            return parse_classify_response(content)
        except ScoreValidationError:
            log_event(db, "warning", f"{FAILED_PREFIX}: invalid output email_id={email['id']}")
    return None


def apply_to_application(
    db: Session, email: dict, application_id: int, label: str, confidence: int, cfg: EmailSettings
) -> Counter:
    application = db.get(Application, application_id, with_for_update=True)
    if application is None:
        notify_review(db, email["id"], REASON_NO_MATCH)
        return Counter(needs_review=1)
    allowed = sender_is_allowed(db, email["sender"], "application")
    decision = decide(
        label, confidence, application.status, cfg.auto_enabled, cfg.min_confidence, allowed
    )
    if decision.action == "change":
        change_status(db, application, decision.new_status, source="email", email_id=email["id"])
        job = db.execute(SELECT_JOB_INFO, {"id": application.job_id}).mappings().first()
        message = build_status_message(
            decision.new_status, job["title"] if job else None, job["company"] if job else None
        )
        insert_notification(db, "status_changed", message, f"/applications/{application.id}")
        return Counter(auto_status_changed=1)
    if decision.action == "review":
        notify_review(db, email["id"], decision.reason)
        return Counter(needs_review=1)
    return Counter()


def process_application(
    db: Session,
    client: httpx.Client,
    email: dict,
    cfg: EmailSettings,
    sleep: Callable[[float], None],
) -> Counter:
    try:
        result = classify(db, client, email, sleep)
    except GroqRequestError:
        log_event(db, "warning", f"{FAILED_PREFIX}: request_error email_id={email['id']}")
        mark_error(db, email["id"], ERROR_REQUEST)
        return Counter(errored=1)
    if result is None:
        mark_error(db, email["id"], ERROR_INVALID_OUTPUT)
        return Counter(errored=1)

    counts = Counter(processed=1, classified=1)
    application_id = email["application_id"]
    if result.label == "unknown":
        label = None
    else:
        label = result.label
        reason = None
        if application_id is None:
            candidates = find_candidates(db, email["subject"], email["snippet"])
            if len(candidates) == 1:
                application_id = candidates[0]["id"]
            elif not candidates:
                reason = REASON_NO_MATCH
            else:
                reason = REASON_MULTIPLE
        if application_id is None:
            notify_review(db, email["id"], reason)
            counts["needs_review"] += 1
        else:
            counts.update(
                apply_to_application(db, email, application_id, label, result.confidence, cfg)
            )
    db.execute(
        UPDATE_RESULT,
        {
            "id": email["id"],
            "label": label,
            "confidence": result.confidence,
            "application_id": application_id,
        },
    )
    db.commit()
    return counts


def record_groq_failure(db: Session, level: str, exc: Exception) -> None:
    db.rollback()
    log_event(db, level, f"{FAILED_PREFIX}: {type(exc).__name__}")


def record_unexpected(db: Session, email_id: int, exc: Exception) -> None:
    try:
        db.rollback()
        log_event(
            db, "error", f"Email processing failed: {type(exc).__name__} email_id={email_id}"
        )
        mark_error(db, email_id, ERROR_UNEXPECTED)
    except Exception:
        db.rollback()


def execute_run(
    db: Session,
    client: httpx.Client,
    limit: int,
    sleep: Callable[[float], None],
) -> dict:
    cfg = load_email_settings(db)
    used_before = count_used_today(db)
    budget = max(cfg.daily_cap - used_before, 0)
    counts: Counter = Counter()
    stopped_reason = None
    skipped_by_cap = 0
    if budget == 0:
        skipped_by_cap = count_waiting_applications(db)
        if skipped_by_cap > 0:
            stopped_reason = "cap_reached"

    queue = load_queue(db, limit, alerts_only=budget == 0)
    interval = get_settings().score_interval_seconds
    calls_made = 0
    for email_id in queue:
        email = load_email(db, email_id)
        if email is None:
            continue
        is_application = email["kind"] == "application"
        if is_application:
            if budget <= 0:
                skipped_by_cap += 1
                stopped_reason = stopped_reason or "cap_reached"
                continue
            budget -= 1
            if calls_made > 0 and interval > 0:
                sleep(interval)
            calls_made += 1
        try:
            if is_application:
                counts.update(process_application(db, client, email, cfg, sleep))
            else:
                counts.update(process_job_alert(db, email))
        except GroqRateLimited as exc:
            record_groq_failure(db, "warning", exc)
            stopped_reason = "rate_limited"
            break
        except GroqTransientError as exc:
            record_groq_failure(db, "warning", exc)
            stopped_reason = "groq_unavailable"
            break
        except GroqAuthError as exc:
            record_groq_failure(db, "error", exc)
            stopped_reason = "groq_auth_error"
            break
        except Exception as exc:
            record_unexpected(db, email["id"], exc)
            counts["errored"] += 1

    used_after = count_used_today(db)
    return {
        "requested": limit,
        "processed": counts["processed"],
        "jobs_created": counts["jobs_created"],
        "jobs_duplicate": counts["jobs_duplicate"],
        "classified": counts["classified"],
        "auto_status_changed": counts["auto_status_changed"],
        "needs_review": counts["needs_review"],
        "errored": counts["errored"],
        "skipped_by_cap": skipped_by_cap,
        "stopped_reason": stopped_reason,
        "cap": {
            "limit": cfg.daily_cap,
            "used_before": used_before,
            "remaining_after": max(cfg.daily_cap - used_after, 0),
        },
    }


def run_email_processing(
    db: Session,
    client: httpx.Client,
    limit: int,
    sleep: Callable[[float], None] | None = None,
) -> dict:
    sleep = sleep or time.sleep
    lock = acquire_lock()
    try:
        return execute_run(db, client, limit, sleep)
    finally:
        release_lock(lock)