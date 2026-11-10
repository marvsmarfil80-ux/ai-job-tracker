import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from sqlalchemy import and_, exists, func, not_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Application, Job
from app.schemas.extract import ExtractRequest, ExtractResponse
from app.schemas.jobs import (
    JobCreate,
    JobList,
    JobOut,
    JobSort,
    JobUpdate,
    PipelineStatus,
    Source,
    Verdict,
)
from app.security import require_api_key
from app.services.extract import run_extract
from app.services.groq_client import get_groq_client
from app.services.jobs import (
    NO_EXTRAS,
    JobExtras,
    clean_description,
    extras_for_job,
    get_thresholds,
    latest_scores,
    priority_for_source,
    verdict_for,
)
from app.services.normalize import normalize_url

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_api_key)])

JobId = Path(ge=1, le=9223372036854775807)


def to_out(job: Job, extras: JobExtras, apply_threshold: int, maybe_threshold: int) -> JobOut:
    out = JobOut.model_validate(job)
    return out.model_copy(
        update={
            "score": extras.score,
            "verdict": verdict_for(extras.score, apply_threshold, maybe_threshold),
            "reason": extras.reason,
            "red_flags": extras.red_flags,
            "application_id": extras.application_id,
        }
    )

def duplicate_response(existing_id: int) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "Job already exists", "existing_id": existing_id},
    )


def get_job_or_404(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("", response_model=JobOut, status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    normalized = normalize_url(payload.url)
    existing_id = db.scalar(select(Job.id).where(Job.url_normalized == normalized))
    if existing_id is not None:
        return duplicate_response(existing_id)

    job = Job(
        source=payload.source,
        title=payload.title,
        company=payload.company,
        url=payload.url,
        url_normalized=normalized,
        description=clean_description(payload.description),
        location=payload.location,
        work_mode=payload.work_mode,
        published=payload.published,
        priority=priority_for_source(payload.source),
        pipeline_status="new",
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_id = db.scalar(select(Job.id).where(Job.url_normalized == normalized))
        if existing_id is not None:
            return duplicate_response(existing_id)
        raise
    db.refresh(job)
    apply_threshold, maybe_threshold = get_thresholds(db)
    return to_out(job, NO_EXTRAS, apply_threshold, maybe_threshold)

@router.post("/extract", response_model=ExtractResponse)
def extract_job_fields(
    payload: ExtractRequest,
    db: Session = Depends(get_db),
    client: httpx.Client = Depends(get_groq_client),
):
    normalized = normalize_url(payload.url)
    existing_id = db.scalar(select(Job.id).where(Job.url_normalized == normalized))
    if existing_id is not None:
        return duplicate_response(existing_id)
    return run_extract(db, client, normalized, payload.page_text)


@router.get("", response_model=JobList)
def list_jobs(
    min_score: int | None = Query(default=None, ge=0, le=100),
    source: Source | None = None,
    verdict: Verdict | None = None,
    q: str | None = Query(default=None, min_length=1, max_length=200),
    pipeline_status: PipelineStatus | None = None,
    awaiting_apply: bool | None = None,
    dismissed: bool | None = None,
    has_application: bool | None = None,
    sort: JobSort = "default",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1000000),
    db: Session = Depends(get_db),
):
    apply_threshold, maybe_threshold = get_thresholds(db)
    latest = latest_scores()

    conditions = []
    if min_score is not None:
        conditions.append(latest.c.score >= min_score)
    if source is not None:
        conditions.append(Job.source == source)
    if pipeline_status is not None:
        conditions.append(Job.pipeline_status == pipeline_status)
    if awaiting_apply is not None:
        awaiting = and_(
            Job.opened_at.is_not(None),
            Application.id.is_(None),
            Job.dismissed_at.is_(None),
        )
        conditions.append(awaiting if awaiting_apply else not_(awaiting))
    if dismissed is not None:
        conditions.append(
            Job.dismissed_at.is_not(None) if dismissed else Job.dismissed_at.is_(None)
        )
    if has_application is not None:
        conditions.append(
            Application.id.is_not(None) if has_application else Application.id.is_(None)
        )
    if q is not None:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(Job.title.ilike(pattern, escape="\\"), Job.company.ilike(pattern, escape="\\"))
        )
    if verdict == "apply":
        conditions.append(latest.c.score >= apply_threshold)
    elif verdict == "maybe":
        conditions.append(and_(latest.c.score >= maybe_threshold, latest.c.score < apply_threshold))
    elif verdict == "skip":
        conditions.append(latest.c.score < maybe_threshold)

    def joined(statement):
        statement = statement.select_from(Job)
        statement = statement.outerjoin(latest, latest.c.job_id == Job.id)
        statement = statement.outerjoin(Application, Application.job_id == Job.id)
        return statement.where(*conditions) if conditions else statement

    if sort == "score_desc":
        order = (latest.c.score.desc().nulls_last(), Job.created_at.desc(), Job.id.desc())
    else:
        order = (Job.priority.desc(), Job.created_at.desc(), Job.id.desc())

    total = db.scalar(joined(select(func.count())))
    rows = db.execute(
        joined(
            select(
                Job,
                latest.c.score,
                latest.c.reason,
                latest.c.red_flags,
                Application.id,
            )
        )
        .order_by(*order)
        .limit(limit)
        .offset(offset)
    ).all()

    items = [
        to_out(job, JobExtras(score, reason, red_flags, application_id), apply_threshold, maybe_threshold)
        for job, score, reason, red_flags, application_id in rows
    ]
    return JobList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int = JobId, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    apply_threshold, maybe_threshold = get_thresholds(db)
    return to_out(job, extras_for_job(db, job_id), apply_threshold, maybe_threshold)


@router.patch("/{job_id}", response_model=JobOut)
def update_job(payload: JobUpdate, job_id: int = JobId, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    changes = payload.model_dump(exclude_unset=True)
    if "description" in changes:
        changes["description"] = clean_description(changes["description"])
    for field, value in changes.items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    apply_threshold, maybe_threshold = get_thresholds(db)
    return to_out(job, extras_for_job(db, job_id), apply_threshold, maybe_threshold)

@router.post("/{job_id}/open", response_model=JobOut)
def mark_job_opened(job_id: int = JobId, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    db.execute(
        update(Job)
        .where(Job.id == job_id, Job.opened_at.is_(None))
        .values(opened_at=func.now())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    db.refresh(job)
    apply_threshold, maybe_threshold = get_thresholds(db)
    return to_out(job, extras_for_job(db, job_id), apply_threshold, maybe_threshold)

@router.post("/{job_id}/dismiss", response_model=JobOut)
def dismiss_job(job_id: int = JobId, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    if job.dismissed_at is None:
        has_application = db.scalar(select(exists().where(Application.job_id == job_id)))
        if has_application:
            raise HTTPException(status_code=409, detail="This job already has an application.")
        db.execute(
            update(Job)
            .where(Job.id == job_id, Job.dismissed_at.is_(None))
            .values(dismissed_at=func.now())
            .execution_options(synchronize_session=False)
        )
        db.commit()
        db.refresh(job)
    apply_threshold, maybe_threshold = get_thresholds(db)
    return to_out(job, extras_for_job(db, job_id), apply_threshold, maybe_threshold)


@router.post("/{job_id}/restore", response_model=JobOut)
def restore_job(job_id: int = JobId, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    if job.dismissed_at is not None:
        db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(dismissed_at=None)
            .execution_options(synchronize_session=False)
        )
        db.commit()
        db.refresh(job)
    apply_threshold, maybe_threshold = get_thresholds(db)
    return to_out(job, extras_for_job(db, job_id), apply_threshold, maybe_threshold)

