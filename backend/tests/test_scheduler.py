import contextlib
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.services import scheduler
from app.services.groq_client import mock_handler
from app.services.scheduler import SchedulerState, SchedulerThread, tick

TEST_DATABASE = "jobtracker_test"
NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
HUNT_LOCK_KEY = 5150002
SCORE_LOCK_KEY = 5150001
PROFILE_MARKER = "PROFILE SECRET TEXT"

BASELINE = {
    "daily_score_cap": 150,
    "apply_threshold": 70,
    "maybe_threshold": 40,
    "title_exclude_regex": "senior|manager",
    "title_include_keywords": ["support", "admin"],
    "scheduler_enabled": True,
    "hunt_interval_hours": 6,
    "score_interval_minutes": 30,
    "score_batch_limit": 2,
}

HOSTS = {
    "weworkremotely.com": "weworkremotely",
    "remoteok.com": "remoteok",
    "remotive.com": "remotive",
}
FEED_BODIES = {
    "weworkremotely": (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        "<item><title>Acme: Support Agent</title><region>Anywhere</region>"
        "<description>Help users</description>"
        "<pubDate>Tue, 27 Oct 2026 07:30:50 +0000</pubDate>"
        "<link>https://weworkremotely.com/remote-jobs/p6b-sched-1</link></item>"
        "</channel></rss>"
    ).encode(),
    "remoteok": json.dumps(
        [
            {"last_updated": "1793001612", "legal": "Fake legal notice"},
            {
                "position": "Data Entry Clerk",
                "company": "Gamma",
                "url": "https://remoteok.com/remote-jobs/p6b-sched-2",
                "date": "2026-10-26T08:00:12+00:00",
                "description": "<p>Enter data</p>",
                "location": "",
            },
        ]
    ).encode(),
    "remotive": json.dumps({"jobs": []}).encode(),
}


def feed_handler(request):
    return httpx.Response(200, content=FEED_BODIES[HOSTS[request.url.host]])


def new_feeds():
    return contextlib.closing(httpx.Client(transport=httpx.MockTransport(feed_handler)))


def ok_groq():
    return contextlib.closing(httpx.Client(transport=httpx.MockTransport(mock_handler)))


def rate_limited_groq():
    def handler(request):
        return httpx.Response(429, headers={"retry-after": "100"}, content=b"SECRET BODY")

    return contextlib.closing(httpx.Client(transport=httpx.MockTransport(handler)))


def noop_sleep(seconds):
    return None


def do_tick(state, now=NOW, groq=ok_groq, feeds=new_feeds):
    return tick(now, state, SessionLocal, groq, feeds, noop_sleep)


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


def reset_tables():
    with engine.begin() as connection:
        name = connection.execute(text("select current_database()")).scalar_one()
        if name != TEST_DATABASE:
            pytest.exit("Refusing to run: connected to the wrong database", returncode=2)
        connection.execute(text("delete from notifications"))
        connection.execute(text("delete from system_events"))
        connection.execute(text("delete from search_runs"))
        connection.execute(text("delete from sources"))
        connection.execute(
            text(
                "insert into sources (name, badge, max_runs_per_day) values "
                "('weworkremotely', 'We Work Remotely', NULL), "
                "('remoteok', 'RemoteOK', NULL), "
                "('remotive', 'Remotive', 4)"
            )
        )


@pytest.fixture(autouse=True)
def scheduler_environment(monkeypatch):
    reset_tables()
    write_settings()
    monkeypatch.setattr(get_settings(), "groq_mock", True)
    monkeypatch.setattr("app.services.scoring.get_profile_text", lambda db: PROFILE_MARKER)
    yield
    reset_tables()
    write_settings(scheduler_enabled=False, score_batch_limit=10)


def add_run(hours_ago, trigger="manual"):
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into search_runs (trigger, status, started_at, finished_at) "
                "values (:trigger, 'done', :started, :started)"
            ),
            {"trigger": trigger, "started": NOW - timedelta(hours=hours_ago)},
        )


def add_jobs(count):
    with engine.begin() as connection:
        for index in range(count):
            url = f"https://example.com/p6b-sched/{index}"
            connection.execute(
                text(
                    "insert into jobs (source, title, company, url, url_normalized, "
                    "description, location, work_mode, published, priority, pipeline_status) "
                    "values ('remoteok', 'Support Agent', 'Acme', :url, :url, 'desc', "
                    "null, 'remote', null, 0, 'new')"
                ),
                {"url": url},
            )


def count(sql):
    with engine.connect() as connection:
        return connection.execute(text(sql)).scalar_one()


def scheduler_events():
    with engine.connect() as connection:
        return connection.execute(
            text(
                "select level, message from system_events "
                "where component = 'scheduler' order by id"
            )
        ).all()


def all_event_messages():
    with engine.connect() as connection:
        return [row[0] for row in connection.execute(text("select message from system_events"))]


@contextlib.contextmanager
def held_lock(key):
    connection = engine.connect()
    try:
        assert connection.execute(
            text("select pg_try_advisory_lock(:key)"), {"key": key}
        ).scalar_one()
        yield
    finally:
        connection.execute(text("select pg_advisory_unlock(:key)"), {"key": key})
        connection.commit()
        connection.close()


def test_disabled_scheduler_does_nothing():
    write_settings(scheduler_enabled=False)
    add_jobs(3)
    summary = do_tick(SchedulerState())
    assert summary == {"enabled": False, "hunt": None, "scoring": None}
    assert count("select count(*) from search_runs") == 0
    assert count("select count(*) from job_scores") == 0


def test_enabling_takes_effect_on_next_tick_without_restart():
    write_settings(scheduler_enabled=False)
    state = SchedulerState()
    assert do_tick(state)["enabled"] is False
    write_settings(scheduler_enabled=True)
    assert do_tick(state)["enabled"] is True


def test_due_hunt_runs_with_scheduled_trigger_and_notifies():
    state = SchedulerState(last_score_attempt=NOW)
    summary = do_tick(state)
    assert summary["hunt"] == "ran"
    with engine.connect() as connection:
        rows = connection.execute(text("select trigger, status from search_runs")).all()
    assert rows == [("scheduled", "done")]
    assert count("select count(*) from notifications where type = 'hunt_done'") == 1
    assert count("select count(*) from jobs") == 2
    messages = [message for _, message in scheduler_events()]
    assert any(message.startswith("Scheduled hunt finished: run") for message in messages)


def test_hunt_not_due_when_recent_run_exists():
    add_run(hours_ago=1)
    summary = do_tick(SchedulerState(last_score_attempt=NOW))
    assert summary["hunt"] == "not_due"
    assert count("select count(*) from search_runs") == 1


def test_manual_run_counts_for_the_interval_too():
    add_run(hours_ago=5, trigger="manual")
    assert do_tick(SchedulerState(last_score_attempt=NOW))["hunt"] == "not_due"


def test_hunt_due_after_interval_passes():
    add_run(hours_ago=7)
    assert do_tick(SchedulerState(last_score_attempt=NOW))["hunt"] == "ran"
    assert count("select count(*) from search_runs") == 2


def test_hunt_lock_conflict_is_silent():
    with held_lock(HUNT_LOCK_KEY):
        summary = do_tick(SchedulerState(last_score_attempt=NOW))
    assert summary["hunt"] == "locked"
    assert count("select count(*) from search_runs") == 0
    assert scheduler_events() == []


def test_due_scoring_runs_with_batch_limit():
    add_run(hours_ago=1)
    add_jobs(3)
    summary = do_tick(SchedulerState())
    assert summary["scoring"] == "ran"
    assert count("select count(*) from job_scores") == 2
    assert count("select count(*) from jobs where pipeline_status = 'scored'") == 2
    assert count("select count(*) from jobs where pipeline_status = 'new'") == 1
    messages = [message for _, message in scheduler_events()]
    assert "Scheduled scoring: attempted 2, scored 2, failed 0, errored 0" in messages


def test_scoring_waits_for_interval_then_runs_again():
    add_run(hours_ago=1)
    add_jobs(3)
    state = SchedulerState()
    assert do_tick(state, NOW)["scoring"] == "ran"
    assert do_tick(state, NOW + timedelta(minutes=10))["scoring"] == "not_due"
    assert count("select count(*) from job_scores") == 2
    add_run(hours_ago=-1)
    assert do_tick(state, NOW + timedelta(minutes=31))["scoring"] == "ran"
    assert count("select count(*) from job_scores") == 3


def test_scoring_not_due_without_new_jobs():
    add_run(hours_ago=1)
    state = SchedulerState()
    assert do_tick(state)["scoring"] == "no_new_jobs"
    assert state.last_score_attempt is None


def test_scoring_lock_conflict_is_silent_and_retried_next_tick():
    add_run(hours_ago=1)
    add_jobs(1)
    state = SchedulerState()
    with held_lock(SCORE_LOCK_KEY):
        assert do_tick(state)["scoring"] == "locked"
    assert state.last_score_attempt is None
    assert scheduler_events() == []
    assert count("select count(*) from job_scores") == 0


def test_missing_profile_warns_once_and_leaks_nothing(monkeypatch):
    def missing(db):
        raise HTTPException(status_code=500, detail="Profile is not set. Save a profile with PUT /profile first.")

    monkeypatch.setattr("app.services.scoring.get_profile_text", missing)
    add_run(hours_ago=1)
    add_jobs(1)
    state = SchedulerState()
    assert do_tick(state, NOW)["scoring"] == "skipped"
    assert do_tick(state, NOW + timedelta(minutes=31))["scoring"] == "skipped"
    events = scheduler_events()
    assert events == [("warning", "Scheduled scoring skipped: Profile is not set. Save a profile with PUT /profile first.")]
    assert do_tick(state, NOW + timedelta(hours=2))["scoring"] == "skipped"
    assert len(scheduler_events()) == 2
    assert count("select count(*) from job_scores") == 0


def test_rate_limited_is_logged_and_not_retried_until_next_interval():
    add_run(hours_ago=1)
    add_jobs(3)
    state = SchedulerState()
    summary = do_tick(state, NOW, groq=rate_limited_groq)
    assert summary["scoring"] == "stopped"
    events = scheduler_events()
    assert ("warning", "Scheduled scoring stopped: rate_limited") in events
    assert do_tick(state, NOW + timedelta(minutes=5), groq=rate_limited_groq)["scoring"] == "not_due"
    assert count("select count(*) from job_scores") == 0
    assert all(PROFILE_MARKER not in message for message in all_event_messages())
    assert all("SECRET BODY" not in message for message in all_event_messages())


def test_hunt_error_does_not_stop_the_tick(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(scheduler, "hunt_step", boom)
    summary = do_tick(SchedulerState())
    assert summary["hunt"] == "error"
    assert summary["scoring"] == "no_new_jobs"
    assert scheduler_events() == [("error", "Scheduled hunt failed: RuntimeError")]


def test_scoring_error_does_not_raise(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(scheduler, "score_step", boom)
    add_run(hours_ago=1)
    summary = do_tick(SchedulerState(), groq=ok_groq)

def test_settings_read_failure_does_not_raise():
    def broken_factory():
        raise RuntimeError("database down")

    state = SchedulerState()
    summary = tick(NOW, state, broken_factory, ok_groq, new_feeds, noop_sleep)
    assert summary["enabled"] is False


def test_repeated_error_is_logged_once_per_hour(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("x")

    monkeypatch.setattr(scheduler, "hunt_step", boom)
    state = SchedulerState()
    for minutes in (0, 1, 2, 3):
        do_tick(state, NOW + timedelta(minutes=minutes))
    assert len(scheduler_events()) == 1
    do_tick(state, NOW + timedelta(minutes=61))
    assert len(scheduler_events()) == 2


def test_thread_is_disabled_in_tests():
    assert get_settings().scheduler_thread_enabled is False
    assert not any(thread.name == "scheduler" for thread in threading.enumerate())


def test_scheduler_thread_calls_tick_and_stops_cleanly(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "tick", lambda now, state: calls.append(now))
    runner = SchedulerThread(interval=0.01)
    runner.start()
    time.sleep(0.2)
    runner.stop()
    assert len(calls) >= 1
    assert not runner.thread.is_alive()


def test_scheduler_thread_survives_tick_exceptions(monkeypatch):
    calls = []

    def boom(now, state):
        calls.append(now)
        raise RuntimeError("x")

    monkeypatch.setattr(scheduler, "tick", boom)
    runner = SchedulerThread(interval=0.01)
    runner.start()
    time.sleep(0.2)
    runner.stop()
    assert len(calls) >= 2
    assert not runner.thread.is_alive()


def test_empty_database_profile_warns_once_with_real_reader(monkeypatch):
    from app.services.profile import get_profile_text

    monkeypatch.setattr("app.services.scoring.get_profile_text", get_profile_text)
    add_run(hours_ago=1)
    add_jobs(1)
    state = SchedulerState()
    assert do_tick(state, NOW)["scoring"] == "skipped"
    assert do_tick(state, NOW + timedelta(minutes=31))["scoring"] == "skipped"
    assert scheduler_events() == [
        ("warning", "Scheduled scoring skipped: Profile is not set. Save a profile with PUT /profile first.")
    ]
    assert count("select count(*) from job_scores") == 0
