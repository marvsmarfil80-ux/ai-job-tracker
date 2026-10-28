from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.settings import SettingsOut, SettingsUpdate
from app.security import require_api_key
from app.services.settings import present, read_values, update_settings

router = APIRouter(
    prefix="/settings", tags=["settings"], dependencies=[Depends(require_api_key)]
)


@router.get("", response_model=SettingsOut)
def show_settings(db: Session = Depends(get_db)):
    return present(read_values(db))


@router.patch("", response_model=SettingsOut)
def change_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    changes = payload.model_dump(exclude_unset=True)
    return present(update_settings(db, changes))