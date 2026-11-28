import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.main import app
from tests.email_helpers import make_application, make_email, read_events, read_status


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def add_event(application_id, from_status, to_status, source, email_id=None):
    with engine.begin() as connection:
        connection.execute(
            text("update applications set status = :status where id = :id"),
            {"status": to_status, "id": application_id},
        )
        return connection.execute(
            text(
                "insert into application_events "
                "(application_id, from_status, to_status, source, email_id) "
                "values (:application_id, :from_status, :to_status, :source, :email_id) "
                "returning id"
            ),
            {
                "application_id": application_id,
                "from_status": from_status,
                "to_status": to_status,
                "source": source,
                "email_id": email_id,
            },
        ).scalar_one()


def count_notifications():
    with engine.connect() as connection:
        return connection.execute(text("select count(*) from notifications")).scalar_one()


def email_state(email_id):
    with engine.connect() as connection:
        return connection.execute(
            text("select status from emails where id = :id"), {"id": email_id}
        ).scalar_one()


def undo(client, headers, event_id):
    return client.post(f"/application-events/{event_id}/undo", headers=headers)


def email_change(status_before="applied", status_after="interview"):
    application_id = make_application("Example Corp", status_before)
    email_id = make_email(status="processed")
    event_id = add_event(application_id, status_before, status_after, "email", email_id)
    return application_id, email_id, event_id


def test_missing_and_wrong_key_are_rejected(client):
    assert client.post("/application-events/1/undo").status_code == 401
    response = client.post("/application-events/1/undo", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


def test_undo_restores_the_previous_status(client, headers):
    application_id, email_id, event_id = email_change("applied", "interview")
    response = undo(client, headers, event_id)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == application_id
    assert data["status"] == "applied"
    assert len(data["events"]) == 2
    assert read_status(application_id) == "applied"
    assert read_events(application_id) == [
        ("applied", "interview", "email", email_id),
        ("interview", "applied", "undo", email_id),
    ]
    assert email_state(email_id) == "processed"


def test_undo_creates_no_notification(client, headers):
    _, _, event_id = email_change()
    assert undo(client, headers, event_id).status_code == 200
    assert count_notifications() == 0


def test_undo_is_blocked_when_a_newer_event_exists(client, headers):
    application_id, email_id, event_id = email_change("applied", "interview")
    add_event(application_id, "interview", "offer", "manual")
    response = undo(client, headers, event_id)
    assert response.status_code == 409
    assert response.json()["detail"] == "The status has changed since this event"
    assert read_status(application_id) == "offer"
    assert len(read_events(application_id)) == 2


def test_second_undo_is_blocked(client, headers):
    application_id, _, event_id = email_change("applied", "interview")
    assert undo(client, headers, event_id).status_code == 200
    again = undo(client, headers, event_id)
    assert again.status_code == 409
    assert again.json()["detail"] == "This status change was already undone"
    assert read_status(application_id) == "applied"
    assert len(read_events(application_id)) == 2


def test_an_undo_event_cannot_be_undone(client, headers):
    application_id, email_id, event_id = email_change()
    assert undo(client, headers, event_id).status_code == 200
    undo_event_id = read_undo_event_id(application_id)
    response = undo(client, headers, undo_event_id)
    assert response.status_code == 422
    assert response.json()["detail"] == "Only email status changes can be undone"


def read_undo_event_id(application_id):
    with engine.connect() as connection:
        return connection.execute(
            text(
                "select id from application_events "
                "where application_id = :id and source = 'undo'"
            ),
            {"id": application_id},
        ).scalar_one()


def test_manual_events_cannot_be_undone(client, headers):
    application_id = make_application("Example Corp", "applied")
    event_id = add_event(application_id, "applied", "interview", "manual")
    response = undo(client, headers, event_id)
    assert response.status_code == 422
    assert response.json()["detail"] == "Only email status changes can be undone"
    assert read_status(application_id) == "interview"


def test_event_without_a_previous_status_cannot_be_undone(client, headers):
    application_id = make_application("Example Corp", "applied")
    email_id = make_email(status="processed")
    event_id = add_event(application_id, None, "applied", "email", email_id)
    response = undo(client, headers, event_id)
    assert response.status_code == 422
    assert response.json()["detail"] == "This event cannot be undone"


def test_unknown_event_is_404_and_bad_id_is_422(client, headers):
    response = undo(client, headers, 999999)
    assert response.status_code == 404
    assert response.json()["detail"] == "Application event not found"
    assert undo(client, headers, 0).status_code == 422


def test_undo_after_a_new_email_change_only_works_for_the_latest(client, headers):
    application_id = make_application("Example Corp", "applied")
    first_email = make_email(status="processed")
    second_email = make_email(status="processed")
    first_event = add_event(application_id, "applied", "assessment", "email", first_email)
    second_event = add_event(application_id, "assessment", "interview", "email", second_email)
    blocked = undo(client, headers, first_event)
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "The status has changed since this event"
    assert undo(client, headers, second_event).status_code == 200
    assert read_status(application_id) == "assessment"


def event_by_id(data):
    return {event["id"]: event for event in data["events"]}


def test_detail_events_include_source_and_email_id(client, headers):
    application_id = make_application("Example Corp", "applied")
    email_id = make_email(status="processed")
    email_event = add_event(application_id, "applied", "interview", "email", email_id)
    manual_event = add_event(application_id, "interview", "offer", "manual")
    response = client.get(f"/applications/{application_id}", headers=headers)
    assert response.status_code == 200
    events = event_by_id(response.json())
    assert set(events) == {email_event, manual_event}
    for event in events.values():
        assert set(event) == {"id", "from_status", "to_status", "changed_at", "source", "email_id"}
    assert events[email_event]["source"] == "email"
    assert events[email_event]["email_id"] == email_id
    assert events[manual_event]["source"] == "manual"
    assert events[manual_event]["email_id"] is None


def test_undo_response_includes_the_undo_event_source(client, headers):
    application_id, email_id, event_id = email_change("applied", "interview")
    response = undo(client, headers, event_id)
    assert response.status_code == 200
    events = event_by_id(response.json())
    undo_event_id = read_undo_event_id(application_id)
    assert set(events) == {event_id, undo_event_id}
    assert events[event_id]["source"] == "email"
    assert events[event_id]["email_id"] == email_id
    assert events[undo_event_id]["source"] == "undo"
    assert events[undo_event_id]["email_id"] == email_id


def test_patch_status_writes_a_manual_event(client, headers):
    application_id = make_application("Example Corp", "applied")
    response = client.patch(
        f"/applications/{application_id}", headers=headers, json={"status": "under_review"}
    )
    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) == 1
    assert events[0]["source"] == "manual"
    assert events[0]["email_id"] is None
