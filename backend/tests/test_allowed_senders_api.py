import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

ENDPOINTS = [
    ("GET", "/allowed-senders"),
    ("POST", "/allowed-senders"),
    ("PATCH", "/allowed-senders/1"),
]


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def add(client, headers, sender="hr@example.com", kind="application"):
    return client.post(
        "/allowed-senders", json={"sender": sender, "kind": kind}, headers=headers
    )


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_missing_key_is_rejected(client, method, path):
    assert client.request(method, path).status_code == 401


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_wrong_key_is_rejected(client, method, path):
    response = client.request(method, path, headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


def test_list_is_empty_then_shows_added_senders_in_order(client, headers):
    assert client.get("/allowed-senders", headers=headers).json() == {"items": [], "total": 0}
    first = add(client, headers, "a@example.com").json()
    second = add(client, headers, "b@example.com", "job_alert").json()
    data = client.get("/allowed-senders", headers=headers).json()
    assert data["total"] == 2
    assert [item["id"] for item in data["items"]] == [first["id"], second["id"]]
    assert set(data["items"][0]) == {"id", "sender", "kind", "enabled"}


def test_add_cleans_and_lowercases_the_address(client, headers):
    response = add(client, headers, "  HR@Example.COM  ")
    assert response.status_code == 201
    data = response.json()
    assert data["sender"] == "hr@example.com"
    assert data["kind"] == "application"
    assert data["enabled"] is True


def test_duplicate_is_409(client, headers):
    assert add(client, headers, "hr@example.com").status_code == 201
    response = add(client, headers, "HR@example.com")
    assert response.status_code == 409
    assert response.json()["detail"] == "Allowed sender already exists"


def test_same_address_with_another_kind_is_allowed(client, headers):
    assert add(client, headers, "hr@example.com", "application").status_code == 201
    assert add(client, headers, "hr@example.com", "job_alert").status_code == 201


@pytest.mark.parametrize(
    "sender",
    [
        "",
        "   ",
        "example.com",
        "hr@",
        "@example.com",
        "hr@example",
        "hr @example.com",
        "hr@exa mple.com",
        "a@example.com OR b@example.com",
        "a@example.com b@example.com",
        "from:a@example.com",
        "{a@example.com}",
        "(a@example.com)",
        "-a@example.com",
        "a@example.com,b@example.com",
        "Name <a@example.com>",
        "a" * 250 + "@example.com",
    ],
)
def test_invalid_senders_are_rejected(client, headers, sender):
    assert add(client, headers, sender).status_code == 422


def test_invalid_kind_and_extra_fields_are_rejected(client, headers):
    assert add(client, headers, "hr@example.com", "other").status_code == 422
    response = client.post(
        "/allowed-senders",
        json={"sender": "hr@example.com", "kind": "application", "enabled": False},
        headers=headers,
    )
    assert response.status_code == 422
    assert client.post("/allowed-senders", json={}, headers=headers).status_code == 422
    response = client.post(
        "/allowed-senders", json={"sender": 5, "kind": "application"}, headers=headers
    )
    assert response.status_code == 422


def test_patch_changes_enabled_only(client, headers):
    sender_id = add(client, headers).json()["id"]
    off = client.patch(f"/allowed-senders/{sender_id}", json={"enabled": False}, headers=headers)
    assert off.status_code == 200
    assert off.json()["enabled"] is False
    assert off.json()["sender"] == "hr@example.com"
    on = client.patch(f"/allowed-senders/{sender_id}", json={"enabled": True}, headers=headers)
    assert on.json()["enabled"] is True


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"enabled": "false"},
        {"enabled": 0},
        {"enabled": None},
        {"sender": "other@example.com"},
        {"kind": "job_alert"},
        {"enabled": False, "sender": "other@example.com"},
    ],
)
def test_patch_rejects_other_changes(client, headers, body):
    sender_id = add(client, headers).json()["id"]
    response = client.patch(f"/allowed-senders/{sender_id}", json=body, headers=headers)
    assert response.status_code == 422
    unchanged = client.get("/allowed-senders", headers=headers).json()["items"][0]
    assert unchanged["sender"] == "hr@example.com"
    assert unchanged["kind"] == "application"
    assert unchanged["enabled"] is True


def test_patch_missing_sender_is_404(client, headers):
    response = client.patch("/allowed-senders/999999", json={"enabled": False}, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Allowed sender not found"
    assert client.patch("/allowed-senders/0", json={"enabled": False}, headers=headers).status_code == 422


def test_linkedin_style_entry_can_only_be_toggled(client, headers):
    sender_id = add(client, headers, "jobs-noreply@linkedin.com", "job_alert").json()["id"]
    changed = client.patch(
        f"/allowed-senders/{sender_id}", json={"sender": "x@example.com"}, headers=headers
    )
    assert changed.status_code == 422
    toggled = client.patch(
        f"/allowed-senders/{sender_id}", json={"enabled": False}, headers=headers
    )
    assert toggled.status_code == 200
    assert toggled.json()["sender"] == "jobs-noreply@linkedin.com"


def test_delete_is_not_available(client, headers):
    sender_id = add(client, headers).json()["id"]
    response = client.delete(f"/allowed-senders/{sender_id}", headers=headers)
    assert response.status_code == 405
    assert client.get("/allowed-senders", headers=headers).json()["total"] == 1