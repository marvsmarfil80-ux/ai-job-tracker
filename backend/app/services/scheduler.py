import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import text

from app.db import SessionLocal
from app.services.feeds import get_feed_client
from app.services.groq_client import get_groq_client
from app.services.hunts import TRIGGER_SCHEDULED, run_hunt
from app.services.scoring import run_scoring
from app.services.settings import read_values

COMPONENT = "scheduler"
TICK_SECONDS = 60.0
WARNING_REPEAT_SECONDS = 3600.0
STOP_LEVELS = {
    "rate_limited": "warning",
    "groq_unavailable": "warning",
    "groq_auth_error": "error",
}


@dataclass
class SchedulerState:
    last_score_attempt: datetime | None = None
    last_warning: dict[str, datetime] = field(default_factory=dict)


def default_groq_client():
    return contextlib.contextmanager(get_groq_client)()


def default_feed_client():
    return contextlib.closing(get_feed_client())


def log_event(session_factory, level: str, message: str, run_id: int | None = None) -> None:
    try:
        with session_factory() as db:
            db.execute(
                text(
                    "insert into system_events (component, level, run_id, message) "
                    "values (:component, :level, :run_id, :message)"
                ),
                {"component": COMPONENT, "level": level, "run_id": run_id, "message": message},
            )
            db.commit()
    except Exception:
        pass


def warn_once(state: SchedulerState, session_factory, now: datetime, level: str, message: str) -> None:
    last = state.last_warning.get(message)
    if last is not None and (now - last).total_seconds() < WARNING_REPEAT_SECONDS:
        return
    state.last_warning[message] = now
    log_event(session_factory, level, message)


def hunt_is_due(db, now: datetime, hours: int) -> bool:
    last = db.execute(text("select max(started_at) from search_runs")).scalar_one()
    return last is None or last <= now - timedelta(hours=hours)


def scoring_has_work(db) -> bool:
    return db.execute(
        text("select exists (select 1 from jobs where pipeline_status = 'new')")
    ).scalar_one()


def hunt_step(now, state, values, session_factory, feed_client_factory) -> str:
    with session_factory() as db:
        if not hunt_is_due(db, now, values["hunt_interval_hours"]):
            return "not_due"
        try:
            with feed_client_factory() as client:
                result = run_hunt(db, client, None, TRIGGER_SCHEDULED)
        except HTTPException as exc:
            if exc.status_code == 409:
                return "locked"
            raise
    log_event(
        session_factory,
        "info",
        f"Scheduled hunt finished: run {result['id']} {result['status']}",
        result["id"],
    )
    return "ran"


def score_step(now, state, values, session_factory, groq_client_factory, sleep) -> str:
    previous = state.last_score_attempt
    interval = timedelta(minutes=values["score_interval_minutes"])
    if previous is not None and now - previous < interval:
        return "not_due"
    with session_factory() as db:
        if not scoring_has_work(db):
            return "no_new_jobs"
        state.last_score_attempt = now
        try:
            with groq_client_factory() as client:
                result = run_scoring(db, client, values["score_batch_limit"], sleep)
        except HTTPException as exc:
            if exc.status_code == 409:
                state.last_score_attempt = previous
                return "locked"
            detail = str(exc.detail)
            level = "warning" if detail.startswith("Profile is not set") else "error"
            warn_once(state, session_factory, now, level, f"Scheduled scoring skipped: {detail}")
            return "skipped"
    reason = result["stopped_reason"]
    summary = (
        f"Scheduled scoring: attempted {result['attempted']}, scored {result['scored']}, "
        f"failed {result['failed']}, errored {result['errored']}"
    )
    if reason is not None:
        summary += f", stopped: {reason}"
    log_event(session_factory, "info", summary)
    if reason in STOP_LEVELS:
        log_event(session_factory, STOP_LEVELS[reason], f"Scheduled scoring stopped: {reason}")
        return "stopped"
    return "ran"


def tick(
    now: datetime,
    state: SchedulerState,
    session_factory=SessionLocal,
    groq_client_factory=default_groq_client,
    feed_client_factory=default_feed_client,
    sleep: Callable[[float], None] | None = None,
) -> dict:
    summary = {"enabled": False, "hunt": None, "scoring": None}
    try:
        with session_factory() as db:
            values = read_values(db)
    except Exception as exc:
        warn_once(
            state,
            session_factory,
            now,
            "error",
            f"Scheduler could not read settings: {type(exc).__name__}",
        )
        return summary
    if values["scheduler_enabled"] is not True:
        return summary
    summary["enabled"] = True
    try:
        summary["hunt"] = hunt_step(now, state, values, session_factory, feed_client_factory)
    except Exception as exc:
        summary["hunt"] = "error"
        warn_once(
            state, session_factory, now, "error", f"Scheduled hunt failed: {type(exc).__name__}"
        )
    try:
        summary["scoring"] = score_step(
            now, state, values, session_factory, groq_client_factory, sleep
        )
    except Exception as exc:
        summary["scoring"] = "error"
        warn_once(
            state, session_factory, now, "error", f"Scheduled scoring failed: {type(exc).__name__}"
        )
    return summary


class SchedulerThread:
    def __init__(self, interval: float = TICK_SECONDS):
        self.interval = interval
        self.state = SchedulerState()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name="scheduler", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self.stop_event.set()
        self.thread.join(timeout)

    def run(self) -> None:
        while not self.stop_event.wait(self.interval):
            try:
                tick(datetime.now(timezone.utc), self.state)
            except Exception:
                pass