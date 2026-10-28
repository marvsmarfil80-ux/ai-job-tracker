from sqlalchemy import text
from sqlalchemy.orm import Session

COMPONENT = "notifications"
TYPE_HUNT_DONE = "hunt_done"

INSERT_NOTIFICATION = text(
    "insert into notifications (type, message, link) "
    "values (:type, :message, :link) returning id"
)

SELECT_STEPS = text(
    'select source, status, "new" from search_run_steps where run_id = :id order by id'
)

COLUMNS = "id, type, message, link, is_read, created_at"


def build_hunt_message(status: str, steps: list[dict], unexpected: bool = False) -> str:
    if status == "error":
        if unexpected:
            return "Hunt failed: an unexpected error occurred"
        return "Hunt failed: all sources returned errors"
    total = sum(step["new"] for step in steps if step["status"] == "done")
    parts = []
    for step in steps:
        if step["status"] == "done":
            parts.append(f"{step['source']} {step['new']}")
        elif step["status"] == "skipped":
            parts.append(f"{step['source']} skipped")
        else:
            parts.append(f"{step['source']} failed")
    noun = "job" if total == 1 else "jobs"
    detail = f" ({', '.join(parts)})" if parts else ""
    return f"Hunt finished: {total} new {noun}{detail}"


def insert_notification(db: Session, type_: str, message: str, link: str | None) -> int:
    return db.execute(
        INSERT_NOTIFICATION, {"type": type_, "message": message, "link": link}
    ).scalar_one()


def log_failure(db: Session, run_id: int, exc: Exception) -> None:
    try:
        db.rollback()
        db.execute(
            text(
                "insert into system_events (component, level, run_id, message) "
                "values (:component, 'error', :run_id, :message)"
            ),
            {
                "component": COMPONENT,
                "run_id": run_id,
                "message": f"Failed to write hunt_done notification: {type(exc).__name__}",
            },
        )
        db.commit()
    except Exception:
        db.rollback()


def notify_hunt_done(
    db: Session, run_id: int, status: str, unexpected: bool = False
) -> bool:
    try:
        steps = [dict(row) for row in db.execute(SELECT_STEPS, {"id": run_id}).mappings().all()]
        message = build_hunt_message(status, steps, unexpected)
        insert_notification(db, TYPE_HUNT_DONE, message, f"/hunts/{run_id}")
        db.commit()
        return True
    except Exception as exc:
        log_failure(db, run_id, exc)
        return False


def list_notifications(
    db: Session, unread: bool | None, limit: int, offset: int
) -> tuple[list[dict], int, int]:
    where = ""
    params: dict = {"limit": limit, "offset": offset}
    if unread is not None:
        where = "where is_read = :is_read"
        params["is_read"] = not unread
    total = db.execute(
        text(f"select count(*) from notifications {where}"),
        {key: value for key, value in params.items() if key == "is_read"},
    ).scalar_one()
    unread_count = db.execute(
        text("select count(*) from notifications where is_read = false")
    ).scalar_one()
    rows = db.execute(
        text(
            f"select {COLUMNS} from notifications {where} "
            "order by created_at desc, id desc limit :limit offset :offset"
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows], total, unread_count


def set_read(db: Session, notification_id: int, is_read: bool) -> dict | None:
    row = db.execute(
        text(
            f"update notifications set is_read = :is_read where id = :id returning {COLUMNS}"
        ),
        {"is_read": is_read, "id": notification_id},
    ).mappings().first()
    db.commit()
    return dict(row) if row is not None else None