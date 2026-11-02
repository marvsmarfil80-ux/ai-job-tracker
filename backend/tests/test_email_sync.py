import contextlib
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.main import app
from app.routers import emails as emails_router
from app.services import email_sync, scheduler

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
WEBHOOK_URL = "http://n8n.test/webhook/secret-path"
WEBHOOK_KEY = "test-webhook-key"
SECRET_TEXT = "SECRET EMAIL SUBJECT"
TIMEOUT_MESSAGE = "n8n did not respond within the timeout."
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
def n8n(monkeypatch):
    calls = []

    def fake(client, url, key, run_id, since):
        calls.append({"url": url, "key": key, "run_id": run_id, "since": since})

    monkeypatch.setattr(email_sync, "call_n8n", fake)
    return calls


@pytest.fixture
def finished(monkeypatch):
    run_ids = []
    monkeypatch.setattr(emails_router, "finish_sync", run_ids.append)
    return run_ids


def add_run(started_at, run_status="running", step_status="running", step_new=0, trigger="manual"):
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                "insert into search_runs (trigger, status, started_at) "
                "values (:trigger, :status, :started) returning id"
            ),
            {"trigger": trigger, "status": run_status, "started": started_at},
        ).scalar_one()
        connection.execute(
            text(
                'insert into search_run_steps (run_id, source, status, "new") '
                "values (:run_id, 'email', :status, :new)"
            ),
            {"run_id": run_id, "status": step_status, "new": step_new},
        )
    return run_id


def add_hunt_run(started_at):
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into search_runs (trigger, status, started_at) "
                "values ('manual', 'done', :started)"
            ),
            {"started": started_at},
        )


def run_of(run_id):
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "select trigger, status, finished_at is not null as finished, total_new "
                "from search_runs where id = :id"
            ),
            {"id": run_id},
        ).mappings().one()
    return dict(row)


def step_of(run_id):
    with engine.connect() as connection:
        row = connection.execute(
            text(
                'select status, message, "new" from search_run_steps '
                "where run_id = :id and source = 'email'"
            ),
            {"id": run_id},
        ).mappings().one()
    return dict(row)


def count_runs():
    with engine.connect() as connection:
        return connection.execute(text("select count(*) from search_runs")).scalar_one()


def latest_run_id():
    with engine.connect() as connection:
        return connection.execute(text("select max(id) from search_runs")).scalar_one()


def events(component="email_sync"):
    with engine.connect() as connection:
        return connection.execute(
            text(
                "select level, message, run_id from system_events "
                "where component = :component order by id"
            ),
            {"component": component},
        ).all()


def all_messages():
    with engine.connect() as connection:
        return [row[0] for row in connection.execute(text("select message from system_events"))]


def notifications():
    with engine.connect() as connection:
        return connection.execute(
            text("select type, message, link from notifications order by id")
        ).all()


def run_finish(run_id):
    email_sync.finish_sync(
        run_id, SessionLocal, lambda: contextlib.nullcontext(), lambda seconds: None, 0
    )


def stub_processing(monkeypatch, result=None, error=None):
    calls = []

    def runner(db, client, limit, sleep=None):
        calls.append(limit)
        if error is not None:
            raise error
        return result

    monkeypatch.setattr(email_sync, "run_email_processing", runner)
    return calls


@pytest.mark.parametrize("key_headers", [{}, {"X-API-Key": "wrong-key"}])
def test_sync_rejects_missing_or_wrong_key(client, key_headers):
    assert client.post("/emails/sync", headers=key_headers).status_code == 401
    assert count_runs() == 0


def test_sync_is_accepted_and_calls_n8n(client, headers, n8n, finished):
    response = client.post("/emails/sync", headers=headers)
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    assert run_of(run_id) == {"trigger": "manual", "status": "running", "finished": False, "total_new": 0}
    assert step_of(run_id)["status"] == "running"
    assert len(n8n) == 1
    assert n8n[0]["run_id"] == run_id
    assert n8n[0]["key"] == WEBHOOK_KEY
    assert n8n[0]["url"] == WEBHOOK_URL
    assert finished == [run_id]


def test_first_sync_looks_back_by_the_setting(client, headers, n8n, finished):
    client.post("/emails/sync", headers=headers)
    parsed = datetime.strptime(n8n[0]["since"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    expected = datetime.now(timezone.utc) - timedelta(days=7)
    assert abs(parsed - expected) < timedelta(minutes=1)


def test_running_sync_returns_409(client, headers, n8n, finished):
    add_run(datetime.now(timezone.utc))
    response = client.post("/emails/sync", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "An email sync is already running."
    assert n8n == []
    assert finished == []
    assert count_runs() == 1


def test_stale_running_sync_does_not_block_a_new_one(client, headers, n8n, finished):
    old = add_run(datetime.now(timezone.utc) - timedelta(seconds=900))
    response = client.post("/emails/sync", headers=headers)
    assert response.status_code == 202
    assert run_of(old)["status"] == "error"
    assert len(n8n) == 1


def test_unreachable_n8n_returns_502_and_closes_the_run(client, headers, monkeypatch, finished):
    def boom(*args, **kwargs):
        raise httpx.ConnectError(WEBHOOK_URL)

    monkeypatch.setattr(email_sync, "call_n8n", boom)
    response = client.post("/emails/sync", headers=headers)
    assert response.status_code == 502
    assert response.json()["detail"] == "Could not reach the n8n webhook."
    run_id = latest_run_id()
    assert run_of(run_id)["status"] == "error"
    assert run_of(run_id)["finished"] is True
    assert step_of(run_id)["status"] == "error"
    assert step_of(run_id)["message"] == "Could not reach the n8n webhook."
    assert events() == [("error", "Could not reach the n8n webhook: ConnectError", run_id)]
    assert all("n8n.test" not in message and "secret-path" not in message for message in all_messages())
    assert finished == []


def test_missing_webhook_config_returns_503(client, headers, monkeypatch, n8n, finished):
    monkeypatch.setattr(get_settings(), "n8n_webhook_url", None)
    response = client.post("/emails/sync", headers=headers)
    assert response.status_code == 503
    assert response.json()["detail"] == "The n8n webhook is not configured."
    assert count_runs() == 0
    assert n8n == []


def test_n8n_receives_key_header_and_json_body():
    seen = {}

    def handler(request):
        seen["key"] = request.headers["x-webhook-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"accepted": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with SessionLocal() as db:
        run_id = email_sync.start_sync(db, "manual", client)
    assert seen["key"] == WEBHOOK_KEY
    assert seen["body"]["run_id"] == run_id
    assert seen["body"]["since"].endswith("Z")


def test_n8n_error_status_returns_502():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as info:
            email_sync.start_sync(db, "manual", client)
    assert info.value.status_code == 502
    assert run_of(latest_run_id())["status"] == "error"


def test_since_without_a_previous_run_uses_the_lookback():
    with SessionLocal() as db:
        assert email_sync.compute_since(db, 7, NOW) == "2026-10-26T12:00:00Z"


def test_since_uses_the_last_done_run_minus_one_hour():
    add_run(NOW - timedelta(hours=5), "done", "done")
    add_run(NOW - timedelta(hours=1), "error", "error")
    with SessionLocal() as db:
        assert email_sync.compute_since(db, 7, NOW) == "2026-11-02T06:00:00Z"


def test_stale_check_marks_only_old_running_syncs():
    old = add_run(NOW - timedelta(seconds=600))
    recent = add_run(NOW - timedelta(seconds=60))
    with SessionLocal() as db:
        assert email_sync.stale_check(db, 300, NOW) == 1
    assert run_of(old)["status"] == "error"
    assert run_of(old)["finished"] is True
    assert step_of(old)["message"] == TIMEOUT_MESSAGE
    assert run_of(recent)["status"] == "running"
    assert events() == [("error", "A stale email sync was marked as failed.", old)]


def test_done_step_runs_processing_once_and_counts_jobs_only(monkeypatch):
    calls = stub_processing(monkeypatch, {"jobs_created": 2, "stopped_reason": None})
    run_id = add_run(NOW, step_status="done", step_new=3)
    run_finish(run_id)
    assert calls == [100]
    assert run_of(run_id) == {"trigger": "manual", "status": "done", "finished": True, "total_new": 2}
    assert notifications() == [
        ("hunt_done", "Email check finished: 3 new emails, 2 new jobs.", None)
    ]


def test_single_counts_use_singular_words(monkeypatch):
    stub_processing(monkeypatch, {"jobs_created": 1, "stopped_reason": None})
    run_finish(add_run(NOW, step_status="done", step_new=1))
    assert notifications() == [("hunt_done", "Email check finished: 1 new email, 1 new job.", None)]


def test_nothing_new_creates_no_notification(monkeypatch):
    stub_processing(monkeypatch, {"jobs_created": 0, "stopped_reason": None})
    run_id = add_run(NOW, step_status="done", step_new=0)
    run_finish(run_id)
    assert run_of(run_id)["status"] == "done"
    assert notifications() == []


def test_processing_that_stops_early_logs_only_the_reason(monkeypatch):
    stub_processing(monkeypatch, {"jobs_created": 0, "stopped_reason": "rate_limited"})
    run_id = add_run(NOW, step_status="done", step_new=0)
    run_finish(run_id)
    assert run_of(run_id)["status"] == "done"
    assert events() == [("warning", "Email processing stopped early: rate_limited", run_id)]


def test_n8n_error_step_closes_the_run_without_processing(monkeypatch):
    calls = stub_processing(monkeypatch, {"jobs_created": 0, "stopped_reason": None})
    run_id = add_run(NOW, step_status="error")
    run_finish(run_id)
    assert calls == []
    assert run_of(run_id)["status"] == "error"
    assert run_of(run_id)["finished"] is True
    assert events() == [("error", "The n8n email importer reported an error.", run_id)]


def test_timeout_marks_step_and_run_as_error(monkeypatch):
    set_setting("email_sync_timeout_seconds", 0)
    calls = stub_processing(monkeypatch, {"jobs_created": 0, "stopped_reason": None})
    run_id = add_run(NOW, step_status="running")
    run_finish(run_id)
    assert calls == []
    assert step_of(run_id)["status"] == "error"
    assert step_of(run_id)["message"] == TIMEOUT_MESSAGE
    assert run_of(run_id)["status"] == "error"
    assert run_of(run_id)["finished"] is True
    assert events() == [("error", TIMEOUT_MESSAGE, run_id)]


def test_busy_processing_is_skipped_quietly(monkeypatch):
    stub_processing(monkeypatch, error=HTTPException(status_code=409, detail="busy"))
    run_id = add_run(NOW, step_status="done", step_new=2)
    run_finish(run_id)
    assert run_of(run_id) == {"trigger": "manual", "status": "done", "finished": True, "total_new": 0}
    assert events() == [("info", "Email processing skipped: another job is running.", run_id)]
    assert notifications() == []


def test_unexpected_failure_closes_the_run_and_leaks_nothing(monkeypatch):
    stub_processing(monkeypatch, error=RuntimeError(SECRET_TEXT))
    run_id = add_run(NOW, step_status="done", step_new=1)
    run_finish(run_id)
    assert run_of(run_id)["status"] == "error"
    assert run_of(run_id)["finished"] is True
    assert events() == [("error", "Email sync failed unexpectedly: RuntimeError", run_id)]
    assert all(SECRET_TEXT not in message for message in all_messages())


def test_email_step_is_not_due_after_a_recent_email_run(n8n):
    add_run(NOW - timedelta(minutes=30), "done", "done")
    started = []
    result = scheduler.email_sync_step(
        NOW, scheduler.SchedulerState(), STEP_VALUES, SessionLocal, started.append
    )
    assert result == "not_due"
    assert started == []
    assert n8n == []


def test_due_email_step_starts_a_scheduled_sync(n8n):
    add_run(NOW - timedelta(hours=3), "done", "done")
    started = []
    result = scheduler.email_sync_step(
        NOW, scheduler.SchedulerState(), STEP_VALUES, SessionLocal, started.append
    )
    run_id = latest_run_id()
    assert result == "started"
    assert started == [run_id]
    assert run_of(run_id)["trigger"] == "scheduled"
    assert len(n8n) == 1


def test_email_step_reports_unreachable_n8n_as_failed(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("x")

    monkeypatch.setattr(email_sync, "call_n8n", boom)
    started = []
    result = scheduler.email_sync_step(
        NOW, scheduler.SchedulerState(), STEP_VALUES, SessionLocal, started.append
    )
    assert result == "failed"
    assert started == []


def test_missing_webhook_config_warns_once_per_hour(monkeypatch):
    monkeypatch.setattr(get_settings(), "n8n_webhook_url", None)
    state = scheduler.SchedulerState()
    for minutes in (0, 1):
        result = scheduler.email_sync_step(
            NOW + timedelta(minutes=minutes), state, STEP_VALUES, SessionLocal, lambda run_id: None
        )
        assert result == "skipped"
    message = "Scheduled email sync skipped: The n8n webhook is not configured."
    assert events("scheduler") == [("warning", message, None)]
    scheduler.email_sync_step(
        NOW + timedelta(minutes=61), state, STEP_VALUES, SessionLocal, lambda run_id: None
    )
    assert len(events("scheduler")) == 2
    assert count_runs() == 0


def test_hunt_is_due_ignores_email_runs():
    add_run(NOW - timedelta(hours=1), "done", "done")
    with SessionLocal() as db:
        assert scheduler.hunt_is_due(db, NOW, 6) is True
    add_hunt_run(NOW - timedelta(hours=1))
    with SessionLocal() as db:
        assert scheduler.hunt_is_due(db, NOW, 6) is False


def test_hunt_is_due_when_only_an_old_hunt_exists_beside_a_new_email_run():
    add_hunt_run(NOW - timedelta(hours=7))
    add_run(NOW - timedelta(minutes=10), "done", "done")
    with SessionLocal() as db:
        assert scheduler.hunt_is_due(db, NOW, 6) is True


def test_disabled_scheduler_never_runs_the_email_step(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "email_sync_step", lambda *args, **kwargs: calls.append(1))
    summary = scheduler.tick(NOW, scheduler.SchedulerState(), SessionLocal)
    assert summary["enabled"] is False
    assert "email_sync" not in summary
    assert calls == []


def test_enabled_scheduler_runs_the_email_step(monkeypatch):
    set_setting("scheduler_enabled", True)
    calls = []
    monkeypatch.setattr(scheduler, "hunt_step", lambda *args, **kwargs: "stub")
    monkeypatch.setattr(scheduler, "score_step", lambda *args, **kwargs: "stub")
    monkeypatch.setattr(
        scheduler, "email_sync_step", lambda *args, **kwargs: calls.append(1) or "started"
    )
    summary = scheduler.tick(NOW, scheduler.SchedulerState(), SessionLocal)
    assert summary["email_sync"] == "started"
    assert calls == [1]