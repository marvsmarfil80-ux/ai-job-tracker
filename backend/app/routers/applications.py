from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Application, Job
from app.schemas.applications import (
    MAX_ID,
    ApplicationCreate,
    ApplicationDetail,
    ApplicationList,
    ApplicationOut,
    ApplicationStatus,
    ApplicationUpdate,
)

from app.security import require_api_key
from app.services.applications import (
    build_detail,
    build_out,
    create_application,
    update_application,
)

router = APIRouter(
    prefix="/applications", tags=["applications"], dependencies=[Depends(require_api_key)]
)

ApplicationId = Path(ge=1, le=MAX_ID)


def duplicate_response(existing_id: int) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Application already exists for this job",
            "existing_id": existing_id,
        },
    )


def get_application_or_404(db: Session, application_id: int) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.post("", response_model=ApplicationOut, status_code=201)
def create(payload: ApplicationCreate, db: Session = Depends(get_db)):
    job = db.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    existing_id = db.scalar(select(Application.id).where(Application.job_id == payload.job_id))
    if existing_id is not None:
        return duplicate_response(existing_id)
    try:
        application = create_application(db, payload)
    except IntegrityError:
        db.rollback()
        existing_id = db.scalar(select(Application.id).where(Application.job_id == payload.job_id))
        if existing_id is not None:
            return duplicate_response(existing_id)
        raise
    return build_out(application, job)


@router.get("", response_model=ApplicationList)
def list_applications(
    status: ApplicationStatus | None = None,
    job_id: int | None = Query(default=None, ge=1, le=MAX_ID),
    q: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1000000),
    db: Session = Depends(get_db),
):
    conditions = []
    if status is not None:
        conditions.append(Application.status == status)
    if job_id is not None:
        conditions.append(Application.job_id == job_id)
    if q is not None:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(Job.title.ilike(pattern, escape="\\"), Job.company.ilike(pattern, escape="\\"))
        )

    total = db.scalar(
        select(func.count())
        .select_from(Application)
        .join(Job, Job.id == Application.job_id)
        .where(*conditions)
    )
    rows = db.execute(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(*conditions)
        .order_by(Application.applied_at.desc().nulls_last(), Application.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    items = [build_out(application, job) for application, job in rows]
    return ApplicationList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: int = ApplicationId, db: Session = Depends(get_db)):
    application = get_application_or_404(db, application_id)
    job = db.get(Job, application.job_id)
    return build_detail(db, application, job)


@router.patch("/{application_id}", response_model=ApplicationDetail)
def change_application(
    payload: ApplicationUpdate,
    application_id: int = ApplicationId,
    db: Session = Depends(get_db),
):
    application = get_application_or_404(db, application_id)
    update_application(db, application, payload.model_dump(exclude_unset=True))
    job = db.get(Job, application.job_id)
    return build_detail(db, application, job)

