import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.score import ScoreRunResponse
from app.security import require_api_key
from app.services.groq_client import get_groq_client
from app.services.scoring import run_scoring

router = APIRouter(prefix="/score", tags=["score"], dependencies=[Depends(require_api_key)])


@router.post("/run", response_model=ScoreRunResponse)
def score_run(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    client: httpx.Client = Depends(get_groq_client),
):
    return run_scoring(db, client, limit)