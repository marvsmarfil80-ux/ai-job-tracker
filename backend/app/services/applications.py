from datetime import datetime, timezone

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.models import Application, ApplicationEvent, Email, FollowUp, Job
from app.schemas.applications import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationEventOut,
    ApplicationOut,
    JobSummary,
)


def build_out(application: Application, job: Job) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        job_id=application.job_id,
        status=application.status,
        applied_at=application.applied_at,
        notes=application.notes,
        job=JobSummary.model_validate(job),
    )


def list_events(db: Session, application_id: int) -> list[ApplicationEvent]:
    return list(
        db.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application_id)
            .order_by(ApplicationEvent.changed_at.asc(), ApplicationEvent.id.asc())
        )
    )


def build_detail(db: Session, application: Application, job: Job) -> ApplicationDetail:
    events = [ApplicationEventOut.model_validate(event) for event in list_events(db, application.id)]
    return ApplicationDetail(**build_out(application, job).model_dump(), events=events)


def create_application(db: Session, payload: ApplicationCreate) -> Application:
    application = Application(
        job_id=payload.job_id,
        status="applied",
        applied_at=payload.applied_at or datetime.now(timezone.utc),
        notes=payload.notes,
    )
    db.add(application)
    db.flush()
    db.add(
        ApplicationEvent(
            application_id=application.id,
            from_status=None,
            to_status="applied",
        )
    )
    db.commit()
    return application


def change_status(
    db: Session,
    application: Application,
    new_status: str,
    source: str = "manual",
    email_id: int | None = None,
) -> bool:
    if new_status == application.status:
        return False
    previous = application.status
    application.status = new_status
    db.flush()
    db.add(
        ApplicationEvent(
            application_id=application.id,
            from_status=previous,
            to_status=new_status,
            source=source,
            email_id=email_id,
        )
    )
    return True


def update_application(db: Session, application: Application, changes: dict) -> None:
    if "notes" in changes:
        application.notes = changes["notes"]
    new_status = changes.get("status")
    if new_status is not None:
        change_status(db, application, new_status)
    db.commit()

HISTORY_MESSAGE = "This application has history. Set its status to withdrawn instead."


def application_has_history(db: Session, application: Application) -> bool:
    if application.status != "applied":
        return True
    events = list_events(db, application.id)
    if len(events) != 1:
        return True
    event = events[0]
    if (
        event.from_status is not None
        or event.to_status != "applied"
        or event.source != "manual"
        or event.email_id is not None
    ):
        return True
    linked_email = db.scalar(select(exists().where(Email.application_id == application.id)))
    return bool(linked_email)


def delete_application(db: Session, application: Application) -> None:
    application_id = application.id
    db.execute(
        delete(FollowUp)
        .where(FollowUp.application_id == application_id)
        .execution_options(synchronize_session=False)
    )
    db.execute(
        delete(ApplicationEvent)
        .where(ApplicationEvent.application_id == application_id)
        .execution_options(synchronize_session=False)
    )
    db.execute(
        delete(Application)
        .where(Application.id == application_id)
        .execution_options(synchronize_session=False)
    )
    db.commit()