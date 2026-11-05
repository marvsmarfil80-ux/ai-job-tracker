from collections.abc import Iterator
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.schemas.system_status import SystemStatus
from app.security import require_api_key
from app.services.system_status import HEALTH_TIMEOUT_SECONDS, build_status

router = APIRouter(tags=["system"], dependencies=[Depends(require_api_key)])


def get_health_client() -> Iterator[httpx.Client]:
    with httpx.Client(
        timeout=httpx.Timeout(HEALTH_TIMEOUT_SECONDS), follow_redirects=False
    ) as client:
        yield client


@router.get("/system/status", response_model=SystemStatus)
def system_status(
    db: Session = Depends(get_db),
    client: httpx.Client = Depends(get_health_client),
    config: Settings = Depends(get_settings),
) -> dict:
    return build_status(db, config, client, datetime.now(timezone.utc))