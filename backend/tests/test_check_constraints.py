import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import engine


def insert_email(kind, status):
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into emails (gmail_message_id, kind, sender, received_at, status) "
                "values (:message_id, :kind, 'sender@example.com', now(), :status)"
            ),
            {"message_id": f"p5a-test-{uuid.uuid4().hex}", "kind": kind, "status": status},
        )


def count(table):
    with engine.connect() as connection:
        return connection.execute(text(f"select count(*) from {table}")).scalar_one()


def make_application():
    with engine.begin() as connection:
        job_id = connection.execute(
            text(
                "insert into jobs (source, title, url, url_normalized) values "
                "('manual', 'Check Test', 'https://example.com/p5a-test/check', "
                "'https://example.com/p5a-test/check') returning id"
            )
        ).scalar_one()
        return connection.execute(
            text("insert into applications (job_id, status) values (:job_id, 'applied') returning id"),
            {"job_id": job_id},
        ).scalar_one()


def insert_event(application_id, from_status, to_status="applied"):
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into application_events (application_id, from_status, to_status) "
                "values (:application_id, :from_status, :to_status)"
            ),
            {"application_id": application_id, "from_status": from_status, "to_status": to_status},
        )


def test_emails_kind_check():
    insert_email("job_alert", "unprocessed")
    insert_email("application", "unprocessed")
    assert count("emails") == 2
    with pytest.raises(IntegrityError) as error:
        insert_email("banana", "unprocessed")
    assert "ck_emails_kind_valid" in str(error.value)
    assert count("emails") == 2


def test_emails_status_check():
    for status in ("unprocessed", "processed", "error"):
        insert_email("job_alert", status)
    assert count("emails") == 3
    with pytest.raises(IntegrityError) as error:
        insert_email("job_alert", "banana")
    assert "ck_emails_status_valid" in str(error.value)
    assert count("emails") == 3


def test_application_events_from_status_check():
    application_id = make_application()
    insert_event(application_id, None)
    insert_event(application_id, "applied", "interview")
    assert count("application_events") == 2
    with pytest.raises(IntegrityError) as error:
        insert_event(application_id, "banana")
    assert "ck_application_events_from_status_valid" in str(error.value)
    assert count("application_events") == 2
