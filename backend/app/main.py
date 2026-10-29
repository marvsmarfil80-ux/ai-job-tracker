from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.routers.hunts import router as hunts_router
from app.routers.jobs import router as jobs_router
from app.routers.notifications import router as notifications_router
from app.routers.profile import router as profile_router
from app.routers.score import router as score_router
from app.routers.settings import router as settings_router
from app.routers.sources import router as sources_router
from app.services.scheduler import SchedulerThread

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    scheduler = None
    if settings.scheduler_thread_enabled:
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
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type"],
)

app.include_router(jobs_router)
app.include_router(score_router)
app.include_router(hunts_router)
app.include_router(sources_router)
app.include_router(settings_router)
app.include_router(notifications_router)
app.include_router(profile_router)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("select 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}