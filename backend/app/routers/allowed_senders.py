from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AllowedSender
from app.schemas.allowed_senders import (
    AllowedSenderCreate,
    AllowedSenderList,
    AllowedSenderOut,
    AllowedSenderUpdate,
)
from app.schemas.applications import MAX_ID
from app.security import require_api_key

router = APIRouter(
    prefix="/allowed-senders",
    tags=["allowed-senders"],
    dependencies=[Depends(require_api_key)],
)

SenderId = Path(ge=1, le=MAX_ID)
DUPLICATE_DETAIL = "Allowed sender already exists"


@router.get("", response_model=AllowedSenderList)
def list_senders(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(AllowedSender).order_by(AllowedSender.id)))
    return {"items": rows, "total": len(rows)}


@router.post("", response_model=AllowedSenderOut, status_code=201)
def add_sender(payload: AllowedSenderCreate, db: Session = Depends(get_db)):
    existing = db.scalar(
        select(AllowedSender.id).where(
            AllowedSender.sender == payload.sender, AllowedSender.kind == payload.kind
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail=DUPLICATE_DETAIL)
    row = AllowedSender(sender=payload.sender, kind=payload.kind)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=DUPLICATE_DETAIL)
    db.refresh(row)
    return row


@router.patch("/{sender_id}", response_model=AllowedSenderOut)
def change_sender(
    payload: AllowedSenderUpdate,
    sender_id: int = SenderId,
    db: Session = Depends(get_db),
):
    row = db.get(AllowedSender, sender_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Allowed sender not found")
    row.enabled = payload.enabled
    db.commit()
    return row