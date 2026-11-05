from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DatabaseStatus(BaseModel):
    status: Literal["ok", "error"]
    schema_version: str | None


class GroqStatus(BaseModel):
    api_key_configured: bool
    mock_mode: bool


class N8nStatus(BaseModel):
    status: Literal["ok", "error", "not_configured"]
    http_status: int | None


class EmailSyncStatus(BaseModel):
    last_run_id: int | None
    last_run_status: Literal["running", "done", "error"] | None
    last_run_finished_at: datetime | None
    last_successful_run_at: datetime | None


class ProfileStatus(BaseModel):
    is_set: bool


class SchedulerStatus(BaseModel):
    enabled: bool
    followup_reminders_enabled: bool


class SystemStatus(BaseModel):
    status: Literal["ok", "degraded"]
    checked_at: datetime
    database: DatabaseStatus
    groq: GroqStatus
    n8n: N8nStatus
    email_sync: EmailSyncStatus
    profile: ProfileStatus
    scheduler: SchedulerStatus