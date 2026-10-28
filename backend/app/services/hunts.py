import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import engine
from app.services.feeds import PARSERS, FeedError, FeedJob, fetch_feed
from app.services.jobs import priority_for_source

LOCK_KEY = 5150002
COMPONENT = "feeds"
TRIGGER_MANUAL = "manual"
DEFAULT_MAX_RUNS_PER_DAY = 4
DAY_START_SQL = (
    "(date_trunc('day', now() at time zone 'Asia/Manila') at time zone 'Asia/Manila')"
)

INSERT_JOB = text(
    "insert into jobs (source, title, company, url, url_normalized, description, "
    "location, work_mode, published, priority, pipeline_status) "
    "values (:source, :title, :company, :url, :url_normalized, :description, "
    ":location, 'remote', :published, :priority, 'new') "
    "on conflict (url_normalized) do nothing returning id"
)


def effective_limit(value: int | None) -> int:
    return DEFAULT_MAX_RUNS_PER_DAY if value is None else value


def count_runs_today(db: Session, source: str) -> int:
    return db.execute(
        text(
            "select count(*) from search_run_steps s "
            "join search_runs r on r.id = s.run_id "
            "where s.source = :source and s.status <> 'skipped' "
            f"and r.started_at >= {DAY_START_SQL}"
        ),
        {"source": source},
    ).scalar_one()


def acquire_lock() -> Connection:
    connection = engine.connect()
    locked = connection.execute(
        text("select pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}
    ).scalar_one()
    if not locked:
        connection.close()
        raise HTTPException(status_code=409, detail="A hunt is already running")
    return connection


def release_lock(connection: Connection) -> None:
    try:
        connection.execute(text("select pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
        connection.commit()
    except Exception:
        connection.invalidate()
    else:
        connection.close()


def log_event(db: Session, run_id: int, message: str) -> None:
    db.execute(
        text(
            "insert into system_events (component, level, run_id, message) "
            "values (:component, 'error', :run_id, :message)"
        ),
        {"component": COMPONENT, "run_id": run_id, "message": message},
    )


def add_step(db: Session, run_id: int, source: str, status: str, message: str | None = None) -> int:
    return db.execute(
        text(
            "insert into search_run_steps (run_id, source, status, message) "
            "values (:run_id, :source, :status, :message) returning id"
        ),
        {"run_id": run_id, "source": source, "status": status, "message": message},
    ).scalar_one()


def finish_step(
    db: Session, step_id: int, status: str, found: int, new: int, message: str | None
) -> None:
    db.execute(
        text(
            'update search_run_steps set status = :status, found = :found, "new" = :new, '
            "message = :message where id = :id"
        ),
        {"status": status, "found": found, "new": new, "message": message, "id": step_id},
    )


def save_jobs(db: Session, jobs: list[FeedJob]) -> tuple[int, int]:
    new = 0
    failed = 0
    for job in jobs:
        params = {
            "source": job.source,
            "title": job.title,
            "company": job.company,
            "url": job.url,
            "url_normalized": job.url_normalized,
            "description": job.description,
            "location": job.location,
            "published": job.published,
            "priority": priority_for_source(job.source),
        }
        try:
            with db.begin_nested():
                inserted = db.execute(INSERT_JOB, params).first()
        except SQLAlchemyError:
            failed += 1
            continue
        if inserted is not None:
            new += 1
    return new, failed


def fail_step(db: Session, run_id: int, step_id: int, source: str, reason: str) -> tuple[str, int]:
    finish_step(db, step_id, "error", 0, 0, reason)
    log_event(db, run_id, f"{source}: {reason}")
    db.commit()
    return "error", 0


def run_source(db: Session, client: httpx.Client, run_id: int, source: str) -> tuple[str, int]:
    step_id = add_step(db, run_id, source, "running")
    db.execute(text("update sources set last_run_at = now() where name = :name"), {"name": source})
    db.commit()
    try:
        raw = fetch_feed(client, source)
        parsed = PARSERS[source](raw)
        new, failed = save_jobs(db, parsed.jobs)
    except FeedError as exc:
        db.rollback()
        return fail_step(db, run_id, step_id, source, str(exc))
    except Exception as exc:
        db.rollback()
        return fail_step(
            db, run_id, step_id, source, f"Unexpected {type(exc).__name__} while processing feed"
        )
    skipped = parsed.skipped + failed
    message = f"Skipped {skipped} invalid items" if skipped else None
    finish_step(db, step_id, "done", len(parsed.jobs), new, message)
    db.commit()
    return "done", new


def build_plan(rows, requested: list[str] | None):
    by_name = {row["name"]: row for row in rows}
    if requested is None:
        return [(row["name"], row) for row in rows if row["enabled"] and row["name"] in PARSERS]
    return [(name, by_name.get(name)) for name in requested]


def skip_reason(db: Session, name: str, row) -> str | None:
    if row is None:
        return "Source is not configured"
    if not row["enabled"]:
        return "Source is disabled"
    if count_runs_today(db, name) >= effective_limit(row["max_runs_per_day"]):
        return "Daily run limit reached"
    return None


def close_run(db: Session, run_id: int, status: str, total_new: int) -> None:
    db.execute(
        text(
            "update search_runs set status = :status, finished_at = now(), "
            "total_new = :total where id = :id"
        ),
        {"status": status, "total": total_new, "id": run_id},
    )
    db.commit()


def execute_hunt(db: Session, client: httpx.Client, requested: list[str] | None) -> int:
    rows = db.execute(
        text("select name, enabled, max_runs_per_day from sources order by id")
    ).mappings().all()
    plan = build_plan(rows, requested)
    run_id = db.execute(
        text("insert into search_runs (trigger) values (:trigger) returning id"),
        {"trigger": TRIGGER_MANUAL},
    ).scalar_one()
    db.commit()

    statuses: list[str] = []
    total_new = 0
    try:
        for name, row in plan:
            reason = skip_reason(db, name, row)
            if reason is not None:
                add_step(db, run_id, name, "skipped", reason)
                db.commit()
                statuses.append("skipped")
                continue
            status, new = run_source(db, client, run_id, name)
            statuses.append(status)
            total_new += new
    except Exception:
        db.rollback()
        close_run(db, run_id, "error", total_new)
        raise

    final = "error" if statuses and all(item == "error" for item in statuses) else "done"
    close_run(db, run_id, final, total_new)
    return run_id


def load_run(db: Session, run_id: int) -> dict | None:
    run = db.execute(
        text(
            "select id, trigger, status, started_at, finished_at, total_new "
            "from search_runs where id = :id"
        ),
        {"id": run_id},
    ).mappings().first()
    if run is None:
        return None
    steps = db.execute(
        text(
            'select source, status, found, "new", message '
            "from search_run_steps where run_id = :id order by id"
        ),
        {"id": run_id},
    ).mappings().all()
    return {**dict(run), "steps": [dict(step) for step in steps]}


def list_runs(db: Session, limit: int, offset: int) -> tuple[list[dict], int]:
    total = db.execute(text("select count(*) from search_runs")).scalar_one()
    runs = db.execute(
        text(
            "select id, trigger, status, started_at, finished_at, total_new "
            "from search_runs order by started_at desc, id desc limit :limit offset :offset"
        ),
        {"limit": limit, "offset": offset},
    ).mappings().all()
    if not runs:
        return [], total
    steps = db.execute(
        text(
            'select run_id, source, status, found, "new", message '
            "from search_run_steps where run_id = any(cast(:ids as bigint[])) order by id"
        ),
        {"ids": [run["id"] for run in runs]},
    ).mappings().all()
    grouped: dict[int, list[dict]] = {}
    for step in steps:
        grouped.setdefault(step["run_id"], []).append(
            {key: step[key] for key in ("source", "status", "found", "new", "message")}
        )
    return [{**dict(run), "steps": grouped.get(run["id"], [])} for run in runs], total


def run_hunt(db: Session, client: httpx.Client, requested: list[str] | None) -> dict:
    lock = acquire_lock()
    try:
        run_id = execute_hunt(db, client, requested)
    finally:
        release_lock(lock)
    return load_run(db, run_id)