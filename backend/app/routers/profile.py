from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.profile import ProfileOut, ProfileUpdate
from app.security import require_api_key
from app.services.profile import present_profile, read_profile, save_profile

router = APIRouter(
    prefix="/profile", tags=["profile"], dependencies=[Depends(require_api_key)]
)


@router.get("", response_model=ProfileOut)
def show_profile(db: Session = Depends(get_db)):
    content, updated_at = read_profile(db)
    return present_profile(content, updated_at)


@router.put("", response_model=ProfileOut)
def replace_profile(payload: ProfileUpdate, db: Session = Depends(get_db)):
    updated_at = save_profile(db, payload.content)
    return present_profile(payload.content, updated_at)
