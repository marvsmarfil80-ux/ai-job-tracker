import json
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.main import app
from app.services import scheduler
from app.services.clock import MANILA
from app.services.follow_up_reminders import (
    build_reminder_message,
    find_overdue_without_reminder,
)
from app.services.scheduler import SchedulerState, hunt_is_due, scoring_has_work, tick

BASE = "https://example.com/p8b-test"
NOW = datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 31)

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


def write_settings(**overrides):
    values = {**BASELINE, **overrides}
    with engine.begin() as connection:
        for key, value in values.items():
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


def noop_sleep(seconds):
    return None


class Recorder:
    def __init__(self):
        self.calls = []

    def groq(self):
        self.calls.append("groq")
        raise AssertionError("Groq must not be called")

    def feeds(self):
        self.calls.append("feeds")
        raise AssertionError("Feeds must not be called")


def run_tick(state, recorder, now=NOW):
    return tick(now, state, SessionLocal, recorder.groq, recorder.feeds, noop_sleep)


def count_rows(table):
    with engine.connect() as connection:
        return connection.execute(text(f"select count(*) from {table}")).scalar_one()


def reminders():
    with engine.connect() as connection:
        return connection.execute(
            text(
                "select id, type, message, link, is_read, created_at from notifications "
                "where type = 'follow_up_overdue' order by id"
            )
        ).all()


def events():
    with engine.connect() as connection:
        return connection.execute(
            text("select component, level, message from system_events order by id")
        ).all()


def make_application(client, headers, slug, title="Python Developer", company="Acme"):
    response = client.post(
        "/jobs",
        json={"source": "manual", "title": title, "company": company, "url": f"{BASE}/{slug}"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    response = client.post("/applications", json={"job_id": job_id}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"], job_id


def make_follow_up(client, headers, application_id, title, due_date=None):
    body = {"application_id": application_id, "title": title}
    if due_date is not None:
        body["due_date"] = due_date
    response = client.post("/follow-ups", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def backdate_notifications(created_at):
    with engine.begin() as connection:
        connection.execute(
            text("update notifications set created_at = :created_at"),
            {"created_at": created_at},
        )


def insert_notification_at(type_, link, created_at):
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into notifications (type, message, link, created_at) "
                "values (:type, 'x', :link, :created_at)"
            ),
            {"type": type_, "link": link, "created_at": created_at},
        )


def test_overdue_follow_up_creates_exactly_one_notification(client, headers):
    application_id, _ = make_application(client, headers, "one")
    follow_up_id = make_follow_up(client, headers, application_id, "Email recruiter", "2026-10-01")
    state = SchedulerState()
    summary = run_tick(state, Recorder())
    assert summary["reminders"] == 1
    rows = reminders()
    assert len(rows) == 1
    assert rows[0].type == "follow_up_overdue"
    assert rows[0].link == f"/follow-ups/{follow_up_id}"
    assert rows[0].is_read is False
    assert rows[0].message == (
        "Follow-up overdue: Email recruiter (Python Developer at Acme), due 2026-10-01"
    )


def test_second_check_does_not_repeat(client, headers):
    application_id, _ = make_application(client, headers, "repeat")
    make_follow_up(client, headers, application_id, "Ping", "2026-10-01")
    state = SchedulerState()
    recorder = Recorder()
    assert run_tick(state, recorder)["reminders"] == 1
    assert run_tick(state, recorder, NOW + timedelta(hours=2))["reminders"] == 0
    assert run_tick(state, recorder, NOW + timedelta(hours=4))["reminders"] == 0
    assert len(reminders()) == 1


def test_completed_follow_up_never_notifies(client, headers):
    application_id, _ = make_application(client, headers, "completed")
    follow_up_id = make_follow_up(client, headers, application_id, "Done", "2026-10-01")
    response = client.patch(
        f"/follow-ups/{follow_up_id}", json={"status": "completed"}, headers=headers
    )
    assert response.status_code == 200
    assert run_tick(SchedulerState(), Recorder())["reminders"] == 0
    assert reminders() == []


def test_follow_up_without_due_date_never_notifies(client, headers):
    application_id, _ = make_application(client, headers, "nodate")
    make_follow_up(client, headers, application_id, "No date")
    assert run_tick(SchedulerState(), Recorder())["reminders"] == 0
    assert reminders() == []


def test_due_today_and_future_do_not_notify_but_yesterday_does(client, headers):
    application_id, _ = make_application(client, headers, "dates")
    make_follow_up(client, headers, application_id, "Today", "2026-10-31")
    make_follow_up(client, headers, application_id, "Future", "2026-11-15")
    yesterday_id = make_follow_up(client, headers, application_id, "Yesterday", "2026-10-30")
    assert run_tick(SchedulerState(), Recorder())["reminders"] == 1
    rows = reminders()
    assert [row.link for row in rows] == [f"/follow-ups/{yesterday_id}"]


def test_moving_due_date_later_and_passing_again_notifies_again(client, headers):
    application_id, _ = make_application(client, headers, "moved")
    follow_up_id = make_follow_up(client, headers, application_id, "Moved", "2026-10-01")
    state = SchedulerState()
    recorder = Recorder()
    assert run_tick(state, recorder)["reminders"] == 1
    backdate_notifications(datetime(2026, 10, 5, 9, 0, tzinfo=MANILA))
    response = client.patch(
        f"/follow-ups/{follow_up_id}", json={"due_date": "2026-11-15"}, headers=headers
    )
    assert response.status_code == 200
    assert run_tick(state, recorder, NOW + timedelta(hours=2))["reminders"] == 0
    assert len(reminders()) == 1
    response = client.patch(
        f"/follow-ups/{follow_up_id}", json={"due_date": "2026-10-20"}, headers=headers
    )
    assert response.status_code == 200
    assert run_tick(state, recorder, NOW + timedelta(hours=4))["reminders"] == 1
    assert len(reminders()) == 2
    assert run_tick(state, recorder, NOW + timedelta(hours=6))["reminders"] == 0
    assert len(reminders()) == 2


def test_existing_notification_rule_boundary(client, headers):
    application_id, _ = make_application(client, headers, "boundary")
    follow_up_id = make_follow_up(client, headers, application_id, "Edge", "2026-10-01")
    link = f"/follow-ups/{follow_up_id}"
    with SessionLocal() as db:
        assert [row["id"] for row in find_overdue_without_reminder(db, TODAY)] == [follow_up_id]
    insert_notification_at("follow_up_overdue", link, datetime(2026, 10, 1, 23, 59, 59, tzinfo=MANILA))
    with SessionLocal() as db:
        assert [row["id"] for row in find_overdue_without_reminder(db, TODAY)] == [follow_up_id]
    backdate_notifications(datetime(2026, 10, 2, 0, 0, 0, tzinfo=MANILA))
    with SessionLocal() as db:
        assert find_overdue_without_reminder(db, TODAY) == []


def test_other_link_or_other_type_does_not_count_as_existing(client, headers):
    application_id, _ = make_application(client, headers, "othertype")
    follow_up_id = make_follow_up(client, headers, application_id, "Other", "2026-10-01")
    late = datetime(2026, 10, 20, 9, 0, tzinfo=MANILA)
    insert_notification_at("follow_up_overdue", f"/follow-ups/{follow_up_id + 100}", late)
    insert_notification_at("hunt_done", f"/follow-ups/{follow_up_id}", late)
    with SessionLocal() as db:
        assert [row["id"] for row in find_overdue_without_reminder(db, TODAY)] == [follow_up_id]


def test_message_is_english_and_parts_are_truncated_without_html(client, headers):
    application_id, job_id = make_application(client, headers, "longparts")
    with engine.begin() as connection:
        connection.execute(
            text("update jobs set title = :title, company = :company where id = :id"),
            {
                "title": "<b>" + "T" * 300 + "</b><script>alert(1)</script>",
                "company": "<i>" + "C" * 300 + "</i>",
                "id": job_id,
            },
        )
    make_follow_up(client, headers, application_id, "x" * 200, "2026-10-01")
    run_tick(SchedulerState(), Recorder())
    message = reminders()[0].message
    assert message.startswith("Follow-up overdue: ")
    assert message.endswith(", due 2026-10-01")
    assert "x" * 100 in message and "x" * 101 not in message
    assert "T" * 100 in message and "T" * 101 not in message
    assert "C" * 100 in message and "C" * 101 not in message
    assert "<" not in message and ">" not in message
    assert len(message) <= 400


def test_build_reminder_message_without_company_or_job():
    assert (
        build_reminder_message("Call", "Python Developer", None, date(2026, 10, 1))
        == "Follow-up overdue: Call (Python Developer), due 2026-10-01"
    )
    assert (
        build_reminder_message("Call", None, None, date(2026, 10, 1))
        == "Follow-up overdue: Call, due 2026-10-01"
    )


def test_reminders_disabled_setting_creates_nothing(client, headers):
    write_settings(followup_reminders_enabled=False)
    application_id, _ = make_application(client, headers, "disabled")
    make_follow_up(client, headers, application_id, "Off", "2026-10-01")
    summary = run_tick(SchedulerState(), Recorder())
    assert summary["reminders"] == "disabled"
    assert reminders() == []


def test_reminders_run_without_hunt_or_scoring_when_scheduler_is_off(client, headers):
    write_settings(scheduler_enabled=False, followup_reminders_enabled=True)
    application_id, _ = make_application(client, headers, "schedoff")
    make_follow_up(client, headers, application_id, "Reminder only", "2026-10-01")
    with SessionLocal() as db:
        assert scoring_has_work(db) is True
        assert hunt_is_due(db, NOW, 6) is True
    runs_before = count_rows("search_runs")
    scores_before = count_rows("job_scores")
    recorder = Recorder()
    summary = run_tick(SchedulerState(), recorder)
    assert summary["enabled"] is False
    assert summary["hunt"] is None
    assert summary["scoring"] is None
    assert summary["reminders"] == 1
    assert len(reminders()) == 1
    assert recorder.calls == []
    assert count_rows("search_runs") == runs_before
    assert count_rows("job_scores") == scores_before


def test_check_runs_at_most_once_per_hour(client, headers):
    application_id, _ = make_application(client, headers, "hourly")
    make_follow_up(client, headers, application_id, "First", "2026-10-01")
    state = SchedulerState()
    recorder = Recorder()
    assert run_tick(state, recorder)["reminders"] == 1
    make_follow_up(client, headers, application_id, "Second", "2026-10-02")
    assert run_tick(state, recorder, NOW + timedelta(minutes=30))["reminders"] == "not_due"
    assert len(reminders()) == 1
    assert run_tick(state, recorder, NOW + timedelta(minutes=59, seconds=59))["reminders"] == "not_due"
    assert run_tick(state, recorder, NOW + timedelta(minutes=61))["reminders"] == 1
    assert len(reminders()) == 2


def test_first_tick_after_startup_checks_immediately(client, headers):
    application_id, _ = make_application(client, headers, "startup")
    make_follow_up(client, headers, application_id, "Startup", "2026-10-01")
    state = SchedulerState()
    assert state.last_reminder_check is None
    assert run_tick(state, Recorder())["reminders"] == 1
    assert state.last_reminder_check == NOW


def test_one_failing_notification_does_not_stop_the_others(client, headers, monkeypatch):
    application_id, job_id = make_application(
        client, headers, "failing", "SecretJobTitle", "SecretCompany"
    )
    bad_id = make_follow_up(client, headers, application_id, "fail me please", "2026-09-01")
    good_id = make_follow_up(client, headers, application_id, "ok me please", "2026-09-02")
    real_create = scheduler.create_reminder

    def flaky(db, row):
        if row["id"] == bad_id:
            raise RuntimeError("boom " + row["title"])
        return real_create(db, row)

    monkeypatch.setattr(scheduler, "create_reminder", flaky)
    summary = run_tick(SchedulerState(), Recorder())
    assert summary["reminders"] == 1
    assert [row.link for row in reminders()] == [f"/follow-ups/{good_id}"]
    logged = events()
    assert len(logged) == 1
    assert logged[0].component == "scheduler"
    assert logged[0].level == "error"
    assert logged[0].message == "Follow-up reminder failed: RuntimeError"
    for entry in logged:
        assert "fail me" not in entry.message
        assert "SecretJobTitle" not in entry.message
        assert "SecretCompany" not in entry.message
        assert "boom" not in entry.message


def test_same_failure_warning_is_logged_at_most_once_per_hour(client, headers, monkeypatch):
    application_id, _ = make_application(client, headers, "warnonce")
    make_follow_up(client, headers, application_id, "fail", "2026-09-01")

    def always_fails(db, row):
        raise RuntimeError("boom")

    monkeypatch.setattr(scheduler, "create_reminder", always_fails)
    state = SchedulerState()
    recorder = Recorder()
    run_tick(state, recorder)
    assert len(events()) == 1
    state.last_reminder_check = None
    run_tick(state, recorder, NOW + timedelta(minutes=10))
    assert len(events()) == 1
    state.last_reminder_check = None
    run_tick(state, recorder, NOW + timedelta(minutes=61))
    assert len(events()) == 2


def test_no_real_network_is_used(client, headers):
    application_id, _ = make_application(client, headers, "network")
    make_follow_up(client, headers, application_id, "Net", "2026-10-01")
    recorder = Recorder()
    run_tick(SchedulerState(), recorder)
    assert recorder.calls == []