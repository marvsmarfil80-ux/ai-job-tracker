import time
from collections.abc import Callable

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.extract_prompt import (
    ExtractNoTitle,
    build_messages,
    parse_extract_response,
)
from app.services.groq_client import (
    GroqAuthError,
    GroqRateLimited,
    GroqRequestError,
    GroqTransientError,
    call_groq,
)
from app.services.profile_sanitizer import sanitize_page_text
from app.services.scoring import (
    EXTRACT_COMPONENT,
    EXTRACT_OK_MESSAGE,
    FAILED_PREFIX,
    utc_day_start,
)
from app.services.scoring_prompt import ScoreValidationError

DAILY_EXTRACT_CAP = 40
MAX_ATTEMPTS = 2
EXTRACT_MAX_TOKENS = 900


def count_extract_calls_today(db: Session) -> int:
    return db.execute(
        text(
            "select count(*) from system_events "
            "where component = :component "
            "and (message = :ok or starts_with(message, :prefix)) "
            "and occurred_at >= :start"
        ),
        {
            "component": EXTRACT_COMPONENT,
            "ok": EXTRACT_OK_MESSAGE,
            "prefix": FAILED_PREFIX,
            "start": utc_day_start(),
        },
    ).scalar_one()


def log_event(db: Session, level: str, message: str) -> None:
    db.execute(
        text(
            "insert into system_events (component, level, message) "
            "values (:component, :level, :message)"
        ),
        {"component": EXTRACT_COMPONENT, "level": level, "message": message},
    )
    db.commit()


def ensure_capacity(db: Session) -> None:
    if count_extract_calls_today(db) >= DAILY_EXTRACT_CAP:
        raise HTTPException(status_code=429, detail="Daily extraction limit reached.")


def fail(db: Session, level: str, reason: str, status: int, detail: str) -> None:
    log_event(db, level, f"{FAILED_PREFIX}: {reason}")
    raise HTTPException(status_code=status, detail=detail)


def run_extract(
    db: Session,
    client: httpx.Client,
    url_normalized: str,
    page_text: str,
    sleep: Callable[[float], None] | None = None,
) -> dict:
    sleep = sleep or time.sleep
    cleaned = sanitize_page_text(page_text)
    if not cleaned:
        raise HTTPException(status_code=422, detail="Page text has no readable content.")

    settings = get_settings()
    if settings.groq_api_key is None and not settings.groq_mock:
        raise HTTPException(status_code=503, detail="The AI service is not configured.")

    messages = build_messages(url_normalized, cleaned)
    for _ in range(MAX_ATTEMPTS):
        ensure_capacity(db)
        try:
            content, _ = call_groq(client, messages, sleep, EXTRACT_MAX_TOKENS)
            result = parse_extract_response(content)
        except ExtractNoTitle:
            log_event(db, "info", EXTRACT_OK_MESSAGE)
            raise HTTPException(
                status_code=422, detail="Could not find a job title in this page text."
            )
        except ScoreValidationError:
            log_event(db, "warning", f"{FAILED_PREFIX}: invalid output")
            continue
        except GroqRateLimited:
            fail(db, "warning", "rate_limited", 429,
                 "The AI service is busy. Try again in a minute.")
        except GroqTransientError:
            fail(db, "warning", "groq_unavailable", 503, "The AI service is unavailable.")
        except GroqAuthError:
            fail(db, "error", "groq_auth_error", 502,
                 "The AI service rejected our credentials.")
        except GroqRequestError:
            fail(db, "warning", "request_error", 503, "The AI service is unavailable.")
        log_event(db, "info", EXTRACT_OK_MESSAGE)
        return {
            "title": result.title,
            "company": result.company,
            "description": result.description,
        }
    raise HTTPException(status_code=502, detail="The AI service returned an invalid response.")
