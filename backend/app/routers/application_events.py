from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.applications import MAX_ID, ApplicationDetail
from app.security import require_api_key
from app.services.application_undo import undo_email_event

router = APIRouter(
    prefix="/application-events",
    tags=["application-events"],
    dependencies=[Depends(require_api_key)],
)

EventId = Path(ge=1, le=MAX_ID)


@router.post("/{event_id}/undo", response_model=ApplicationDetail)
def undo_event(event_id: int = EventId, db: Session = Depends(get_db)):
    return undo_email_event(db, event_id)