from itertools import count

from sqlalchemy import text

from app.db import engine

_numbers = count(1)


def make_application(company="Example Corp", status="applied", title="Support Agent"):
    number = next(_numbers)
    key = f"p9a-test-job-{number}"
    with engine.begin() as connection:
        job_id = connection.execute(
            text(
                "insert into jobs (source, title, company, url, url_normalized) "
                "values ('manual', :title, :company, :key, :key) returning id"
            ),
            {"title": title, "company": company, "key": key},
        ).scalar_one()
        return connection.execute(
            text("insert into applications (job_id, status) values (:job_id, :status) returning id"),
            {"job_id": job_id, "status": status},
        ).scalar_one()


def make_email(
    kind="application",
    sender="hr@example.com",
    subject="Hello",
    snippet="Hi",
    status="unprocessed",
    application_id=None,
    body_html=None,
):
    number = next(_numbers)
    with engine.begin() as connection:
        return connection.execute(
            text(
                "insert into emails "
                "(gmail_message_id, kind, sender, subject, snippet, body_html, "
                "received_at, status, application_id) "
                "values (:gid, :kind, :sender, :subject, :snippet, :body, now(), "
                ":status, :application_id) returning id"
            ),
            {
                "gid": f"p9a-test-{number}",
                "kind": kind,
                "sender": sender,
                "subject": subject,
                "snippet": snippet,
                "body": body_html,
                "status": status,
                "application_id": application_id,
            },
        ).scalar_one()


def add_allowed_sender(sender, kind="application", enabled=True):
    with engine.begin() as connection:
        return connection.execute(
            text(
                "insert into allowed_senders (sender, kind, enabled) "
                "values (:sender, :kind, :enabled) returning id"
            ),
            {"sender": sender, "kind": kind, "enabled": enabled},
        ).scalar_one()


def read_status(application_id):
    with engine.connect() as connection:
        return connection.execute(
            text("select status from applications where id = :id"), {"id": application_id}
        ).scalar_one()


def read_events(application_id):
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "select from_status, to_status, source, email_id "
                "from application_events where application_id = :id order by id"
            ),
            {"id": application_id},
        ).all()
    return [tuple(row) for row in rows]