import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from app.config import get_settings
from app.db import engine, get_db
from app.main import app
from app.routers.system_status import get_health_client

LOCAL_URL = "http://127.0.0.1:5679/webhook/secret-path-abc"
REMOTE_URL = "http://n8n.test/webhook/secret-path-abc"
GROQ_KEY = "GROQ-SECRET-VALUE"
PROFILE_MARKER = "PROFILE SECRET TEXT"
BASE = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
TOP_KEYS = {"status", "checked_at", "database", "groq", "n8n", "email_sync", "profile", "scheduler"}
LEAK_MARKERS = [LOCAL_URL, "secret-path-abc", "127.0.0.1", "5679", GROQ_KEY, PROFILE_MARKER]


def upsert_setting(key, value):
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into settings (key, value) values (:key, cast(:value as jsonb)) "
                "on conflict (key) do update set value = excluded.value"
            ),
            {"key": key, "value": json.dumps(value)},
        )


def clear_tables():
    with engine.begin() as connection:
        connection.execute(text("delete from search_runs"))
        connection.execute(text("delete from system_events"))
        connection.execute(text("delete from profile"))


def set_profile(content):
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into profile (content) values (:content) "
                "on conflict (id) do update set content = excluded.content"
            ),
            {"content": content},
        )


def add_run(started_at, status, finished_at=None, source="email"):
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                "insert into search_runs (trigger, status, started_at, finished_at) "
                "values ('p10a-test', :status, :started, :finished) returning id"
            ),
            {"status": status, "started": started_at, "finished": finished_at},
        ).scalar_one()
        connection.execute(
            text(
                "insert into search_run_steps (run_id, source, status) "
                "values (:run_id, :source, :status)"
            ),
            {"run_id": run_id, "source": source, "status": status},
        )
    return run_id


def read_schema_version():
    with engine.connect() as connection:
        try:
            return connection.execute(
                text("select version_num from alembic_version limit 1")
            ).scalar_one_or_none()
        except Exception:
            return None


def parse(value):
    return datetime.fromisoformat(value) if value is not None else None


def set_n8n(monkeypatch, url):
    value = SecretStr(url) if url is not None else None
    monkeypatch.setattr(get_settings(), "n8n_webhook_url", value)


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    clear_tables()
    config = get_settings()
    monkeypatch.setattr(config, "n8n_webhook_url", None)
    monkeypatch.setattr(config, "groq_api_key", SecretStr(GROQ_KEY))
    monkeypatch.setattr(config, "groq_mock", False)
    upsert_setting("scheduler_enabled", False)
    upsert_setting("followup_reminders_enabled", True)
    yield
    app.dependency_overrides.pop(get_health_client, None)
    app.dependency_overrides.pop(get_db, None)
    clear_tables()
    upsert_setting("scheduler_enabled", False)
    upsert_setting("followup_reminders_enabled", True)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


@pytest.fixture
def fake_n8n():
    calls = []

    def install(respond):
        def handler(request):
            calls.append(request)
            return respond(request)

        def dependency():
            with httpx.Client(transport=httpx.MockTransport(handler)) as fake:
                yield fake

        app.dependency_overrides[get_health_client] = dependency
        return calls

    return install


def get_status(client, headers):
    return client.get("/system/status", headers=headers)


def ok_response(request):
    return httpx.Response(200)


def test_requires_api_key(client):
    assert client.get("/system/status").status_code == 401
    assert client.get("/system/status", headers={"X-API-Key": "wrong"}).status_code == 401


def test_response_shape_when_healthy(client, headers):
    response = get_status(client, headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == TOP_KEYS
    assert set(body["database"]) == {"status", "schema_version"}
    assert set(body["groq"]) == {"api_key_configured", "mock_mode"}
    assert set(body["n8n"]) == {"status", "http_status"}
    assert set(body["email_sync"]) == {
        "last_run_id",
        "last_run_status",
        "last_run_finished_at",
        "last_successful_run_at",
    }
    assert set(body["profile"]) == {"is_set"}
    assert set(body["scheduler"]) == {"enabled", "followup_reminders_enabled"}
    assert body["status"] == "ok"
    assert body["database"] == {"status": "ok", "schema_version": read_schema_version()}
    checked_at = parse(body["checked_at"])
    assert checked_at.tzinfo is not None
    assert abs(datetime.now(timezone.utc) - checked_at) < timedelta(seconds=60)


def test_ok_when_n8n_not_configured(client, headers):
    body = get_status(client, headers).json()
    assert body["n8n"] == {"status": "not_configured", "http_status": None}
    assert body["status"] == "ok"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://127.0.0.1:5679/webhook/secret-path-abc", "http://127.0.0.1:5679/healthz"),
        ("http://localhost:5679/webhook/secret-path-abc", "http://localhost:5679/healthz"),
        ("http://[::1]:5679/webhook/secret-path-abc", "http://[::1]:5679/healthz"),
    ],
)
def test_ok_when_local_n8n_is_healthy(client, headers, monkeypatch, fake_n8n, url, expected):
    set_n8n(monkeypatch, url)
    calls = fake_n8n(ok_response)
    body = get_status(client, headers).json()
    assert body["n8n"] == {"status": "ok", "http_status": 200}
    assert body["status"] == "ok"
    assert len(calls) == 1
    assert calls[0].method == "GET"
    assert str(calls[0].url) == expected


def test_degraded_when_n8n_returns_error_status(client, headers, monkeypatch, fake_n8n):
    set_n8n(monkeypatch, LOCAL_URL)
    fake_n8n(lambda request: httpx.Response(500))
    body = get_status(client, headers).json()
    assert body["n8n"] == {"status": "error", "http_status": 500}
    assert body["status"] == "degraded"
    assert body["database"]["status"] == "ok"


@pytest.mark.parametrize(
    "url",
    [
        REMOTE_URL,
        "http://192.168.1.10:5679/webhook/secret-path-abc",
        "http://127.0.0.1.evil.test/webhook/secret-path-abc",
        "http://0.0.0.0:5679/webhook/secret-path-abc",
        "ftp://127.0.0.1:5679/webhook/secret-path-abc",
    ],
)
def test_non_local_host_is_error_without_any_call(client, headers, monkeypatch, fake_n8n, url):
    set_n8n(monkeypatch, url)
    calls = fake_n8n(ok_response)
    body = get_status(client, headers).json()
    assert body["n8n"] == {"status": "error", "http_status": None}
    assert body["status"] == "degraded"
    assert calls == []


def test_redirect_is_not_followed(client, headers, monkeypatch, fake_n8n):
    set_n8n(monkeypatch, LOCAL_URL)
    calls = fake_n8n(
        lambda request: httpx.Response(302, headers={"Location": "http://127.0.0.1:5679/other"})
    )
    body = get_status(client, headers).json()
    assert body["n8n"] == {"status": "error", "http_status": 302}
    assert body["status"] == "degraded"
    assert len(calls) == 1


def test_timeout_is_error(client, headers, monkeypatch, fake_n8n):
    set_n8n(monkeypatch, LOCAL_URL)

    def respond(request):
        raise httpx.ConnectTimeout("timeout", request=request)

    fake_n8n(respond)
    body = get_status(client, headers).json()
    assert body["n8n"] == {"status": "error", "http_status": None}
    assert body["status"] == "degraded"


def test_exception_text_is_not_exposed(client, headers, monkeypatch, fake_n8n, caplog):
    set_n8n(monkeypatch, LOCAL_URL)

    def respond(request):
        raise httpx.ConnectError("boom secret-path-abc", request=request)

    fake_n8n(respond)
    with caplog.at_level(logging.DEBUG):
        response = get_status(client, headers)
    assert "boom" not in response.text
    assert "secret-path-abc" not in response.text
    assert "boom" not in caplog.text
    assert "secret-path-abc" not in caplog.text


def test_response_and_logs_contain_no_secrets(client, headers, monkeypatch, fake_n8n, caplog):
    set_n8n(monkeypatch, LOCAL_URL)
    set_profile(PROFILE_MARKER)
    fake_n8n(ok_response)
    with caplog.at_level(logging.DEBUG):
        response = get_status(client, headers)
    assert response.status_code == 200
    for marker in LEAK_MARKERS:
        assert marker not in response.text
        assert marker not in caplog.text
    assert "webhook" not in response.text.lower()


@pytest.mark.parametrize(
    "value,expected",
    [(SecretStr(GROQ_KEY), True), (SecretStr(""), False), (SecretStr("   "), False), (None, False)],
)
def test_groq_api_key_configured(client, headers, monkeypatch, value, expected):
    monkeypatch.setattr(get_settings(), "groq_api_key", value)
    response = get_status(client, headers)
    assert response.json()["groq"]["api_key_configured"] is expected
    assert GROQ_KEY not in response.text


@pytest.mark.parametrize("mock", [True, False])
def test_groq_mock_mode(client, headers, monkeypatch, mock):
    monkeypatch.setattr(get_settings(), "groq_mock", mock)
    assert get_status(client, headers).json()["groq"]["mock_mode"] is mock


def test_profile_is_set_flag(client, headers):
    assert get_status(client, headers).json()["profile"] == {"is_set": False}
    set_profile("  \n ")
    assert get_status(client, headers).json()["profile"] == {"is_set": False}
    set_profile(PROFILE_MARKER)
    response = get_status(client, headers)
    assert response.json()["profile"] == {"is_set": True}
    assert PROFILE_MARKER not in response.text


def test_scheduler_flags_follow_settings(client, headers):
    upsert_setting("scheduler_enabled", True)
    upsert_setting("followup_reminders_enabled", False)
    body = get_status(client, headers).json()
    assert body["scheduler"] == {"enabled": True, "followup_reminders_enabled": False}


def test_scheduler_flags_use_defaults_when_keys_are_missing(client, headers):
    with engine.begin() as connection:
        connection.execute(
            text(
                "delete from settings where key in "
                "('scheduler_enabled', 'followup_reminders_enabled')"
            )
        )
    body = get_status(client, headers).json()
    assert body["scheduler"] == {"enabled": False, "followup_reminders_enabled": True}


def test_email_sync_without_any_run(client, headers):
    assert get_status(client, headers).json()["email_sync"] == {
        "last_run_id": None,
        "last_run_status": None,
        "last_run_finished_at": None,
        "last_successful_run_at": None,
    }


def test_email_sync_with_running_run(client, headers):
    run_id = add_run(BASE, "running")
    sync = get_status(client, headers).json()["email_sync"]
    assert sync["last_run_id"] == run_id
    assert sync["last_run_status"] == "running"
    assert sync["last_run_finished_at"] is None
    assert sync["last_successful_run_at"] is None


def test_email_sync_with_error_run(client, headers):
    finished = BASE + timedelta(minutes=1)
    run_id = add_run(BASE, "error", finished)
    sync = get_status(client, headers).json()["email_sync"]
    assert sync["last_run_id"] == run_id
    assert sync["last_run_status"] == "error"
    assert parse(sync["last_run_finished_at"]) == finished
    assert sync["last_successful_run_at"] is None


def test_email_sync_with_done_run(client, headers):
    finished = BASE + timedelta(minutes=2)
    run_id = add_run(BASE, "done", finished)
    sync = get_status(client, headers).json()["email_sync"]
    assert sync["last_run_id"] == run_id
    assert sync["last_run_status"] == "done"
    assert parse(sync["last_run_finished_at"]) == finished
    assert parse(sync["last_successful_run_at"]) == finished


def test_email_sync_last_run_is_newest_and_success_is_latest_done(client, headers):
    old_done_finished = BASE - timedelta(hours=3)
    newer_done_finished = BASE - timedelta(hours=2)
    add_run(BASE - timedelta(hours=4), "done", old_done_finished)
    add_run(BASE - timedelta(hours=3), "done", newer_done_finished)
    error_id = add_run(BASE, "error", BASE + timedelta(minutes=1))
    sync = get_status(client, headers).json()["email_sync"]
    assert sync["last_run_id"] == error_id
    assert sync["last_run_status"] == "error"
    assert parse(sync["last_successful_run_at"]) == newer_done_finished


def test_email_sync_running_run_after_a_done_run(client, headers):
    finished = BASE - timedelta(hours=1)
    add_run(BASE - timedelta(hours=2), "done", finished)
    running_id = add_run(BASE, "running")
    sync = get_status(client, headers).json()["email_sync"]
    assert sync["last_run_id"] == running_id
    assert sync["last_run_status"] == "running"
    assert parse(sync["last_successful_run_at"]) == finished


def test_email_sync_ignores_runs_without_an_email_step(client, headers):
    email_finished = BASE - timedelta(hours=5)
    email_id = add_run(BASE - timedelta(hours=6), "done", email_finished)
    add_run(BASE, "done", BASE + timedelta(minutes=1), source="remoteok")
    sync = get_status(client, headers).json()["email_sync"]
    assert sync["last_run_id"] == email_id
    assert parse(sync["last_successful_run_at"]) == email_finished


def test_email_sync_is_empty_when_only_hunt_runs_exist(client, headers):
    add_run(BASE, "done", BASE + timedelta(minutes=1), source="weworkremotely")
    sync = get_status(client, headers).json()["email_sync"]
    assert sync["last_run_id"] is None
    assert sync["last_successful_run_at"] is None


class BrokenSession:
    def execute(self, *args, **kwargs):
        raise RuntimeError("database down")

    def rollback(self):
        pass


class FakeResult:
    def scalar_one(self):
        return 1

    def scalar_one_or_none(self):
        return "fake_revision"


class FlakySession:
    def execute(self, statement, params=None):
        sql = str(statement)
        if "search_runs" in sql or "from profile" in sql or "from settings" in sql:
            raise RuntimeError("sub-check failed")
        return FakeResult()

    def rollback(self):
        pass


def test_unreachable_database_returns_503(client, headers):
    def broken():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken
    response = get_status(client, headers)
    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unreachable."}


def test_failing_sub_checks_do_not_break_the_endpoint(client, headers):
    def flaky():
        yield FlakySession()

    app.dependency_overrides[get_db] = flaky
    response = get_status(client, headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == {"status": "ok", "schema_version": "fake_revision"}
    assert body["email_sync"] == {
        "last_run_id": None,
        "last_run_status": None,
        "last_run_finished_at": None,
        "last_successful_run_at": None,
    }
    assert body["profile"] == {"is_set": False}
    assert body["scheduler"] == {"enabled": False, "followup_reminders_enabled": True}