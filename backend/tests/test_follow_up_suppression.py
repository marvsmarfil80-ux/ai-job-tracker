from datetime import date

import pytest
from sqlalchemy import text

from app.db import SessionLocal, engine
from app.services.follow_up_reminders import find_overdue_without_reminder
from tests.email_helpers import make_application

DUE = date(2026, 1, 1)
TODAY = date(2026, 1, 10)


def add_follow_up(application_id):
    with engine.begin() as connection:
        return connection.execute(
            text(
                "insert into follow_ups (application_id, title, due_date, status) "
                "values (:application_id, 'Check in', :due, 'pending') returning id"
            ),
            {"application_id": application_id, "due": DUE},
        ).scalar_one()


def found_ids():
    with SessionLocal() as db:
        return [row["id"] for row in find_overdue_without_reminder(db, TODAY)]


def set_status(application_id, status):
    with engine.begin() as connection:
        connection.execute(
            text("update applications set status = :status where id = :id"),
            {"status": status, "id": application_id},
        )


@pytest.mark.parametrize(
    "status", ["applied", "under_review", "assessment", "interview", "offer"]
)
def test_active_applications_still_get_reminders(status):
    follow_up_id = add_follow_up(make_application("Example Corp", status))
    assert found_ids() == [follow_up_id]


@pytest.mark.parametrize("status", ["rejected", "withdrawn"])
def test_closed_applications_get_no_reminder(status):
    add_follow_up(make_application("Example Corp", status))
    assert found_ids() == []


def test_reminder_stops_when_the_application_becomes_rejected():
    application_id = make_application("Example Corp", "interview")
    follow_up_id = add_follow_up(application_id)
    assert found_ids() == [follow_up_id]
    set_status(application_id, "rejected")
    assert found_ids() == []


def test_only_the_closed_application_is_skipped():
    open_id = add_follow_up(make_application("Example Corp", "applied"))
    add_follow_up(make_application("Sample Inc", "withdrawn"))
    assert found_ids() == [open_id]


def test_existing_notifications_are_not_deleted():
    follow_up_id = add_follow_up(make_application("Example Corp", "rejected"))
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into notifications (type, message, link) "
                "values ('follow_up_overdue', 'Follow-up overdue: Check in', :link)"
            ),
            {"link": f"/follow-ups/{follow_up_id}"},
        )
    assert found_ids() == []
    with engine.connect() as connection:
        count = connection.execute(
            text("select count(*) from notifications where type = 'follow_up_overdue'")
        ).scalar_one()
    assert count == 1