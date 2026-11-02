import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Application, Email
from app.schemas.applications import MAX_ID
from app.schemas.emails import (
    EmailClass,
    EmailKind,
    EmailList,
    EmailOut,
    EmailProcessResponse,
    EmailStatus,
    EmailUpdate,
)
from app.security import require_api_key
from app.services.email_processing import run_email_processing
from app.services.email_sync import finish_sync, start_sync
from app.services.emails import get_email_item, list_emails
from app.services.groq_client import get_groq_client
from app.services.hunts import TRIGGER_MANUAL

router = APIRouter(prefix="/emails", tags=["emails"], dependencies=[Depends(require_api_key)])

EmailId = Path(ge=1, le=MAX_ID)


@router.post("/process", response_model=EmailProcessResponse)
def process_emails(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    client: httpx.Client = Depends(get_groq_client),
):
    return run_email_processing(db, client, limit)

@router.post("/sync", status_code=202)
def sync_emails(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    run_id = start_sync(db, TRIGGER_MANUAL)
    background_tasks.add_task(finish_sync, run_id)
    return {"run_id": run_id}


@router.get("", response_model=EmailList)
def get_emails(
    kind: EmailKind | None = None,
    status: EmailStatus | None = None,
    email_class: EmailClass | None = Query(default=None, alias="class"),
    linked: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1000000),
    db: Session = Depends(get_db),
):
    items, total = list_emails(db, kind, status, email_class, linked, limit, offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{email_id}", response_model=EmailOut)
def get_email(email_id: int = EmailId, db: Session = Depends(get_db)):
    item = get_email_item(db, email_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return item


@router.patch("/{email_id}", response_model=EmailOut)
def change_email(
    payload: EmailUpdate,
    email_id: int = EmailId,
    db: Session = Depends(get_db),
):
    email = db.get(Email, email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    if email.kind != "application":
        raise HTTPException(
            status_code=422, detail="Only application emails can be linked"
        )
    if payload.application_id is not None:
        if db.get(Application, payload.application_id) is None:
            raise HTTPException(status_code=404, detail="Application not found")
    email.application_id = payload.application_id
    db.commit()
    return get_email_item(db, email_id)