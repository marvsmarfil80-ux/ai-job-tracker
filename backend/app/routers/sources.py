from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Source
from app.schemas.sources import SourceList, SourceOut, SourceUpdate
from app.security import require_api_key
from app.services.hunts import count_runs_today, effective_limit

router = APIRouter(prefix="/sources", tags=["sources"], dependencies=[Depends(require_api_key)])

SourceId = Path(ge=1, le=9223372036854775807)


def to_out(db: Session, source: Source) -> SourceOut:
    out = SourceOut.model_validate(source)
    return out.model_copy(
        update={
            "effective_max_runs_per_day": effective_limit(source.max_runs_per_day),
            "runs_today": count_runs_today(db, source.name),
        }
    )


@router.get("", response_model=SourceList)
def list_sources(db: Session = Depends(get_db)):
    sources = db.scalars(select(Source).order_by(Source.id)).all()
    items = [to_out(db, source) for source in sources]
    return SourceList(items=items, total=len(items))


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(payload: SourceUpdate, source_id: int = SourceId, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return to_out(db, source)