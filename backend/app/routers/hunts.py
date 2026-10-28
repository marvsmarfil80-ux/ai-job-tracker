from collections.abc import Iterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.hunts import HuntCreate, HuntList, HuntOut
from app.security import require_api_key
from app.services.feeds import get_feed_client
from app.services.hunts import list_runs, load_run, run_hunt

router = APIRouter(prefix="/hunts", tags=["hunts"], dependencies=[Depends(require_api_key)])

RunId = Path(ge=1, le=9223372036854775807)


def feed_client() -> Iterator[httpx.Client]:
    client = get_feed_client()
    try:
        yield client
    finally:
        client.close()


@router.post("", response_model=HuntOut, status_code=201)
def create_hunt(
    payload: HuntCreate | None = None,
    db: Session = Depends(get_db),
    client: httpx.Client = Depends(feed_client),
):
    requested = payload.sources if payload is not None else None
    return run_hunt(db, client, requested)


@router.get("", response_model=HuntList)
def get_hunts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1000000),
    db: Session = Depends(get_db),
):
    items, total = list_runs(db, limit, offset)
    return HuntList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{run_id}", response_model=HuntOut)
def get_hunt(run_id: int = RunId, db: Session = Depends(get_db)):
    run = load_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Hunt not found")
    return run