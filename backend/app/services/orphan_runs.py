from sqlalchemy import text

from app.db import SessionLocal

COMPONENT = "startup"
STEP_MESSAGE = "Interrupted by a restart."


def close_orphan_runs(session_factory=SessionLocal) -> int:
    with session_factory() as db:
        run_ids = db.execute(
            text("select id from search_runs where status = 'running' order by id")
        ).scalars().all()
    closed = 0
    for run_id in run_ids:
        with session_factory() as db:
            try:
                db.execute(
                    text(
                        "update search_run_steps set status = 'error', message = :message "
                        "where run_id = :run_id and status = 'running'"
                    ),
                    {"message": STEP_MESSAGE, "run_id": run_id},
                )
                result = db.execute(
                    text(
                        "update search_runs set status = 'error', finished_at = now() "
                        "where id = :id and status = 'running'"
                    ),
                    {"id": run_id},
                )
                db.commit()
            except Exception:
                db.rollback()
                continue
            closed += result.rowcount
    if closed > 0:
        with session_factory() as db:
            db.execute(
                text(
                    "insert into system_events (component, level, message) "
                    "values (:component, 'warning', :message)"
                ),
                {
                    "component": COMPONENT,
                    "message": f"Closed {closed} orphaned run(s) at startup.",
                },
            )
            db.commit()
    return closed