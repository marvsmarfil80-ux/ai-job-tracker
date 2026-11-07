import contextlib
import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.main import app
from app.services import email_sync, scheduler
from app.services.orphan_runs import close_orphan_runs

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
WEBHOOK_URL = "http://n8n.test/webhook/secret-path"
WEBHOOK_KEY = "test-webhook-key"
SECRET_TEXT = "SECRET EMAIL SUBJECT"
TYPE = "email_sync_failed"
UNREACHABLE = "Email check failed: Could not reach the n8n webhook."
TIMEOUT = "Email check failed: n8n did not respond within the timeout."
IMPORTER_ERROR = "Email check failed: The n8n email importer reported an error."
UNEXPECTED = "Email check failed: The email sync failed unexpectedly."
SETTINGS = {
    "email_sync_lookback_days": 7,
    "email_sync_timeout_seconds": 300,
    "email_sync_interval_minutes": 120,
    "scheduler_enabled": False,
}
STEP_VALUES = {"email_sync_timeout_seconds": 300, "email_sync_interval_minutes": 120}


def set_setting(key, value):
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into settings (key, value) values (:key, cast(:value as jsonb)) "
                "on conflict (key) do update set value = excluded.value"
            ),
            {"key": key, "value": json.dumps(value)},
        )


def reset():
    with engine.begin() as connection:
        connection.execute(text("delete from search_runs"))
        connection.execute(text("delete from system_events"))
        connection.execute(text("delete from notifications"))
    for key, value in SETTINGS.items():
        set_setting(key, value)


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    reset()
    config = get_settings()
    monkeypatch.setattr(config, "n8n_webhook_url", SecretStr(WEBHOOK_URL))
    monkeypatch.setattr(config, "n8n_webhook_key", SecretStr(WEBHOOK_KEY))
    yield
    reset()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


@pytest.fixture
def unreachable(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError(WEBHOOK_URL)

    monkeypatch.setattr(email_sync, "call_n8n", boom)


def add_run(started_at, run_status="running", step_status="running", step_new=0):
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                "insert into search_runs (trigger, status, started_at) "
                "values ('manual', :status, :started) returning id"
            ),
            {"status": run_status, "started": started_at},
        ).scalar_one()
        connection.execute(
            text(
                'insert into search_run_steps (run_id, source, status, "new") '
                "values (:run_id, 'email', :status, :new)"
            ),
            {"run_id": run_id, "status": step_status, "new": step_new},
        )
    return run_id


def run_status(run_id):
    with engine.connect() as connection:
        return connection.execute(
            text("select status from search_runs where id = :id"), {"id": run_id}
        ).scalar_one()


def latest_run_id():
    with engine.connect() as connection:
        return connection.execute(text("select max(id) from search_runs")).scalar_one()


def count_runs():
    with engine.connect() as connection:
        return connection.execute(text("select count(*) from search_runs")).scalar_one()


def failed_notifications():
    with engine.connect() as connection:
        return connection.execute(
            text("select type, message, link from notifications where type = :type order by id"),
            {"type": TYPE},
        ).all()


def count_notifications():
    with engine.connect() as connection:
        return connection.execute(text("select count(*) from notifications")).scalar_one()


def mark_all_read():
    with engine.begin() as connection:
        connection.execute(text("update notifications set is_read = true"))


def run_finish(run_id):
    email_sync.finish_sync(
        run_id, SessionLocal, lambda: contextlib.nullcontext(), lambda seconds: None, 0
    )


def stub_processing(monkeypatch, result=None, error=None):
    def runner(db, client, limit, sleep=None):
        if error is not None:
            raise error
        return result

    monkeypatch.setattr(email_sync, "run_email_processing", runner)


def test_unreachable_webhook_creates_a_notification(client, headers, unreachable):
    response = client.post("/emails/sync", headers=headers)
    assert response.status_code == 502
    assert failed_notifications() == [(TYPE, UNREACHABLE, None)]
    assert run_status(latest_run_id()) == "error"


def test_unread_notification_blocks_a_new_one_until_it_is_read(client, headers, unreachable):
    assert client.post("/emails/sync", headers=headers).status_code == 502
    assert client.post("/emails/sync", headers=headers).status_code == 502
    assert count_runs() == 2
    assert len(failed_notifications()) == 1
    mark_all_read()
    assert client.post("/emails/sync", headers=headers).status_code == 502
    assert len(failed_notifications()) == 2


def test_finish_sync_timeout_creates_a_notification(monkeypatch):
    set_setting("email_sync_timeout_seconds", 0)
    stub_processing(monkeypatch, {"jobs_created": 0, "stopped_reason": None})
    run_id = add_run(NOW)
    run_finish(run_id)
    assert run_status(run_id) == "error"
    assert failed_notifications() == [(TYPE, TIMEOUT, None)]


def test_importer_error_step_creates_a_notification(monkeypatch):
    stub_processing(monkeypatch, {"jobs_created": 0, "stopped_reason": None})
    run_id = add_run(NOW, step_status="error")
    run_finish(run_id)
    assert run_status(run_id) == "error"
    assert failed_notifications() == [(TYPE, IMPORTER_ERROR, None)]


def test_unexpected_failure_creates_a_notification_without_leaking(monkeypatch):
    stub_processing(monkeypatch, error=RuntimeError(SECRET_TEXT))
    run_id = add_run(NOW, step_status="done", step_new=1)
    run_finish(run_id)
    assert run_status(run_id) == "error"
    assert failed_notifications() == [(TYPE, UNEXPECTED, None)]
    with engine.connect() as connection:
        messages = [row[0] for row in connection.execute(text("select message from notifications"))]
    assert all(SECRET_TEXT not in message for message in messages)


def test_stale_check_creates_a_notification():
    old = add_run(datetime(2026, 11, 2, 11, 0, tzinfo=timezone.utc))
    with SessionLocal() as db:
        assert email_sync.stale_check(db, 300, NOW) == 1
    assert run_status(old) == "error"
    assert failed_notifications() == [(TYPE, TIMEOUT, None)]


def test_successful_sync_creates_no_failure_notification(monkeypatch):
    stub_processing(monkeypatch, {"jobs_created": 1, "stopped_reason": None})
    run_id = add_run(NOW, step_status="done", step_new=1)
    run_finish(run_id)
    assert run_status(run_id) == "done"
    assert failed_notifications() == []


def test_running_sync_returns_409_and_creates_no_notification(client, headers, unreachable):
    add_run(datetime.now(timezone.utc))
    response = client.post("/emails/sync", headers=headers)
    assert response.status_code == 409
    assert count_notifications() == 0


def test_missing_webhook_config_returns_503_and_creates_no_notification(client, headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "n8n_webhook_url", None)
    response = client.post("/emails/sync", headers=headers)
    assert response.status_code == 503
    assert count_runs() == 0
    assert count_notifications() == 0


def test_closing_orphan_runs_creates_no_notification():
    run_id = add_run(NOW)
    assert close_orphan_runs() == 1
    assert run_status(run_id) == "error"
    assert count_notifications() == 0


def test_a_failing_notification_does_not_break_closing_the_run(client, headers, unreachable, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("notification failed")

    monkeypatch.setattr(email_sync, "insert_notification", boom)
    response = client.post("/emails/sync", headers=headers)
    assert response.status_code == 502
    assert response.json()["detail"] == "Could not reach the n8n webhook."
    assert run_status(latest_run_id()) == "error"
    assert count_notifications() == 0


def test_the_reason_is_cleaned_and_cut_to_100_characters():
    with SessionLocal() as db:
        assert email_sync.notify_sync_failed(db, "<b>bad</b> " + "x" * 200) is True
    assert failed_notifications() == [(TYPE, "Email check failed: bad " + "x" * 96, None)]


def test_scheduler_failure_creates_a_notification(unreachable):
    started = []
    result = scheduler.email_sync_step(
        NOW, scheduler.SchedulerState(), STEP_VALUES, SessionLocal, started.append
    )
    assert result == "failed"
    assert started == []
    assert failed_notifications() == [(TYPE, UNREACHABLE, None)]