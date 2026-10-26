from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Job
from app.schemas.jobs import (
    JobCreate,
    JobList,
    JobOut,
    JobUpdate,
    PipelineStatus,
    Source,
    Verdict,
)
from app.security import require_api_key
from app.services.jobs import (
    clean_description,
    get_thresholds,
    latest_score_for_job,
    latest_scores,
    priority_for_source,
    verdict_for,
)
from app.services.normalize import normalize_url

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_api_key)])

JobId = Path(ge=1, le=9223372036854775807)


def to_out(job: Job, score: int | None, apply_threshold: int, maybe_threshold: int) -> JobOut:
    out = JobOut.model_validate(job)
    return out.model_copy(
        update={
            "score": score,
            "verdict": verdict_for(score, apply_threshold, maybe_threshold),
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
    return to_out(job, None, apply_threshold, maybe_threshold)


@router.get("", response_model=JobList)
def list_jobs(
    min_score: int | None = Query(default=None, ge=0, le=100),
    source: Source | None = None,
    verdict: Verdict | None = None,
    q: str | None = Query(default=None, min_length=1, max_length=200),
    pipeline_status: PipelineStatus | None = None,
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

    def filtered(statement):
        return statement.where(*conditions) if conditions else statement

    total = db.scalar(
        filtered(select(func.count()).select_from(Job).outerjoin(latest, latest.c.job_id == Job.id))
    )
    rows = db.execute(
        filtered(select(Job, latest.c.score).outerjoin(latest, latest.c.job_id == Job.id))
        .order_by(Job.priority.desc(), Job.created_at.desc(), Job.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    items = [to_out(job, score, apply_threshold, maybe_threshold) for job, score in rows]
    return JobList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int = JobId, db: Session = Depends(get_db)):
    job = get_job_or_404(db, job_id)
    apply_threshold, maybe_threshold = get_thresholds(db)
    return to_out(job, latest_score_for_job(db, job_id), apply_threshold, maybe_threshold)


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
    return to_out(job, latest_score_for_job(db, job_id), apply_threshold, maybe_threshold)
