import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.main import app
from app.services import email_processing
from app.services.groq_client import get_groq_client
from tests.email_helpers import make_application, make_email, read_events, read_status

ENDPOINTS = [
    ("GET", "/emails"),
    ("POST", "/emails/process"),
    ("GET", "/emails/1"),
    ("PATCH", "/emails/1"),
]


@pytest.fixture
def client():
    app.dependency_overrides[get_groq_client] = lambda: object()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_groq_client, None)


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def fake_groq(client, messages, sleep=None):
    return json.dumps({"class": "unknown", "confidence": 90}), 10


def set_received(email_id, moment):
    with engine.begin() as connection:
        connection.execute(
            text("update emails set received_at = :moment where id = :id"),
            {"moment": moment, "id": email_id},
        )


def set_class(email_id, label):
    with engine.begin() as connection:
        connection.execute(
            text('update emails set "class" = :label where id = :id'),
            {"label": label, "id": email_id},
        )


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_missing_key_is_rejected(client, method, path):
    assert client.request(method, path).status_code == 401


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_wrong_key_is_rejected(client, method, path):
    response = client.request(method, path, headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


def test_process_returns_the_summary(client, headers, monkeypatch):
    monkeypatch.setattr(email_processing, "call_groq", fake_groq)
    email_id = make_email()
    response = client.post("/emails/process?limit=5", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "requested",
        "processed",
        "jobs_created",
        "jobs_duplicate",
        "classified",
        "auto_status_changed",
        "needs_review",
        "errored",
        "skipped_by_cap",
        "stopped_reason",
        "cap",
    }
    assert data["requested"] == 5
    assert data["processed"] == 1
    assert data["classified"] == 1
    assert data["stopped_reason"] is None
    assert data["cap"] == {"limit": 30, "used_before": 0, "remaining_after": 29}
    detail = client.get(f"/emails/{email_id}", headers=headers).json()
    assert detail["status"] == "processed"


def test_process_default_limit_is_ten(client, headers, monkeypatch):
    monkeypatch.setattr(email_processing, "call_groq", fake_groq)
    response = client.post("/emails/process", headers=headers)
    assert response.status_code == 200
    assert response.json()["requested"] == 10


@pytest.mark.parametrize("value", ["0", "51", "-1", "abc"])
def test_process_limit_is_validated(client, headers, value):
    response = client.post(f"/emails/process?limit={value}", headers=headers)
    assert response.status_code == 422


def test_process_returns_409_when_already_running(client, headers):
    lock = email_processing.acquire_lock()
    try:
        response = client.post("/emails/process", headers=headers)
    finally:
        email_processing.release_lock(lock)
    assert response.status_code == 409
    assert response.json()["detail"] == "Email processing is already running"


def test_list_never_returns_the_body(client, headers):
    make_email(kind="job_alert", body_html="<p>SECRET-BODY-TEXT</p>")
    response = client.get("/emails", headers=headers)
    assert response.status_code == 200
    assert "SECRET-BODY-TEXT" not in response.text
    assert "body_html" not in response.text
    item = response.json()["items"][0]
    assert set(item) == {
        "id",
        "kind",
        "status",
        "class",
        "received_at",
        "sender",
        "subject",
        "snippet",
        "application",
    }
    assert item["application"] is None


def test_detail_never_returns_the_body(client, headers):
    email_id = make_email(kind="job_alert", body_html="<p>SECRET-BODY-TEXT</p>")
    response = client.get(f"/emails/{email_id}", headers=headers)
    assert response.status_code == 200
    assert "SECRET-BODY-TEXT" not in response.text
    assert "body_html" not in response.text


def test_list_is_newest_first(client, headers):
    now = datetime.now(timezone.utc)
    oldest = make_email()
    newest = make_email()
    middle = make_email()
    set_received(oldest, now - timedelta(days=3))
    set_received(middle, now - timedelta(days=2))
    set_received(newest, now - timedelta(days=1))
    data = client.get("/emails", headers=headers).json()
    assert [item["id"] for item in data["items"]] == [newest, middle, oldest]
    assert data["total"] == 3


def test_equal_times_are_ordered_by_id_descending(client, headers):
    moment = datetime.now(timezone.utc) - timedelta(days=1)
    first = make_email()
    second = make_email()
    set_received(first, moment)
    set_received(second, moment)
    data = client.get("/emails", headers=headers).json()
    assert [item["id"] for item in data["items"]] == [second, first]


def test_pagination(client, headers):
    now = datetime.now(timezone.utc)
    ids = [make_email() for _ in range(3)]
    for number, email_id in enumerate(ids):
        set_received(email_id, now - timedelta(days=number))
    data = client.get("/emails?limit=2&offset=1", headers=headers).json()
    assert data["total"] == 3
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert [item["id"] for item in data["items"]] == [ids[1], ids[2]]


def test_filter_by_kind(client, headers):
    alert = make_email(kind="job_alert")
    make_email(kind="application")
    data = client.get("/emails?kind=job_alert", headers=headers).json()
    assert [item["id"] for item in data["items"]] == [alert]
    assert data["total"] == 1


def test_filter_by_status(client, headers):
    make_email(status="unprocessed")
    done = make_email(status="processed")
    data = client.get("/emails?status=processed", headers=headers).json()
    assert [item["id"] for item in data["items"]] == [done]


def test_filter_by_class(client, headers):
    first = make_email(status="processed")
    second = make_email(status="processed")
    make_email()
    set_class(first, "interview")
    set_class(second, "rejection")
    data = client.get("/emails?class=interview", headers=headers).json()
    assert [item["id"] for item in data["items"]] == [first]
    assert data["items"][0]["class"] == "interview"


def test_filter_by_linked(client, headers):
    application_id = make_application()
    linked = make_email(application_id=application_id)
    unlinked = make_email()
    only_linked = client.get("/emails?linked=true", headers=headers).json()
    only_unlinked = client.get("/emails?linked=false", headers=headers).json()
    assert [item["id"] for item in only_linked["items"]] == [linked]
    assert [item["id"] for item in only_unlinked["items"]] == [unlinked]


def test_filters_can_be_combined(client, headers):
    make_email(kind="job_alert", status="processed")
    wanted = make_email(kind="application", status="processed")
    make_email(kind="application", status="unprocessed")
    data = client.get("/emails?kind=application&status=processed", headers=headers).json()
    assert [item["id"] for item in data["items"]] == [wanted]


@pytest.mark.parametrize(
    "query",
    [
        "kind=other",
        "status=other",
        "class=hired",
        "class=unknown",
        "linked=maybe",
        "limit=0",
        "limit=201",
        "offset=-1",
    ],
)
def test_invalid_query_values_are_rejected(client, headers, query):
    assert client.get(f"/emails?{query}", headers=headers).status_code == 422


def test_linked_application_summary(client, headers):
    application_id = make_application("Example Corp", "interview", title="Support Agent")
    email_id = make_email(application_id=application_id)
    item = client.get(f"/emails/{email_id}", headers=headers).json()
    assert item["application"] == {
        "id": application_id,
        "status": "interview",
        "job_title": "Support Agent",
        "company": "Example Corp",
    }


def test_get_one_and_not_found(client, headers):
    email_id = make_email(sender="hr@example.com", subject="Hello", snippet="Hi")
    response = client.get(f"/emails/{email_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == email_id
    assert data["sender"] == "hr@example.com"
    assert data["subject"] == "Hello"
    assert data["snippet"] == "Hi"
    missing = client.get("/emails/999999", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Email not found"
    assert client.get("/emails/0", headers=headers).status_code == 422


def test_patch_links_an_email_without_changing_the_status(client, headers):
    application_id = make_application("Example Corp", "applied")
    email_id = make_email()
    response = client.patch(
        f"/emails/{email_id}", json={"application_id": application_id}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["application"]["id"] == application_id
    assert read_status(application_id) == "applied"
    assert read_events(application_id) == []


def test_patch_removes_the_link(client, headers):
    application_id = make_application()
    email_id = make_email(application_id=application_id)
    response = client.patch(
        f"/emails/{email_id}", json={"application_id": None}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["application"] is None
    detail = client.get(f"/emails/{email_id}", headers=headers).json()
    assert detail["application"] is None


def test_patch_job_alert_is_rejected(client, headers):
    application_id = make_application()
    email_id = make_email(kind="job_alert")
    response = client.patch(
        f"/emails/{email_id}", json={"application_id": application_id}, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Only application emails can be linked"


def test_patch_missing_application_is_404(client, headers):
    email_id = make_email()
    response = client.patch(
        f"/emails/{email_id}", json={"application_id": 999999}, headers=headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_patch_missing_email_is_404(client, headers):
    response = client.patch("/emails/999999", json={"application_id": None}, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Email not found"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"status": "processed"},
        {"application_id": 1, "subject": "x"},
        {"application_id": "1"},
        {"application_id": 0},
        {"application_id": 1.5},
    ],
)
def test_patch_rejects_bad_bodies(client, headers, body):
    email_id = make_email()
    response = client.patch(f"/emails/{email_id}", json=body, headers=headers)
    assert response.status_code == 422