from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

MANILA = ZoneInfo("Asia/Manila")

def get_now() -> datetime:
    return datetime.now(timezone.utc)


def manila_today(now: datetime | None = None) -> date:
    current = now if now is not None else get_now()
    if current.tzinfo is None:
        raise ValueError("now must include a timezone")
    return current.astimezone(MANILA).date()

