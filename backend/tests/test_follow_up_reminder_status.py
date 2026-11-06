import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.main import app
from app.services.scheduler import SchedulerState, tick
from tests.email_helpers import make_application

NOW = datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc)

BASELINE = {
    "daily_score_cap": 150,
    "apply_threshold": 70,
    "maybe_threshold": 40,
    "title_exclude_regex": "senior|manager",
    "title_include_keywords": ["support", "admin"],
    "scheduler_enabled": False,
    "hunt_interval_hours": 6,
    "score_interval_minutes": 30,
    "score_batch_limit": 2,
    "followup_reminders_enabled": True,
}


def write_settings():
    with engine.begin() as connection:
        for key, value in BASELINE.items():
            connection.execute(
                text(
                    "insert into settings (key, value) values (:key, cast(:value as jsonb)) "
                    "on conflict (key) do update set value = excluded.value"
                ),
                {"key": key, "value": json.dumps(value)},
            )


def clear_events():
    with engine.begin() as connection:
        name = connection.execute(text("select current_database()")).scalar_one()
        assert name == "jobtracker_test"
        connection.execute(text("delete from system_events"))


@pytest.fixture(autouse=True)
def reminder_settings():
    write_settings()
    clear_events()
    yield
    write_settings()
    clear_events()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


class Recorder:
    def groq(self):
        raise AssertionError("Groq must not be called")

    def feeds(self):
        raise AssertionError("Feeds must not be called")


def noop_sleep(seconds):
    return None


def run_tick(state, now=NOW):
    recorder = Recorder()
    return tick(now, state, SessionLocal, recorder.groq, recorder.feeds, noop_sleep)


def add_overdue_follow_up(application_id):
    with engine.begin() as connection:
        return connection.execute(
            text(
                "insert into follow_ups (application_id, title, due_date, status) "
                "values (:application_id, 'Check in', '2026-10-01', 'pending') returning id"
            ),
            {"application_id": application_id},
        ).scalar_one()


def reminder_links():
    with engine.connect() as connection:
        rows = connection.execute(
            text("select link from notifications where type = 'follow_up_overdue' order by id")
        ).all()
    return [row.link for row in rows]


def follow_up_status(follow_up_id):
    with engine.connect() as connection:
        return connection.execute(
            text("select status from follow_ups where id = :id"), {"id": follow_up_id}
        ).scalar_one()


@pytest.mark.parametrize(
    "status", ["applied", "under_review", "assessment", "interview", "offer"]
)
def test_tick_still_reminds_for_active_application(status):
    follow_up_id = add_overdue_follow_up(make_application("Example Corp", status))
    summary = run_tick(SchedulerState())
    assert summary["reminders"] == 1
    assert reminder_links() == [f"/follow-ups/{follow_up_id}"]


@pytest.mark.parametrize("status", ["rejected", "withdrawn"])
def test_tick_creates_no_reminder_for_closed_application(status):
    follow_up_id = add_overdue_follow_up(make_application("Example Corp", status))
    summary = run_tick(SchedulerState())
    assert summary["reminders"] == 0
    assert reminder_links() == []
    assert follow_up_status(follow_up_id) == "pending"


@pytest.mark.parametrize("closed", ["rejected", "withdrawn"])
@pytest.mark.parametrize("active", ["applied", "interview"])
def test_reminder_resumes_when_application_returns_to_active(client, headers, closed, active):
    application_id = make_application("Example Corp", closed)
    follow_up_id = add_overdue_follow_up(application_id)
    state = SchedulerState()
    assert run_tick(state)["reminders"] == 0
    assert reminder_links() == []
    response = client.patch(
        f"/applications/{application_id}", json={"status": active}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == active
    assert run_tick(state, NOW + timedelta(hours=2))["reminders"] == 1
    assert reminder_links() == [f"/follow-ups/{follow_up_id}"]
    assert run_tick(state, NOW + timedelta(hours=4))["reminders"] == 0
    assert len(reminder_links()) == 1