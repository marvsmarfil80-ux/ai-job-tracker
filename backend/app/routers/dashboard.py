from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Application, FollowUp, Job
from app.schemas.dashboard import DashboardSummary
from app.security import require_api_key
from app.services.jobs import get_thresholds, latest_scores

router = APIRouter(
    prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_api_key)]
)


@router.get("/summary", response_model=DashboardSummary)
def get_summary(db: Session = Depends(get_db)):
    apply_threshold, _ = get_thresholds(db)
    latest = latest_scores()

    total_applications = db.scalar(select(func.count()).select_from(Application))
    interviews = db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.status == "interview")
    )
    pending_follow_ups = db.scalar(
        select(func.count()).select_from(FollowUp).where(FollowUp.status == "pending")
    )
    jobs_discovered = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.dismissed_at.is_(None), Job.pipeline_status != "filtered_out")
    )
    recommended_jobs = db.scalar(
        select(func.count())
        .select_from(Job)
        .outerjoin(latest, latest.c.job_id == Job.id)
        .outerjoin(Application, Application.job_id == Job.id)
        .where(
            latest.c.score >= apply_threshold,
            Job.dismissed_at.is_(None),
            Application.id.is_(None),
        )
    )
    return DashboardSummary(
        total_applications=total_applications,
        interviews=interviews,
        pending_follow_ups=pending_follow_ups,
        jobs_discovered=jobs_discovered,
        recommended_jobs=recommended_jobs,
    )