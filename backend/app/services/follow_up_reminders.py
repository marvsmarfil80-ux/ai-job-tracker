import re
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.notifications import insert_notification

TYPE_FOLLOW_UP_OVERDUE = "follow_up_overdue"
MAX_PART_LENGTH = 100
TAG_PATTERN = re.compile(r"<[^>]*>")
SPACE_PATTERN = re.compile(r"\s+")

SELECT_NEEDING_REMINDER = text(
    "select f.id, f.title, f.due_date, j.title as job_title, j.company as company "
    "from follow_ups f "
    "join applications a on a.id = f.application_id "
    "join jobs j on j.id = a.job_id "
    "where f.status = 'pending' and f.due_date is not null and f.due_date < :today "
    "and not exists ("
    "select 1 from notifications n "
    "where n.type = 'follow_up_overdue' "
    "and n.link = '/follow-ups/' || cast(f.id as text) "
    "and n.created_at >= (cast(f.due_date + 1 as timestamp) at time zone 'Asia/Manila')"
    ") order by f.due_date asc, f.id asc"
)


def clean_part(value: str | None) -> str:
    if not value:
        return ""
    without_tags = TAG_PATTERN.sub(" ", value)
    plain = without_tags.replace("<", "").replace(">", "")
    collapsed = SPACE_PATTERN.sub(" ", plain).strip()
    return collapsed[:MAX_PART_LENGTH].strip()


def build_reminder_message(
    title: str, job_title: str | None, company: str | None, due_date: date
) -> str:
    job = clean_part(job_title)
    firm = clean_part(company)
    if job and firm:
        where = f"{job} at {firm}"
    else:
        where = job or firm
    context = f" ({where})" if where else ""
    name = clean_part(title) or "Untitled follow-up"
    return f"Follow-up overdue: {name}{context}, due {due_date.isoformat()}"


def find_overdue_without_reminder(db: Session, today: date) -> list[dict]:
    rows = db.execute(SELECT_NEEDING_REMINDER, {"today": today}).mappings().all()
    return [dict(row) for row in rows]


def create_reminder(db: Session, row: dict) -> None:
    message = build_reminder_message(
        row["title"], row["job_title"], row["company"], row["due_date"]
    )
    insert_notification(db, TYPE_FOLLOW_UP_OVERDUE, message, f"/follow-ups/{row['id']}")
    db.commit()