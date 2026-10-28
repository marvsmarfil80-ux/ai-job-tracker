from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.routers.hunts import router as hunts_router
from app.routers.jobs import router as jobs_router
from app.routers.score import router as score_router
from app.routers.settings import router as settings_router
from app.routers.sources import router as sources_router

settings = get_settings()

app = FastAPI(
    title="AI Job Tracker API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
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


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("select 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}