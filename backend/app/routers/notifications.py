from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.notifications import NotificationList, NotificationOut, NotificationUpdate
from app.security import require_api_key
from app.services.notifications import list_notifications, set_read

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_api_key)],
)

NotificationId = Path(ge=1, le=9223372036854775807)


@router.get("", response_model=NotificationList)
def get_notifications(
    unread: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1000000),
    db: Session = Depends(get_db),
):
    items, total, unread_count = list_notifications(db, unread, limit, offset)
    return NotificationList(
        items=items, total=total, unread_count=unread_count, limit=limit, offset=offset
    )


@router.patch("/{notification_id}", response_model=NotificationOut)
def update_notification(
    payload: NotificationUpdate,
    notification_id: int = NotificationId,
    db: Session = Depends(get_db),
):
    updated = set_read(db, notification_id, payload.is_read)
    if updated is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return updated