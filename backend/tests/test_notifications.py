import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.main import app
from app.routers.hunts import feed_client
from app.services.hunts import run_hunt

TEST_DATABASE = "jobtracker_test"
HOSTS = {
    "weworkremotely.com": "weworkremotely",
    "remoteok.com": "remoteok",
    "remotive.com": "remotive",
}

WWR_BODY = (
    '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
    "<item><title>Acme: Support Agent</title><region>Anywhere</region>"
    "<description>Help users</description>"
    "<pubDate>Tue, 27 Oct 2026 07:30:50 +0000</pubDate>"
    "<link>https://weworkremotely.com/remote-jobs/p6b-acme-support</link></item>"
    "</channel></rss>"
).encode()

REMOTEOK_BODY = json.dumps(
    [
        {"last_updated": "1793001612", "legal": "Fake legal notice"},
        {
            "position": "Data Entry Clerk",
            "company": "Gamma",
            "url": "https://remoteok.com/remote-jobs/p6b-data-entry-1",
            "date": "2026-10-26T08:00:12+00:00",
            "description": "<p>Enter data</p>",
            "location": "",
        },
    ]
).encode()

REMOTIVE_BODY = json.dumps(
    {
        "00-warning": "Fake warning",
        "0-legal-notice": "Fake legal notice",
        "jobs": [
            {
                "url": "https://remotive.com/remote-jobs/support/p6b-agent-1",
                "title": "Support Agent",
                "company_name": "Delta",
                "publication_date": "2026-10-22T18:40:19",
                "candidate_required_location": "Worldwide",
                "description": "<p>Answer tickets</p>",
            }
        ],
    }
).encode()

BODIES = {
    "weworkremotely": WWR_BODY,
    "remoteok": REMOTEOK_BODY,
    "remotive": REMOTIVE_BODY,
}


class Feeds:
    def __init__(self, error_status=None):
        self.error_status = error_status
        self.client = httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        if self.error_status is not None:
            return httpx.Response(self.error_status, content=b"SECRET BODY")
        return httpx.Response(200, content=BODIES[HOSTS[request.url.host]])


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
def notification_environment():
    reset_tables()
    yield
    reset_tables()


@pytest.fixture
def feeds():
    control = Feeds()
    app.dependency_overrides[feed_client] = lambda: control.client
    yield control
    app.dependency_overrides.pop(feed_client, None)
    control.client.close()


@pytest.fixture
def failing_feeds():
    control = Feeds(error_status=500)
    yield control
    control.client.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def run(control, trigger="manual"):
    with SessionLocal() as db:
        return run_hunt(db, control.client, None, trigger)


def notification_rows():
    with engine.connect() as connection:
        return connection.execute(
            text("select type, message, link, is_read from notifications order by id")
        ).all()


def event_rows():
    with engine.connect() as connection:
        return connection.execute(
            text("select component, level, run_id, message from system_events order by id")
        ).all()


def insert_series(count=5):
    with engine.begin() as connection:
        for index in range(count):
            connection.execute(
                text(
                    "insert into notifications (type, message, link, is_read, created_at) "
                    "values ('hunt_done', :message, null, false, "
                    "now() - cast(:minutes as integer) * interval '1 minute')"
                ),
                {"message": f"n{index}", "minutes": count - index},
            )


def ids_by_message():
    with engine.connect() as connection:
        rows = connection.execute(text("select id, message from notifications")).all()
    return {message: row_id for row_id, message in rows}


def test_successful_hunt_creates_hunt_done(feeds):
    result = run(feeds)
    rows = notification_rows()
    assert len(rows) == 1
    kind, message, link, is_read = rows[0]
    assert kind == "hunt_done"
    assert message.startswith(f"Hunt finished: {result['total_new']} new job")
    for source in ("weworkremotely", "remoteok", "remotive"):
        assert source in message
    assert link == f"/hunts/{result['id']}"
    assert is_read is False


def test_failed_hunt_creates_english_message_without_response_body(failing_feeds):
    result = run(failing_feeds)
    assert result["status"] == "error"
    rows = notification_rows()
    assert len(rows) == 1
    assert rows[0][0] == "hunt_done"
    assert rows[0][1] == "Hunt failed: all sources returned errors"
    assert "SECRET" not in rows[0][1]
    assert rows[0][2] == f"/hunts/{result['id']}"


def test_scheduled_hunt_also_creates_notification(feeds):
    result = run(feeds, trigger="scheduled")
    assert result["trigger"] == "scheduled"
    assert len(notification_rows()) == 1


def test_post_hunts_creates_notification(client, headers, feeds):
    response = client.post("/hunts", headers=headers)
    assert response.status_code == 201
    rows = notification_rows()
    assert len(rows) == 1
    assert rows[0][2] == f"/hunts/{response.json()['id']}"


def test_notification_write_failure_does_not_break_hunt(feeds, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("notification table exploded")

    monkeypatch.setattr("app.services.notifications.insert_notification", boom)
    result = run(feeds)
    assert result["status"] == "done"
    assert notification_rows() == []
    events = [row for row in event_rows() if row[0] == "notifications"]
    assert len(events) == 1
    assert events[0][1] == "error"
    assert events[0][2] == result["id"]
    assert events[0][3] == "Failed to write hunt_done notification: RuntimeError"
    assert "exploded" not in events[0][3]


def test_unexpected_error_creates_failure_notification(feeds, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("app.services.hunts.run_source", boom)
    with pytest.raises(RuntimeError):
        run(feeds)
    rows = notification_rows()
    assert len(rows) == 1
    assert rows[0][1] == "Hunt failed: an unexpected error occurred"
    with engine.connect() as connection:
        status = connection.execute(text("select status from search_runs")).scalar_one()
    assert status == "error"


def test_get_requires_key(client):
    assert client.get("/notifications").status_code == 401


def test_patch_requires_key(client):
    insert_series(1)
    row_id = ids_by_message()["n0"]
    assert client.patch(f"/notifications/{row_id}", json={"is_read": True}).status_code == 401
    assert notification_rows()[0][3] is False


def test_get_empty(client, headers):
    data = client.get("/notifications", headers=headers).json()
    assert data == {"items": [], "total": 0, "unread_count": 0, "limit": 50, "offset": 0}


def test_get_newest_first_with_counts(client, headers):
    insert_series(5)
    data = client.get("/notifications", headers=headers).json()
    assert [item["message"] for item in data["items"]] == ["n4", "n3", "n2", "n1", "n0"]
    assert data["total"] == 5
    assert data["unread_count"] == 5
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_unread_filter_and_unread_count(client, headers):
    insert_series(5)
    ids = ids_by_message()
    for name in ("n1", "n3"):
        client.patch(f"/notifications/{ids[name]}", json={"is_read": True}, headers=headers)
    unread = client.get("/notifications?unread=true", headers=headers).json()
    assert [item["message"] for item in unread["items"]] == ["n4", "n2", "n0"]
    assert unread["total"] == 3
    assert unread["unread_count"] == 3
    read = client.get("/notifications?unread=false", headers=headers).json()
    assert [item["message"] for item in read["items"]] == ["n3", "n1"]
    assert read["total"] == 2
    assert read["unread_count"] == 3


def test_pagination(client, headers):
    insert_series(5)
    data = client.get("/notifications?limit=2&offset=1", headers=headers).json()
    assert [item["message"] for item in data["items"]] == ["n3", "n2"]
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 1
    beyond = client.get("/notifications?offset=10", headers=headers).json()
    assert beyond["items"] == []
    assert beyond["total"] == 5


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=201", "offset=-1", "unread=maybe"],
)
def test_bad_query_values_are_rejected(client, headers, query):
    assert client.get(f"/notifications?{query}", headers=headers).status_code == 422


def test_limit_of_200_is_accepted(client, headers):
    assert client.get("/notifications?limit=200", headers=headers).status_code == 200


def test_patch_marks_read_and_back(client, headers):
    insert_series(1)
    row_id = ids_by_message()["n0"]
    response = client.patch(f"/notifications/{row_id}", json={"is_read": True}, headers=headers)
    assert response.status_code == 200
    assert response.json()["is_read"] is True
    assert response.json()["message"] == "n0"
    assert notification_rows()[0][3] is True
    again = client.patch(f"/notifications/{row_id}", json={"is_read": False}, headers=headers)
    assert again.json()["is_read"] is False
    assert notification_rows()[0][3] is False


@pytest.mark.parametrize(
    "body",
    [
        {"message": "changed"},
        {"is_read": True, "type": "status_changed"},
        {"is_read": True, "link": "/x"},
        {},
        {"is_read": "yes"},
        {"is_read": 1},
        {"is_read": None},
    ],
)
def test_patch_rejects_other_fields_and_bad_values(client, headers, body):
    insert_series(1)
    row_id = ids_by_message()["n0"]
    response = client.patch(f"/notifications/{row_id}", json=body, headers=headers)
    assert response.status_code == 422
    rows = notification_rows()
    assert rows[0][1] == "n0"
    assert rows[0][3] is False


def test_patch_missing_notification_is_404(client, headers):
    response = client.patch("/notifications/987654", json={"is_read": True}, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Notification not found"


def test_patch_invalid_id_is_422(client, headers):
    response = client.patch("/notifications/0", json={"is_read": True}, headers=headers)
    assert response.status_code == 422