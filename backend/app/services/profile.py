from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.profile_sanitizer import address_warnings, sanitize_profile

NOT_SET_DETAIL = "Profile is not set. Save a profile with PUT /profile first."


def read_profile(db: Session) -> tuple[str, datetime | None]:
    row = db.execute(text("select content, updated_at from profile where id = 1")).one_or_none()
    if row is None:
        return "", None
    return row.content, row.updated_at


def save_profile(db: Session, content: str) -> datetime:
    updated_at = db.execute(
        text(
            "insert into profile (id, content, updated_at) values (1, :content, now()) "
            "on conflict (id) do update set content = excluded.content, updated_at = now() "
            "returning updated_at"
        ),
        {"content": content},
    ).scalar_one()
    db.commit()
    return updated_at


def present_profile(content: str, updated_at: datetime | None) -> dict:
    result = sanitize_profile(content)
    return {
        "content": content,
        "updated_at": updated_at,
        "char_count": len(content),
        "groq_view": result.text,
        "redactions": {"emails": result.emails, "phones": result.phones, "lines": result.lines},
        "warnings": address_warnings(content),
    }


def get_profile_text(db: Session) -> str:
    content, _ = read_profile(db)
    cleaned = sanitize_profile(content).text
    if not cleaned:
        raise HTTPException(status_code=500, detail=NOT_SET_DETAIL)
    return cleaned
