from fastapi import HTTPException
from app.config import get_settings
MAX_PROFILE_CHARS = 4000

def get_profile_text() -> str:
    path = get_settings().profile_path
    try:
        content = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="profile.txt is missing")
    except (OSError, UnicodeDecodeError):
        raise HTTPException(status_code=500, detail="profile.txt could not be read")
    if not content:
        raise HTTPException(status_code=500, detail="profile.txt is empty")
    if len(content) > MAX_PROFILE_CHARS:
        raise HTTPException(
            status_code=500,
            detail=f"profile.txt is longer than {MAX_PROFILE_CHARS} characters",
        )
    return content



