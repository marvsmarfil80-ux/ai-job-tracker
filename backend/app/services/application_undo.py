from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application, ApplicationEvent, Job
from app.schemas.applications import ApplicationDetail
from app.services.applications import build_detail, change_status


def undo_email_event(db: Session, event_id: int) -> ApplicationDetail:
    event = db.get(ApplicationEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Application event not found")
    if event.source != "email":
        raise HTTPException(
            status_code=422, detail="Only email status changes can be undone"
        )
    application = db.get(Application, event.application_id, with_for_update=True)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if event.email_id is not None:
        undone = db.scalar(
            select(ApplicationEvent.id)
            .where(
                ApplicationEvent.application_id == event.application_id,
                ApplicationEvent.source == "undo",
                ApplicationEvent.email_id == event.email_id,
                ApplicationEvent.id > event.id,
            )
            .limit(1)
        )
        if undone is not None:
            raise HTTPException(
                status_code=409, detail="This status change was already undone"
            )
    latest = db.scalar(
        select(func.max(ApplicationEvent.id)).where(
            ApplicationEvent.application_id == event.application_id
        )
    )
    if latest != event.id:
        raise HTTPException(
            status_code=409, detail="The status has changed since this event"
        )
    if event.from_status is None:
        raise HTTPException(status_code=422, detail="This event cannot be undone")
    change_status(
        db, application, event.from_status, source="undo", email_id=event.email_id
    )
    db.commit()
    job = db.get(Job, application.job_id)
    return build_detail(db, application, job)