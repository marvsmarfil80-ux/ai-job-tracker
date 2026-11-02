import contextlib
import time
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import get_settings
from app.db import SessionLocal
from app.services.email_processing import run_email_processing
from app.services.groq_client import get_groq_client
from app.services.notifications import insert_notification
from app.services.settings import read_values

COMPONENT = "email_sync"
SOURCE = "email"
WEBHOOK_HEADER = "X-Webhook-Key"
WEBHOOK_TIMEOUT_SECONDS = 10.0
POLL_SECONDS = 5.0
OVERLAP = timedelta(hours=1)
PROCESS_LIMIT = 100
NOTIFICATION_TYPE = "hunt_done"
MESSAGE_NOT_CONFIGURED = "The n8n webhook is not configured."
MESSAGE_RUNNING = "An email sync is already running."
MESSAGE_UNREACHABLE = "Could not reach the n8n webhook."
MESSAGE_TIMEOUT = "n8n did not respond within the timeout."


def default_groq_client():
    return contextlib.contextmanager(get_groq_client)()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_event(db: Session, level: str, message: str, run_id: int | None = None) -> None:
    db.execute(
        text(
            "insert into system_events (component, level, run_id, message) "
            "values (:component, :level, :run_id, :message)"
        ),
        {"component": COMPONENT, "level": level, "run_id": run_id, "message": message},
    )
    db.commit()


def close_run(db: Session, run_id: int, status: str, total_new: int = 0) -> None:
    db.execute(
        text(
            "update search_runs set status = :status, finished_at = now(), "
            "total_new = :total where id = :id"
        ),
        {"status": status, "total": total_new, "id": run_id},
    )
    db.commit()


def mark_step_error(db: Session, run_id: int, message: str) -> int:
    result = db.execute(
        text(
            "update search_run_steps set status = 'error', message = :message "
            "where run_id = :run_id and source = :source and status = 'running'"
        ),
        {"message": message, "run_id": run_id, "source": SOURCE},
    )
    db.commit()
    return result.rowcount


def stale_check(db: Session, timeout_seconds: int, now: datetime | None = None) -> int:
    cutoff = (now or utc_now()) - timedelta(seconds=timeout_seconds)
    run_ids = db.execute(
        text(
            "select s.run_id from search_run_steps s "
            "join search_runs r on r.id = s.run_id "
            "where s.source = :source and s.status = 'running' and r.started_at < :cutoff"
        ),
        {"source": SOURCE, "cutoff": cutoff},
    ).scalars().all()
    for run_id in run_ids:
        if mark_step_error(db, run_id, MESSAGE_TIMEOUT) == 1:
            close_run(db, run_id, "error")
            log_event(db, "error", "A stale email sync was marked as failed.", run_id)
    return len(run_ids)


def sync_is_running(db: Session) -> bool:
    return db.execute(
        text(
            "select exists (select 1 from search_run_steps "
            "where source = :source and status = 'running')"
        ),
        {"source": SOURCE},
    ).scalar_one()


def compute_since(db: Session, lookback_days: int, now: datetime | None = None) -> str:
    current = now or utc_now()
    last = db.execute(
        text(
            "select max(r.started_at) from search_runs r "
            "join search_run_steps s on s.run_id = r.id "
            "where s.source = :source and s.status = 'done'"
        ),
        {"source": SOURCE},
    ).scalar_one()
    if last is not None:
        return format_utc(last - OVERLAP)
    return format_utc(current - timedelta(days=lookback_days))


def call_n8n(client: httpx.Client, url: str, key: str, run_id: int, since: str) -> None:
    response = client.post(
        url,
        json={"run_id": run_id, "since": since},
        headers={WEBHOOK_HEADER: key},
    )
    response.raise_for_status()


def start_sync(db: Session, trigger: str, http_client: httpx.Client | None = None) -> int:
    config = get_settings()
    if config.n8n_webhook_url is None or config.n8n_webhook_key is None:
        raise HTTPException(status_code=503, detail=MESSAGE_NOT_CONFIGURED)
    values = read_values(db)
    stale_check(db, values["email_sync_timeout_seconds"])
    if sync_is_running(db):
        raise HTTPException(status_code=409, detail=MESSAGE_RUNNING)
    since = compute_since(db, values["email_sync_lookback_days"])
    run_id = db.execute(
        text("insert into search_runs (trigger) values (:trigger) returning id"),
        {"trigger": trigger},
    ).scalar_one()
    db.execute(
        text(
            "insert into search_run_steps (run_id, source, status) "
            "values (:run_id, :source, 'running')"
        ),
        {"run_id": run_id, "source": SOURCE},
    )
    db.commit()
    url = config.n8n_webhook_url.get_secret_value()
    key = config.n8n_webhook_key.get_secret_value()
    try:
        if http_client is None:
            with httpx.Client(timeout=httpx.Timeout(WEBHOOK_TIMEOUT_SECONDS)) as client:
                call_n8n(client, url, key, run_id, since)
        else:
            call_n8n(http_client, url, key, run_id, since)
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        mark_step_error(db, run_id, MESSAGE_UNREACHABLE)
        close_run(db, run_id, "error")
        log_event(db, "error", f"Could not reach the n8n webhook: {type(exc).__name__}", run_id)
        raise HTTPException(status_code=502, detail=MESSAGE_UNREACHABLE)
    return run_id


def read_step(session_factory, run_id: int) -> dict | None:
    with session_factory() as db:
        row = db.execute(
            text(
                'select status, "new" from search_run_steps '
                "where run_id = :run_id and source = :source order by id desc limit 1"
            ),
            {"run_id": run_id, "source": SOURCE},
        ).mappings().first()
    return dict(row) if row is not None else None


def wait_for_step(session_factory, run_id: int, timeout_seconds: float, sleep, poll_seconds: float):
    deadline = time.monotonic() + timeout_seconds
    while True:
        step = read_step(session_factory, run_id)
        if step is None:
            return "missing", None
        if step["status"] != "running":
            return step["status"], step
        if time.monotonic() >= deadline:
            with session_factory() as db:
                if mark_step_error(db, run_id, MESSAGE_TIMEOUT) == 1:
                    return "timeout", None
            continue
        sleep(poll_seconds)


def build_message(new_emails: int, new_jobs: int) -> str:
    emails = f"{new_emails} new email" + ("" if new_emails == 1 else "s")
    jobs = f"{new_jobs} new job" + ("" if new_jobs == 1 else "s")
    return f"Email check finished: {emails}, {jobs}."


def process_and_close(db: Session, run_id: int, step: dict, groq_client_factory) -> None:
    try:
        with groq_client_factory() as client:
            result = run_email_processing(db, client, PROCESS_LIMIT)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        close_run(db, run_id, "done")
        log_event(db, "info", "Email processing skipped: another job is running.", run_id)
        return
    jobs_created = result["jobs_created"]
    close_run(db, run_id, "done", jobs_created)
    if result["stopped_reason"] is not None:
        log_event(
            db, "warning", f"Email processing stopped early: {result['stopped_reason']}", run_id
        )
    new_emails = step["new"]
    if new_emails > 0 or jobs_created > 0:
        insert_notification(db, NOTIFICATION_TYPE, build_message(new_emails, jobs_created), None)
        db.commit()


def record_failure(session_factory, run_id: int, exc: Exception) -> None:
    try:
        with session_factory() as db:
            mark_step_error(db, run_id, "The email sync failed unexpectedly.")
            db.execute(
                text(
                    "update search_runs set status = 'error', finished_at = now() "
                    "where id = :id and status = 'running'"
                ),
                {"id": run_id},
            )
            db.commit()
            log_event(
                db, "error", f"Email sync failed unexpectedly: {type(exc).__name__}", run_id
            )
    except Exception:
        pass


def finish_sync(
    run_id: int,
    session_factory=SessionLocal,
    groq_client_factory=default_groq_client,
    sleep=time.sleep,
    poll_seconds: float = POLL_SECONDS,
) -> None:
    try:
        with session_factory() as db:
            timeout_seconds = read_values(db)["email_sync_timeout_seconds"]
        outcome, step = wait_for_step(
            session_factory, run_id, timeout_seconds, sleep, poll_seconds
        )
        with session_factory() as db:
            if outcome == "done":
                process_and_close(db, run_id, step, groq_client_factory)
            elif outcome == "timeout":
                close_run(db, run_id, "error")
                log_event(db, "error", MESSAGE_TIMEOUT, run_id)
            else:
                close_run(db, run_id, "error")
                log_event(db, "error", "The n8n email importer reported an error.", run_id)
    except Exception as exc:
        record_failure(session_factory, run_id, exc)