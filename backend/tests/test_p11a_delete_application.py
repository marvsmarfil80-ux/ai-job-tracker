import itertools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.main import app

BASE = "https://example.com/p11a-delete"
HISTORY_MESSAGE = "This application has history. Set its status to withdrawn instead."

counter = itertools.count(1)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def make_job(client, headers):
    slug = f"job-{next(counter)}"
    response = client.post(
        "/jobs",
        json={"source": "manual", "title": "Python Developer", "company": "Acme", "url": f"{BASE}/{slug}"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def make_application(client, headers):
    job_id = make_job(client, headers)
    response = client.post("/applications", json={"job_id": job_id}, headers=headers)
    assert response.status_code == 201, response.text
    return job_id, response.json()["id"]


def count_rows(table, where="true", params=None):
    with engine.connect() as connection:
        return connection.execute(
            text(f"select count(*) from {table} where {where}"), params or {}
        ).scalar_one()


def add_follow_up(application_id):
    with engine.begin() as connection:
        return connection.execute(
            text(
                "insert into follow_ups (application_id, title) "
                "values (:application_id, 'Send a thank-you note') returning id"
            ),
            {"application_id": application_id},
        ).scalar_one()


def add_email(application_id):
    number = next(counter)
    with engine.begin() as connection:
        return connection.execute(
            text(
                "insert into emails (gmail_message_id, kind, sender, subject, received_at, "
                "application_id) values (:gid, 'application', 'hr@example.com', 'Hello', now(), "
                ":application_id) returning id"
            ),
            {"gid": f"p11a-delete-{number}", "application_id": application_id},
        ).scalar_one()


def email_application_id(email_id):
    with engine.connect() as connection:
        return connection.execute(
            text("select application_id from emails where id = :id"), {"id": email_id}
        ).scalar_one()


def awaiting_ids(client, headers):
    response = client.get("/jobs?awaiting_apply=true", headers=headers)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def test_delete_requires_the_api_key(client, headers):
    _, application_id = make_application(client, headers)
    assert client.delete(f"/applications/{application_id}").status_code == 401
    assert (
        client.delete(f"/applications/{application_id}", headers={"X-API-Key": "wrong"}).status_code
        == 401
    )
    assert count_rows("applications") == 1


def test_delete_returns_404_for_a_missing_application(client, headers):
    assert client.delete("/applications/999999", headers=headers).status_code == 404


def test_delete_removes_the_application_and_its_only_event(client, headers):
    job_id, application_id = make_application(client, headers)
    client.post(f"/jobs/{job_id}/open", headers=headers)
    assert awaiting_ids(client, headers) == []
    response = client.delete(f"/applications/{application_id}", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert count_rows("applications") == 0
    assert count_rows("application_events") == 0
    assert count_rows("jobs", "id = :id", {"id": job_id}) == 1
    assert awaiting_ids(client, headers) == [job_id]


def test_delete_removes_follow_ups_and_keeps_notifications(client, headers):
    _, application_id = make_application(client, headers)
    follow_up_id = add_follow_up(application_id)
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into notifications (type, message, link) values "
                "('follow_up_overdue', 'Follow-up overdue: Send a thank-you note', :link)"
            ),
            {"link": f"/follow-ups/{follow_up_id}"},
        )
    response = client.delete(f"/applications/{application_id}", headers=headers)
    assert response.status_code == 204
    assert count_rows("follow_ups") == 0
    assert count_rows("notifications") == 1


def test_deleting_twice_returns_404_the_second_time(client, headers):
    _, application_id = make_application(client, headers)
    assert client.delete(f"/applications/{application_id}", headers=headers).status_code == 204
    assert client.delete(f"/applications/{application_id}", headers=headers).status_code == 404


def test_delete_returns_409_when_the_status_is_not_applied(client, headers):
    _, application_id = make_application(client, headers)
    client.patch(f"/applications/{application_id}", json={"status": "interview"}, headers=headers)
    response = client.delete(f"/applications/{application_id}", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == HISTORY_MESSAGE
    assert count_rows("applications") == 1
    assert count_rows("application_events") == 2


def test_delete_returns_409_after_the_status_went_back_to_applied(client, headers):
    _, application_id = make_application(client, headers)
    client.patch(f"/applications/{application_id}", json={"status": "withdrawn"}, headers=headers)
    client.patch(f"/applications/{application_id}", json={"status": "applied"}, headers=headers)
    response = client.delete(f"/applications/{application_id}", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == HISTORY_MESSAGE
    assert count_rows("application_events") == 3


def test_delete_returns_409_when_the_only_event_is_not_manual(client, headers):
    _, application_id = make_application(client, headers)
    with engine.begin() as connection:
        connection.execute(
            text("update application_events set source = 'email' where application_id = :id"),
            {"id": application_id},
        )
    response = client.delete(f"/applications/{application_id}", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == HISTORY_MESSAGE
    assert count_rows("applications") == 1


def test_delete_returns_409_when_an_email_is_linked(client, headers):
    _, application_id = make_application(client, headers)
    email_id = add_email(application_id)
    response = client.delete(f"/applications/{application_id}", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == HISTORY_MESSAGE
    assert count_rows("applications") == 1
    assert email_application_id(email_id) == application_id


def test_a_refused_delete_keeps_the_follow_ups(client, headers):
    _, application_id = make_application(client, headers)
    add_follow_up(application_id)
    client.patch(f"/applications/{application_id}", json={"notes": "x", "status": "offer"}, headers=headers)
    response = client.delete(f"/applications/{application_id}", headers=headers)
    assert response.status_code == 409
    assert count_rows("follow_ups") == 1


def test_delete_does_not_touch_other_applications(client, headers):
    _, first = make_application(client, headers)
    other_job, second = make_application(client, headers)
    add_follow_up(second)
    assert client.delete(f"/applications/{first}", headers=headers).status_code == 204
    assert count_rows("applications") == 1
    assert count_rows("application_events") == 1
    assert count_rows("follow_ups") == 1
    assert client.get(f"/applications/{second}", headers=headers).status_code == 200