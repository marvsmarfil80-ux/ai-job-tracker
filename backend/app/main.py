import logging

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.routers.allowed_senders import router as allowed_senders_router
from app.routers.application_events import router as application_events_router
from app.routers.applications import router as applications_router
from app.routers.dashboard import router as dashboard_router
from app.routers.emails import router as emails_router
from app.routers.follow_ups import router as follow_ups_router
from app.routers.hunts import router as hunts_router
from app.routers.jobs import router as jobs_router
from app.routers.notifications import router as notifications_router
from app.routers.profile import router as profile_router
from app.routers.resume import router as resume_router
from app.routers.score import router as score_router
from app.routers.settings import router as settings_router
from app.routers.sources import router as sources_router
from app.routers.system_status import router as system_status_router
from app.services.orphan_runs import close_orphan_runs
from app.services.scheduler import SchedulerThread

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    scheduler = None
    if settings.scheduler_thread_enabled:
        try:
            close_orphan_runs()
        except Exception as exc:
            logger.warning("Could not close orphaned runs at startup: %s", type(exc).__name__)
        scheduler = SchedulerThread()
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.stop()


app = FastAPI(
    title="AI Job Tracker API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type"],
)

app.include_router(jobs_router)
app.include_router(score_router)
app.include_router(hunts_router)
app.include_router(sources_router)
app.include_router(settings_router)
app.include_router(notifications_router)
app.include_router(profile_router)
app.include_router(resume_router)
app.include_router(applications_router)
app.include_router(follow_ups_router)
app.include_router(emails_router)
app.include_router(allowed_senders_router)
app.include_router(application_events_router)
app.include_router(system_status_router)
app.include_router(dashboard_router)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("select 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}