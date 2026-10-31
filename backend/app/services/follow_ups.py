from datetime import date, datetime

from sqlalchemy import and_, case
from sqlalchemy.orm import Session

from app.models import Application, FollowUp, Job
from app.schemas.follow_ups import (
    ApplicationSummary,
    FollowUpCreate,
    FollowUpDetail,
    FollowUpOut,
)


def is_overdue(status: str, due_date: date | None, today: date) -> bool:
    return status == "pending" and due_date is not None and due_date < today


def overdue_condition(today: date):
    return and_(
        FollowUp.status == "pending",
        FollowUp.due_date.is_not(None),
        FollowUp.due_date < today,
    )


def list_order():
    is_pending = FollowUp.status == "pending"
    return (
        case((is_pending, 0), else_=1),
        case((is_pending, FollowUp.due_date)).asc().nulls_last(),
        FollowUp.completed_at.desc().nulls_last(),
        FollowUp.id.asc(),
    )


def build_out(follow_up: FollowUp, today: date) -> FollowUpOut:
    return FollowUpOut(
        id=follow_up.id,
        application_id=follow_up.application_id,
        title=follow_up.title,
        due_date=follow_up.due_date,
        status=follow_up.status,
        completed_at=follow_up.completed_at,
        created_at=follow_up.created_at,
        is_overdue=is_overdue(follow_up.status, follow_up.due_date, today),
    )


def build_detail(
    follow_up: FollowUp, application: Application, job: Job, today: date
) -> FollowUpDetail:
    return FollowUpDetail(
        **build_out(follow_up, today).model_dump(),
        application=ApplicationSummary(
            application_id=application.id,
            application_status=application.status,
            job_title=job.title,
            job_company=job.company,
        ),
    )


def create_follow_up(db: Session, payload: FollowUpCreate) -> FollowUp:
    follow_up = FollowUp(
        application_id=payload.application_id,
        title=payload.title,
        due_date=payload.due_date,
        status="pending",
        completed_at=None,
    )
    db.add(follow_up)
    db.commit()
    db.refresh(follow_up)
    return follow_up


def update_follow_up(
    db: Session, follow_up: FollowUp, changes: dict, now: datetime
) -> None:
    if "title" in changes:
        follow_up.title = changes["title"]
    if "due_date" in changes:
        follow_up.due_date = changes["due_date"]
    new_status = changes.get("status")
    if new_status is not None and new_status != follow_up.status:
        follow_up.status = new_status
        follow_up.completed_at = now if new_status == "completed" else None
    db.commit()