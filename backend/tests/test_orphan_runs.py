from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import main
from app.config import get_settings
from app.db import engine
from app.main import app
from app.services.orphan_runs import close_orphan_runs

BASE = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
INTERRUPTED = "Interrupted by a restart."


def clear_tables():
    with engine.begin() as connection:
        connection.execute(text("delete from search_runs"))
        connection.execute(text("delete from system_events"))
        connection.execute(text("delete from notifications"))


@pytest.fixture(autouse=True)
def clean():
    clear_tables()
    yield
    clear_tables()


def add_run(status, finished_at=None, steps=()):
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                "insert into search_runs (trigger, status, started_at, finished_at) "
                "values ('p10a-test', :status, :started, :finished) returning id"
            ),
            {"status": status, "started": BASE, "finished": finished_at},
        ).scalar_one()
        for source, step_status, message in steps:
            connection.execute(
                text(
                    "insert into search_run_steps (run_id, source, status, message) "
                    "values (:run_id, :source, :status, :message)"
                ),
                {"run_id": run_id, "source": source, "status": step_status, "message": message},
            )
    return run_id


def read_run(run_id):
    with engine.connect() as connection:
        row = connection.execute(
            text("select status, finished_at from search_runs where id = :id"),
            {"id": run_id},
        ).one()
    return tuple(row)


def read_steps(run_id):
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "select source, status, message from search_run_steps "
                "where run_id = :id order by id"
            ),
            {"id": run_id},
        ).all()
    return [tuple(row) for row in rows]


def read_events():
    with engine.connect() as connection:
        rows = connection.execute(
            text("select component, level, run_id, message from system_events order by id")
        ).all()
    return [tuple(row) for row in rows]


def count_notifications():
    with engine.connect() as connection:
        return connection.execute(text("select count(*) from notifications")).scalar_one()


def test_running_run_with_running_step_becomes_error():
    run_id = add_run("running", steps=[("email", "running", None)])
    assert close_orphan_runs() == 1
    status, finished = read_run(run_id)
    assert status == "error"
    assert finished is not None
    assert abs(datetime.now(timezone.utc) - finished) < timedelta(seconds=60)
    assert read_steps(run_id) == [("email", "error", INTERRUPTED)]


def test_running_run_whose_steps_are_done_becomes_error():
    run_id = add_run("running", steps=[("email", "done", None)])
    assert close_orphan_runs() == 1
    status, finished = read_run(run_id)
    assert status == "error"
    assert finished is not None
    assert read_steps(run_id) == [("email", "done", None)]


def test_only_running_steps_are_changed():
    run_id = add_run(
        "running",
        steps=[
            ("remoteok", "done", "kept done"),
            ("remotive", "error", "kept error"),
            ("weworkremotely", "skipped", "Source is disabled"),
            ("email", "running", None),
        ],
    )
    assert close_orphan_runs() == 1
    assert read_steps(run_id) == [
        ("remoteok", "done", "kept done"),
        ("remotive", "error", "kept error"),
        ("weworkremotely", "skipped", "Source is disabled"),
        ("email", "error", INTERRUPTED),
    ]


def test_hunt_run_is_also_closed():
    run_id = add_run("running", steps=[("remoteok", "running", None)])
    assert close_orphan_runs() == 1
    assert read_run(run_id)[0] == "error"
    assert read_steps(run_id) == [("remoteok", "error", INTERRUPTED)]


def test_finished_runs_are_not_touched():
    done_finished = BASE + timedelta(minutes=1)
    error_finished = BASE + timedelta(minutes=2)
    done_id = add_run("done", done_finished, steps=[("email", "done", None)])
    error_id = add_run("error", error_finished, steps=[("email", "error", "kept error")])
    assert close_orphan_runs() == 0
    assert read_run(done_id) == ("done", done_finished)
    assert read_run(error_id) == ("error", error_finished)
    assert read_steps(done_id) == [("email", "done", None)]
    assert read_steps(error_id) == [("email", "error", "kept error")]


def test_no_event_is_written_when_nothing_is_closed():
    add_run("done", BASE + timedelta(minutes=1), steps=[("email", "done", None)])
    assert close_orphan_runs() == 0
    assert read_events() == []


def test_one_summary_event_without_email_content():
    add_run("running", steps=[("email", "running", None)])
    add_run("running", steps=[("remoteok", "running", None)])
    add_run("done", BASE + timedelta(minutes=1), steps=[("email", "done", None)])
    assert close_orphan_runs() == 2
    assert read_events() == [
        ("startup", "warning", None, "Closed 2 orphaned run(s) at startup.")
    ]
    assert count_notifications() == 0


def test_closing_twice_does_nothing_the_second_time():
    add_run("running", steps=[("email", "running", None)])
    assert close_orphan_runs() == 1
    assert close_orphan_runs() == 0
    assert len(read_events()) == 1


def test_function_is_not_called_by_the_lifespan_in_tests():
    assert get_settings().scheduler_thread_enabled is False
    run_id = add_run("running", steps=[("email", "running", None)])
    with TestClient(app):
        pass
    assert read_run(run_id)[0] == "running"
    assert read_steps(run_id) == [("email", "running", None)]


class FakeScheduler:
    events = None

    def start(self):
        self.events.append("scheduler_start")

    def stop(self):
        self.events.append("scheduler_stop")


def install_fakes(monkeypatch, close):
    events = []
    FakeScheduler.events = events
    monkeypatch.setattr(main.settings, "scheduler_thread_enabled", True)
    monkeypatch.setattr(main, "close_orphan_runs", close)
    monkeypatch.setattr(main, "SchedulerThread", FakeScheduler)
    return events


def test_startup_closes_orphans_before_the_scheduler_starts(monkeypatch):
    events = []
    events = install_fakes(monkeypatch, lambda: events.append("close"))
    FakeScheduler.events = events
    monkeypatch.setattr(main, "close_orphan_runs", lambda: events.append("close"))
    with TestClient(app):
        assert events == ["close", "scheduler_start"]
    assert events == ["close", "scheduler_start", "scheduler_stop"]


def test_startup_continues_when_closing_orphans_fails(monkeypatch):
    def broken():
        raise RuntimeError("boom")

    events = install_fakes(monkeypatch, broken)
    with TestClient(app):
        assert events == ["scheduler_start"]
    assert events == ["scheduler_start", "scheduler_stop"]