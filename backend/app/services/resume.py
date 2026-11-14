from __future__ import annotations

import io
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from fastapi import HTTPException
from pypdf import PdfReader
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.groq_client import (
    GroqAuthError,
    GroqRateLimited,
    GroqRequestError,
    GroqTransientError,
    call_groq,
)
from app.services.profile_sanitizer import REMOVED, _EMAIL, _LABEL_LINE, _remove_phones
from app.services.resume_prompt import (
    ResumeValidationError,
    build_messages,
    parse_resume_response,
)
from app.services.scoring import FAILED_PREFIX, utc_day_start
from app.services.scoring_prompt import ScoreValidationError

RESUME_COMPONENT = "resume"
RESUME_OK_MESSAGE = "Resume draft call"

MAX_PDF_BYTES = 2_097_152
MAX_PAGES = 5
MAX_PROMPT_CHARS = 6_000
RESUME_DAILY_CAP = 5
MAX_ATTEMPTS = 2
RESUME_MAX_TOKENS = 600
MAX_SKILLS = 40
MAX_DRAFT_CHARS = 2_000

PDF_MAGIC = b"%PDF-"

URL_PATTERN = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"']+")
ADDRESS_POSTAL = re.compile(r"(?<!\d)\d{4,5}(?!\d)")
ADDRESS_WORD = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:street|st\.|ave|avenue|brgy|barangay|city|province|zip|postal|subdivision)(?![A-Za-z0-9])"
)

WARNING_CONTACT = "Some contact details were removed before analysis."
WARNING_TRUNCATED = "The text was truncated before analysis."
WARNING_DROPPED = "Some skills were dropped because they were not found in the PDF text."


@dataclass(frozen=True)
class RedactResult:
    text: str
    emails: int
    phones: int
    lines: int
    urls: int
    address_lines: int


def _reject(status: int, detail: str) -> None:
    raise HTTPException(status_code=status, detail=detail)


def _extract_pdf_text(pdf_bytes: bytes) -> tuple[str, int]:
    if not pdf_bytes.startswith(PDF_MAGIC):
        _reject(422, "The file is not a valid PDF.")
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        encrypted = bool(reader.is_encrypted)
    except Exception:
        _reject(422, "The file is not a valid PDF.")
    if encrypted:
        _reject(422, "The PDF is encrypted.")
    try:
        page_count = len(reader.pages)
    except Exception:
        _reject(422, "The file is not a valid PDF.")
    if page_count > MAX_PAGES:
        _reject(422, "The PDF has too many pages.")
    chunks: list[str] = []
    for page in reader.pages:
        try:
            extracted = page.extract_text() or ""
        except Exception:
            extracted = ""
        chunks.append(extracted)
    combined = "\n".join(chunks)
    if not combined.strip():
        _reject(422, "The PDF has no readable text.")
    return combined, page_count


def _redact(text: str) -> RedactResult:
    kept: list[str] = []
    removed_lines = 0
    for line in text.splitlines():
        if _LABEL_LINE.match(line):
            removed_lines += 1
            continue
        kept.append(line)
    without_label_lines = "\n".join(kept)
    text_after_emails, emails = _EMAIL.subn(REMOVED, without_label_lines)
    text_after_phones, phones = _remove_phones(text_after_emails)
    text_after_urls, urls = URL_PATTERN.subn(REMOVED, text_after_phones)
    address_lines = 0
    final_lines: list[str] = []
    for line in text_after_urls.splitlines():
        if ADDRESS_POSTAL.search(line) and ADDRESS_WORD.search(line):
            address_lines += 1
            final_lines.append(REMOVED)
        else:
            final_lines.append(line)
    return RedactResult(
        text="\n".join(final_lines),
        emails=emails,
        phones=phones,
        lines=removed_lines,
        urls=urls,
        address_lines=address_lines,
    )


def count_resume_calls_today(db: Session) -> int:
    return db.execute(
        text(
            "select count(*) from system_events "
            "where component = :component "
            "and (message = :ok or starts_with(message, :prefix)) "
            "and occurred_at >= :start"
        ),
        {
            "component": RESUME_COMPONENT,
            "ok": RESUME_OK_MESSAGE,
            "prefix": FAILED_PREFIX,
            "start": utc_day_start(),
        },
    ).scalar_one()


def count_shared_calls_today(db: Session) -> int:
    return db.execute(
        text(
            "select "
            "(select count(*) from job_scores where scored_at >= :start) "
            "+ (select count(*) from system_events "
            "where component = 'scoring' and starts_with(message, :prefix) "
            "and occurred_at >= :start) "
            "+ (select count(*) from system_events "
            "where component = 'extract' "
            "and (message = 'Extract call' or starts_with(message, :prefix)) "
            "and occurred_at >= :start)"
        ),
        {"start": utc_day_start(), "prefix": FAILED_PREFIX},
    ).scalar_one()


def _load_shared_cap(db: Session) -> int | None:
    value = db.execute(
        text("select value from settings where key = 'daily_score_cap'")
    ).scalar_one_or_none()
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _check_caps(db: Session) -> None:
    resume_used = count_resume_calls_today(db)
    if resume_used >= RESUME_DAILY_CAP:
        _reject(429, "Daily resume draft limit reached.")
    shared_cap = _load_shared_cap(db)
    if shared_cap is None:
        return
    if count_shared_calls_today(db) + resume_used >= shared_cap:
        _reject(429, "Daily resume draft limit reached.")


def log_event(db: Session, level: str, message: str) -> None:
    db.execute(
        text(
            "insert into system_events (component, level, message) "
            "values (:component, :level, :message)"
        ),
        {"component": RESUME_COMPONENT, "level": level, "message": message},
    )
    db.commit()


def fail(db: Session, level: str, reason: str, status: int, detail: str) -> None:
    log_event(db, level, f"{FAILED_PREFIX}: {reason}")
    _reject(status, detail)


def _skill_pattern(skill: str) -> re.Pattern[str]:
    normalized = " ".join(skill.split())
    return re.compile(
        r"(?<![A-Za-z0-9])" + re.escape(normalized) + r"(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _validate_skills(candidates: list[str], prompt_text: str) -> tuple[list[str], list[str]]:
    haystack = _normalize(prompt_text.replace(REMOVED, " "))
    seen: set[str] = set()
    kept: list[str] = []
    dropped: list[str] = []
    for value in candidates:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        if _skill_pattern(value).search(haystack):
            if len(kept) < MAX_SKILLS:
                kept.append(value)
        else:
            dropped.append(value)
    return kept, dropped


def _build_draft(skills: list[str]) -> str:
    prefix = "Skills: "
    if not skills:
        return prefix.rstrip()
    parts: list[str] = []
    total = len(prefix)
    for index, skill in enumerate(skills):
        addition = skill if index == 0 else ", " + skill
        if total + len(addition) > MAX_DRAFT_CHARS:
            break
        parts.append(addition)
        total += len(addition)
    return prefix + "".join(parts)


def _build_warnings(redactions: RedactResult, truncated: bool, dropped: int) -> list[str]:
    warnings: list[str] = []
    if (
        redactions.emails
        or redactions.phones
        or redactions.lines
        or redactions.urls
        or redactions.address_lines
    ):
        warnings.append(WARNING_CONTACT)
    if truncated:
        warnings.append(WARNING_TRUNCATED)
    if dropped > 0:
        warnings.append(WARNING_DROPPED)
    return warnings


def run_resume_draft(
    db: Session,
    client: httpx.Client,
    pdf_bytes: bytes,
    sleep: Callable[[float], None] | None = None,
) -> dict:
    sleep = sleep or time.sleep

    extracted_text, page_count = _extract_pdf_text(pdf_bytes)
    extracted_chars = len(extracted_text)

    redactions = _redact(extracted_text)
    prompt_text = redactions.text
    truncated = False
    if len(prompt_text) > MAX_PROMPT_CHARS:
        prompt_text = prompt_text[:MAX_PROMPT_CHARS]
        truncated = True

    settings = get_settings()
    if settings.groq_api_key is None and not settings.groq_mock:
        _reject(503, "The AI service is not configured.")

    messages = build_messages(prompt_text)
    for _ in range(MAX_ATTEMPTS):
        _check_caps(db)
        try:
            content, _ = call_groq(client, messages, sleep, RESUME_MAX_TOKENS)
            parsed = parse_resume_response(content)
        except (ResumeValidationError, ScoreValidationError):
            log_event(db, "warning", f"{FAILED_PREFIX}: invalid output")
            continue
        except GroqRateLimited:
            fail(db, "warning", "rate_limited", 429, "The AI service is busy. Try again in a minute.")
        except GroqTransientError:
            fail(db, "warning", "groq_unavailable", 503, "The AI service is unavailable.")
        except GroqAuthError:
            fail(db, "error", "groq_auth_error", 502, "The AI service rejected our credentials.")
        except GroqRequestError:
            fail(db, "warning", "request_error", 503, "The AI service is unavailable.")
        log_event(db, "info", RESUME_OK_MESSAGE)
        skills, dropped_skills = _validate_skills(parsed.skills, prompt_text)
        if not skills:
            _reject(422, "No skills could be found in this PDF.")
        return {
            "skills": skills,
            "draft_content": _build_draft(skills),
            "pages": page_count,
            "extracted_chars": extracted_chars,
            "truncated": truncated,
            "redactions": {
                "emails": redactions.emails,
                "phones": redactions.phones,
                "lines": redactions.lines,
                "urls": redactions.urls,
                "address_lines": redactions.address_lines,
            },
            "dropped_skills": dropped_skills,
            "warnings": _build_warnings(redactions, truncated, len(dropped_skills)),
        }
    _reject(502, "The AI service returned an invalid response.")