from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, ApplicationEvent, Job
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


def update_application(db: Session, application: Application, changes: dict) -> None:
    if "notes" in changes:
        application.notes = changes["notes"]
    new_status = changes.get("status")
    if new_status is not None and new_status != application.status:
        previous = application.status
        application.status = new_status
        db.flush()
        db.add(
            ApplicationEvent(
                application_id=application.id,
                from_status=previous,
                to_status=new_status,
            )
        )
    db.commit()