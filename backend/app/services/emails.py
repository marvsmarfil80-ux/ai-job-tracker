from sqlalchemy import func, select
from sqlalchemy.orm import Session, defer

from app.models import Application, Email, Job


def build_item(email: Email, application: Application | None, job: Job | None) -> dict:
    linked = None
    if application is not None and job is not None:
        linked = {
            "id": application.id,
            "status": application.status,
            "job_title": job.title,
            "company": job.company,
        }
    return {
        "id": email.id,
        "kind": email.kind,
        "status": email.status,
        "email_class": email.email_class,
        "received_at": email.received_at,
        "sender": email.sender,
        "subject": email.subject,
        "snippet": email.snippet,
        "application": linked,
    }


def base_query():
    return (
        select(Email, Application, Job)
        .options(defer(Email.body_html))
        .outerjoin(Application, Application.id == Email.application_id)
        .outerjoin(Job, Job.id == Application.job_id)
    )


def list_emails(
    db: Session,
    kind: str | None,
    status: str | None,
    label: str | None,
    linked: bool | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    conditions = []
    if kind is not None:
        conditions.append(Email.kind == kind)
    if status is not None:
        conditions.append(Email.status == status)
    if label is not None:
        conditions.append(Email.email_class == label)
    if linked is True:
        conditions.append(Email.application_id.is_not(None))
    if linked is False:
        conditions.append(Email.application_id.is_(None))
    total = db.scalar(select(func.count()).select_from(Email).where(*conditions))
    rows = db.execute(
        base_query()
        .where(*conditions)
        .order_by(Email.received_at.desc(), Email.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [build_item(email, application, job) for email, application, job in rows], total


def get_email_item(db: Session, email_id: int) -> dict | None:
    row = db.execute(base_query().where(Email.id == email_id)).first()
    if row is None:
        return None
    email, application, job = row
    return build_item(email, application, job)