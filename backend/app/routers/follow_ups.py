from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy import func, not_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Application, FollowUp, Job
from app.schemas.applications import MAX_ID
from app.schemas.follow_ups import (
    FollowUpCreate,
    FollowUpDetail,
    FollowUpList,
    FollowUpOut,
    FollowUpStatus,
    FollowUpUpdate,
)
from app.security import require_api_key
from app.services.clock import get_now, manila_today
from app.services.follow_ups import (
    build_detail,
    build_out,
    create_follow_up,
    list_order,
    overdue_condition,
    update_follow_up,
)

router = APIRouter(
    prefix="/follow-ups", tags=["follow-ups"], dependencies=[Depends(require_api_key)]
)

FollowUpId = Path(ge=1, le=MAX_ID)


def joined_select():
    return (
        select(FollowUp, Application, Job)
        .join(Application, Application.id == FollowUp.application_id)
        .join(Job, Job.id == Application.job_id)
    )


def get_row_or_404(db: Session, follow_up_id: int):
    row = db.execute(joined_select().where(FollowUp.id == follow_up_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    return row


@router.post("", response_model=FollowUpOut, status_code=201)
def create(
    payload: FollowUpCreate,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    if db.get(Application, payload.application_id) is None:
        raise HTTPException(status_code=404, detail="Application not found")
    follow_up = create_follow_up(db, payload)
    return build_out(follow_up, manila_today(now))


@router.get("", response_model=FollowUpList)
def list_follow_ups(
    status: FollowUpStatus | None = None,
    application_id: int | None = Query(default=None, ge=1, le=MAX_ID),
    overdue: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1000000),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    today = manila_today(now)
    conditions = []
    if status is not None:
        conditions.append(FollowUp.status == status)
    if application_id is not None:
        conditions.append(FollowUp.application_id == application_id)
    if overdue is True:
        conditions.append(overdue_condition(today))
    if overdue is False:
        conditions.append(not_(overdue_condition(today)))

    total = db.scalar(select(func.count()).select_from(FollowUp).where(*conditions))
    rows = db.execute(
        joined_select()
        .where(*conditions)
        .order_by(*list_order())
        .limit(limit)
        .offset(offset)
    ).all()
    items = [build_detail(f, a, j, today) for f, a, j in rows]
    return FollowUpList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{follow_up_id}", response_model=FollowUpDetail)
def get_follow_up(
    follow_up_id: int = FollowUpId,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    follow_up, application, job = get_row_or_404(db, follow_up_id)
    return build_detail(follow_up, application, job, manila_today(now))


@router.patch("/{follow_up_id}", response_model=FollowUpDetail)
def change_follow_up(
    payload: FollowUpUpdate,
    follow_up_id: int = FollowUpId,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    follow_up, application, job = get_row_or_404(db, follow_up_id)
    update_follow_up(db, follow_up, payload.model_dump(exclude_unset=True), now)
    return build_detail(follow_up, application, job, manila_today(now))


@router.delete("/{follow_up_id}", status_code=204)
def delete_follow_up(follow_up_id: int = FollowUpId, db: Session = Depends(get_db)):
    follow_up = db.get(FollowUp, follow_up_id)
    if follow_up is None:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    db.delete(follow_up)
    db.commit()
    return Response(status_code=204)