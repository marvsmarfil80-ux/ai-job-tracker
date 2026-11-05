import logging

from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings
from app.services.settings import DEFAULTS

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
HEALTH_TIMEOUT_SECONDS = 3.0
EMAIL_SOURCE = "email"
DATABASE_MESSAGE = "Database is unreachable."
SCHEDULER_KEYS = ["scheduler_enabled", "followup_reminders_enabled"]

class HealthLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/healthz" not in record.getMessage()


logging.getLogger("httpx").addFilter(HealthLogFilter())

EMAIL_RUN_FILTER = (
    "exists (select 1 from search_run_steps s "
    "where s.run_id = r.id and s.source = :source)"
)


def secret_is_set(value) -> bool:
    if value is None:
        return False
    raw = value.get_secret_value() if hasattr(value, "get_secret_value") else str(value)
    return raw.strip() != ""


def to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc)


def check_database(db: Session) -> dict:
    try:
        db.execute(text("select 1"))
    except Exception:
        raise HTTPException(status_code=503, detail=DATABASE_MESSAGE)
    try:
        version = db.execute(
            text("select version_num from alembic_version limit 1")
        ).scalar_one_or_none()
    except Exception:
        db.rollback()
        version = None
    return {"status": "ok", "schema_version": version}


def health_url(raw: str) -> str | None:
    try:
        parts = urlsplit(raw)
        host = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or host not in LOCAL_HOSTS:
        return None
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return f"{parts.scheme}://{netloc}/healthz"


def check_n8n(url, client: httpx.Client) -> dict:
    if not secret_is_set(url):
        return {"status": "not_configured", "http_status": None}
    target = health_url(url.get_secret_value())
    if target is None:
        return {"status": "error", "http_status": None}
    try:
        response = client.get(
            target, timeout=HEALTH_TIMEOUT_SECONDS, follow_redirects=False
        )
    except Exception:
        return {"status": "error", "http_status": None}
    status = "ok" if response.status_code == 200 else "error"
    return {"status": status, "http_status": response.status_code}


def check_email_sync(db: Session) -> dict:
    empty = {
        "last_run_id": None,
        "last_run_status": None,
        "last_run_finished_at": None,
        "last_successful_run_at": None,
    }
    params = {"source": EMAIL_SOURCE}
    try:
        last = db.execute(
            text(
                "select r.id, r.status, r.finished_at from search_runs r "
                f"where {EMAIL_RUN_FILTER} "
                "order by r.started_at desc, r.id desc limit 1"
            ),
            params,
        ).mappings().first()
        success = db.execute(
            text(
                "select max(r.finished_at) from search_runs r "
                f"where r.status = 'done' and {EMAIL_RUN_FILTER}"
            ),
            params,
        ).scalar_one()
    except Exception:
        db.rollback()
        return empty
    if last is None:
        return empty
    return {
        "last_run_id": last["id"],
        "last_run_status": last["status"],
        "last_run_finished_at": to_utc(last["finished_at"]),
        "last_successful_run_at": to_utc(success),
    }


def check_profile(db: Session) -> dict:
    try:
        is_set = db.execute(
            text(r"select exists (select 1 from profile where content ~ '\S')")
        ).scalar_one()
    except Exception:
        db.rollback()
        is_set = False
    return {"is_set": bool(is_set)}


def check_scheduler(db: Session) -> dict:
    values = {key: DEFAULTS[key] for key in SCHEDULER_KEYS}
    try:
        rows = db.execute(
            text("select key, value from settings where key = any(cast(:keys as text[]))"),
            {"keys": SCHEDULER_KEYS},
        ).all()
    except Exception:
        db.rollback()
        rows = []
    for key, value in rows:
        if isinstance(value, bool):
            values[key] = value
    return {
        "enabled": values["scheduler_enabled"],
        "followup_reminders_enabled": values["followup_reminders_enabled"],
    }


def build_status(db: Session, config: Settings, client: httpx.Client, now: datetime) -> dict:
    database = check_database(db)
    n8n = check_n8n(config.n8n_webhook_url, client)
    healthy = database["status"] == "ok" and n8n["status"] in ("ok", "not_configured")
    return {
        "status": "ok" if healthy else "degraded",
        "checked_at": now.astimezone(timezone.utc),
        "database": database,
        "groq": {
            "api_key_configured": secret_is_set(config.groq_api_key),
            "mock_mode": bool(config.groq_mock),
        },
        "n8n": n8n,
        "email_sync": check_email_sync(db),
        "profile": check_profile(db),
        "scheduler": check_scheduler(db),
    }