from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.main import app
from app.services import applications as application_service

BASE = "https://example.com/p8a-test"
STATUSES = [
    "applied",
    "under_review",
    "assessment",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
]


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def make_job(client, headers, slug="job-1", **overrides):
    payload = {
        "source": "manual",
        "title": "Python Developer",
        "company": "Acme",
        "url": f"{BASE}/{slug}",
    }
    payload.update(overrides)
    response = client.post("/jobs", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def apply_to(client, headers, job_id, **extra):
    response = client.post(
        "/applications", json={"job_id": job_id, **extra}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def count_rows(table):
    with engine.connect() as connection:
        return connection.execute(text(f"select count(*) from {table}")).scalar_one()


def db_status(application_id):
    with engine.connect() as connection:
        return connection.execute(
            text("select status from applications where id = :id"),
            {"id": application_id},
        ).scalar_one()


def set_job_column(job_id, column, value):
    with engine.begin() as connection:
        connection.execute(
            text(f"update jobs set {column} = :value where id = :id"),
            {"value": value, "id": job_id},
        )


def ids(response):
    return [item["id"] for item in response.json()["items"]]


def boom(**kwargs):
    raise RuntimeError("event failed")


def test_auth_required_on_every_endpoint(client, headers):
    job_id = make_job(client, headers)
    application = apply_to(client, headers, job_id)
    calls = [
        ("post", "/applications", {"job_id": job_id}),
        ("get", "/applications", None),
        ("get", f"/applications/{application['id']}", None),
        ("patch", f"/applications/{application['id']}", {"notes": "x"}),
        ("post", f"/jobs/{job_id}/open", None),
        ("get", "/jobs?awaiting_apply=true", None),
    ]
    for method, path, body in calls:
        kwargs = {"json": body} if body is not None else {}
        assert client.request(method, path, **kwargs).status_code == 401
        wrong = client.request(method, path, headers={"X-API-Key": "wrong"}, **kwargs)
        assert wrong.status_code == 401


def test_create_application_success_with_first_event(client, headers):
    job_id = make_job(client, headers)
    response = client.post(
        "/applications",
        json={"job_id": job_id, "notes": "Applied via site"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["job_id"] == job_id
    assert body["status"] == "applied"
    assert body["notes"] == "Applied via site"
    applied_at = datetime.fromisoformat(body["applied_at"])
    assert abs(datetime.now(timezone.utc) - applied_at) < timedelta(seconds=60)
    assert body["job"] == {
        "id": job_id,
        "title": "Python Developer",
        "company": "Acme",
        "url": f"{BASE}/job-1",
        "source": "manual",
    }
    detail = client.get(f"/applications/{body['id']}", headers=headers).json()
    assert len(detail["events"]) == 1
    event = detail["events"][0]
    assert event["from_status"] is None
    assert event["to_status"] == "applied"
    assert event["changed_at"]
    assert count_rows("application_events") == 1


def test_create_uses_given_applied_at(client, headers):
    job_id = make_job(client, headers)
    body = apply_to(client, headers, job_id, applied_at="2026-01-15T09:30:00+08:00")
    parsed = datetime.fromisoformat(body["applied_at"])
    assert parsed == datetime(2026, 1, 15, 1, 30, tzinfo=timezone.utc)


def test_create_rejects_applied_at_more_than_one_day_ahead(client, headers):
    job_id = make_job(client, headers)
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    response = client.post(
        "/applications", json={"job_id": job_id, "applied_at": future}, headers=headers
    )
    assert response.status_code == 422
    assert count_rows("applications") == 0


def test_create_allows_applied_at_within_one_day_ahead(client, headers):
    job_id = make_job(client, headers)
    soon = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
    apply_to(client, headers, job_id, applied_at=soon)


def test_create_rejects_applied_at_without_timezone(client, headers):
    job_id = make_job(client, headers)
    response = client.post(
        "/applications",
        json={"job_id": job_id, "applied_at": "2026-01-15T09:30:00"},
        headers=headers,
    )
    assert response.status_code == 422


def test_create_duplicate_returns_409_with_existing_id(client, headers):
    job_id = make_job(client, headers)
    first = apply_to(client, headers, job_id)
    response = client.post("/applications", json={"job_id": job_id}, headers=headers)
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Application already exists for this job",
        "existing_id": first["id"],
    }
    assert count_rows("applications") == 1
    assert count_rows("application_events") == 1


def test_create_for_missing_job_is_404(client, headers):
    response = client.post("/applications", json={"job_id": 999999}, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"
    assert count_rows("applications") == 0


def test_create_notes_too_long_is_422(client, headers):
    job_id = make_job(client, headers)
    response = client.post(
        "/applications",
        json={"job_id": job_id, "notes": "x" * 2001},
        headers=headers,
    )
    assert response.status_code == 422


def test_create_notes_at_limit_is_accepted(client, headers):
    job_id = make_job(client, headers)
    body = apply_to(client, headers, job_id, notes="x" * 2000)
    assert len(body["notes"]) == 2000


@pytest.mark.parametrize(
    "body",
    [
        {"job_id": 1, "status": "interview"},
        {"job_id": 1, "id": 5},
        {"notes": "no job"},
        {"job_id": "1"},
        {"job_id": 0},
    ],
)
def test_create_invalid_body_is_422(client, headers, body):
    make_job(client, headers)
    response = client.post("/applications", json=body, headers=headers)
    assert response.status_code == 422


def test_create_for_filtered_out_job_is_allowed(client, headers):
    job_id = make_job(client, headers)
    set_job_column(job_id, "pipeline_status", "filtered_out")
    body = apply_to(client, headers, job_id)
    assert body["status"] == "applied"


def test_create_rolls_back_when_event_fails(client, headers, monkeypatch):
    job_id = make_job(client, headers)
    monkeypatch.setattr(application_service, "ApplicationEvent", boom)
    with pytest.raises(RuntimeError):
        client.post("/applications", json={"job_id": job_id}, headers=headers)
    assert count_rows("applications") == 0
    assert count_rows("application_events") == 0


def test_list_is_empty_at_first(client, headers):
    response = client.get("/applications", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_orders_newest_first_and_breaks_ties_by_id(client, headers):
    a = apply_to(
        client, headers, make_job(client, headers, "a"), applied_at="2026-03-01T00:00:00+00:00"
    )
    b = apply_to(
        client, headers, make_job(client, headers, "b"), applied_at="2026-05-01T00:00:00+00:00"
    )
    c = apply_to(
        client, headers, make_job(client, headers, "c"), applied_at="2026-05-01T00:00:00+00:00"
    )
    response = client.get("/applications", headers=headers)
    assert ids(response) == [c["id"], b["id"], a["id"]]


def test_list_filters_by_status(client, headers):
    first = apply_to(client, headers, make_job(client, headers, "a"))
    apply_to(client, headers, make_job(client, headers, "b"))
    client.patch(
        f"/applications/{first['id']}", json={"status": "interview"}, headers=headers
    )
    response = client.get("/applications", params={"status": "interview"}, headers=headers)
    assert ids(response) == [first["id"]]
    assert response.json()["total"] == 1
    bad = client.get("/applications", params={"status": "hired"}, headers=headers)
    assert bad.status_code == 422


def test_list_filters_by_job_id(client, headers):
    job_a = make_job(client, headers, "a")
    first = apply_to(client, headers, job_a)
    apply_to(client, headers, make_job(client, headers, "b"))
    response = client.get("/applications", params={"job_id": job_a}, headers=headers)
    assert ids(response) == [first["id"]]


def test_list_search_escapes_like_wildcards(client, headers):
    percent = apply_to(
        client,
        headers,
        make_job(client, headers, "p", title="100% Remote Role", company="Alpha"),
    )
    apply_to(
        client, headers, make_job(client, headers, "q", title="Plain Role", company="Beta")
    )
    underscore = apply_to(
        client,
        headers,
        make_job(client, headers, "r", title="snake_case Role", company="Gamma"),
    )
    apply_to(
        client,
        headers,
        make_job(client, headers, "s", title="snakeXcase Role", company="Delta"),
    )

    def search(value):
        return client.get("/applications", params={"q": value}, headers=headers)

    assert ids(search("%")) == [percent["id"]]
    assert ids(search("_")) == [underscore["id"]]
    assert ids(search("snake_case")) == [underscore["id"]]
    assert ids(search("ALPHA")) == [percent["id"]]
    assert search("role").json()["total"] == 4
    assert client.get("/applications", params={"q": "x" * 201}, headers=headers).status_code == 422


def test_list_pagination(client, headers):
    created = [
        apply_to(
            client,
            headers,
            make_job(client, headers, f"j{index}"),
            applied_at=f"2026-0{index + 1}-01T00:00:00+00:00",
        )
        for index in range(3)
    ]
    newest_first = [item["id"] for item in reversed(created)]
    page_one = client.get("/applications", params={"limit": 2}, headers=headers).json()
    assert [item["id"] for item in page_one["items"]] == newest_first[:2]
    assert page_one["total"] == 3
    assert page_one["limit"] == 2
    assert page_one["offset"] == 0
    page_two = client.get(
        "/applications", params={"limit": 2, "offset": 2}, headers=headers
    ).json()
    assert [item["id"] for item in page_two["items"]] == newest_first[2:]
    for params in ({"limit": 0}, {"limit": 201}, {"offset": -1}):
        assert client.get("/applications", params=params, headers=headers).status_code == 422


def test_list_items_include_job_summary(client, headers):
    job_id = make_job(client, headers)
    apply_to(client, headers, job_id)
    item = client.get("/applications", headers=headers).json()["items"][0]
    assert set(item["job"]) == {"id", "title", "company", "url", "source"}
    assert item["job"]["id"] == job_id


def test_get_one_returns_events_oldest_first(client, headers):
    application = apply_to(client, headers, make_job(client, headers))
    path = f"/applications/{application['id']}"
    client.patch(path, json={"status": "interview"}, headers=headers)
    client.patch(path, json={"status": "offer"}, headers=headers)
    events = client.get(path, headers=headers).json()["events"]
    assert [(e["from_status"], e["to_status"]) for e in events] == [
        (None, "applied"),
        ("applied", "interview"),
        ("interview", "offer"),
    ]
    times = [e["changed_at"] for e in events]
    assert times == sorted(times)


def test_get_one_missing_is_404(client, headers):
    response = client.get("/applications/999999", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"
    assert client.get("/applications/0", headers=headers).status_code == 422


@pytest.mark.parametrize("target", STATUSES)
def test_patch_every_status(client, headers, target):
    application = apply_to(client, headers, make_job(client, headers))
    response = client.patch(
        f"/applications/{application['id']}", json={"status": target}, headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == target
    assert db_status(application["id"]) == target
    if target == "applied":
        assert len(body["events"]) == 1
    else:
        assert len(body["events"]) == 2
        assert body["events"][-1]["from_status"] == "applied"
        assert body["events"][-1]["to_status"] == target


def test_patch_same_status_creates_no_event_but_updates_notes(client, headers):
    application = apply_to(client, headers, make_job(client, headers))
    response = client.patch(
        f"/applications/{application['id']}",
        json={"status": "applied", "notes": "Updated"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["notes"] == "Updated"
    assert count_rows("application_events") == 1


def test_patch_notes_only(client, headers):
    application = apply_to(client, headers, make_job(client, headers))
    response = client.patch(
        f"/applications/{application['id']}", json={"notes": "Call on Monday"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["notes"] == "Call on Monday"
    assert response.json()["status"] == "applied"
    assert count_rows("application_events") == 1


def test_patch_null_notes_clears_them(client, headers):
    application = apply_to(client, headers, make_job(client, headers), notes="Old note")
    response = client.patch(
        f"/applications/{application['id']}", json={"notes": None}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["notes"] is None


def test_patch_status_and_notes_together(client, headers):
    application = apply_to(client, headers, make_job(client, headers))
    response = client.patch(
        f"/applications/{application['id']}",
        json={"status": "assessment", "notes": "Take-home test"},
        headers=headers,
    )
    body = response.json()
    assert body["status"] == "assessment"
    assert body["notes"] == "Take-home test"
    assert len(body["events"]) == 2


@pytest.mark.parametrize(
    "body",
    [
        {"job_id": 5},
        {"id": 1},
        {"applied_at": "2026-01-01T00:00:00+00:00"},
        {"created_at": "2026-01-01T00:00:00+00:00"},
        {"status": "offer", "job_id": 5},
        {},
        {"status": None},
        {"status": "hired"},
        {"notes": "x" * 2001},
    ],
)
def test_patch_invalid_body_is_422_and_changes_nothing(client, headers, body):
    application = apply_to(client, headers, make_job(client, headers))
    response = client.patch(
        f"/applications/{application['id']}", json=body, headers=headers
    )
    assert response.status_code == 422
    assert db_status(application["id"]) == "applied"
    assert count_rows("application_events") == 1


def test_patch_missing_application_is_404(client, headers):
    response = client.patch("/applications/999999", json={"status": "offer"}, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_patch_rolls_back_status_when_event_fails(client, headers, monkeypatch):
    application = apply_to(client, headers, make_job(client, headers))
    monkeypatch.setattr(application_service, "ApplicationEvent", boom)
    with pytest.raises(RuntimeError):
        client.patch(
            f"/applications/{application['id']}",
            json={"status": "interview", "notes": "Should not be saved"},
            headers=headers,
        )
    assert db_status(application["id"]) == "applied"
    with engine.connect() as connection:
        notes = connection.execute(
            text("select notes from applications where id = :id"),
            {"id": application["id"]},
        ).scalar_one()
    assert notes is None
    assert count_rows("application_events") == 1


def test_open_sets_opened_at_once(client, headers):
    job_id = make_job(client, headers)
    first = client.post(f"/jobs/{job_id}/open", headers=headers)
    assert first.status_code == 200, first.text
    opened_at = first.json()["opened_at"]
    assert opened_at is not None
    assert first.json()["id"] == job_id
    second = client.post(f"/jobs/{job_id}/open", headers=headers)
    assert second.status_code == 200
    assert second.json()["opened_at"] == opened_at


def test_open_missing_job_is_404(client, headers):
    response = client.post("/jobs/999999/open", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"
    assert client.post("/jobs/0/open", headers=headers).status_code == 422


def test_open_creates_no_application_and_keeps_pipeline_status(client, headers):
    job_id = make_job(client, headers)
    set_job_column(job_id, "pipeline_status", "filtered_out")
    response = client.post(f"/jobs/{job_id}/open", headers=headers)
    assert response.json()["pipeline_status"] == "filtered_out"
    assert count_rows("applications") == 0
    other = make_job(client, headers, "other")
    after = client.post(f"/jobs/{other}/open", headers=headers)
    assert after.json()["pipeline_status"] == "new"
    assert count_rows("applications") == 0


def test_awaiting_apply_filter(client, headers):
    opened_only = make_job(client, headers, "opened-only")
    not_opened = make_job(client, headers, "not-opened")
    opened_and_applied = make_job(client, headers, "opened-applied")
    client.post(f"/jobs/{opened_only}/open", headers=headers)
    client.post(f"/jobs/{opened_and_applied}/open", headers=headers)
    apply_to(client, headers, opened_and_applied)

    def listing(**params):
        response = client.get("/jobs", params=params, headers=headers)
        assert response.status_code == 200, response.text
        return sorted(ids(response))

    assert listing(awaiting_apply="true") == [opened_only]
    assert listing(awaiting_apply="false") == sorted([not_opened, opened_and_applied])
    assert listing() == sorted([opened_only, not_opened, opened_and_applied])

    apply_to(client, headers, opened_only)
    assert listing(awaiting_apply="true") == []


def test_awaiting_apply_invalid_value_is_422(client, headers):
    response = client.get("/jobs", params={"awaiting_apply": "maybe"}, headers=headers)
    assert response.status_code == 422