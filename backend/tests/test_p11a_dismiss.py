import itertools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.main import app
from app.services import scheduler, scoring
from app.services.title_filter import apply_title_filter

BASE = "https://example.com/p11a-dismiss"
EXCLUDE_REGEX = (
    "senior|director|head of|principal|vice president|manager|architect|"
    "(?<![a-z])staff(?![a-z])|recruiter|sales|nurse|physician|"
    "(?<!non-)(?<!non )(?<!non)voice|call center|(?<![a-z])lead(?![a-z])"
)
INCLUDE_KEYWORDS = ["assistant", "data entry", "support", "admin", "junior", "entry", "automation"]
DISMISSED_CONFLICT = "This job is dismissed. Restore it first."
HAS_APPLICATION = "This job already has an application."

url_counter = itertools.count(1)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def create(client, headers, slug="job-1"):
    response = client.post(
        "/jobs",
        json={"source": "manual", "title": "Python Developer", "company": "Acme", "url": f"{BASE}/{slug}"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_raw_job(source="remoteok", title="Plumber", priority=0, status="new"):
    url = f"{BASE}/raw/{next(url_counter)}"
    with engine.begin() as connection:
        return connection.execute(
            text(
                "insert into jobs (source, title, company, url, url_normalized, priority, "
                "pipeline_status) values (:source, :title, 'Acme', :url, :url, :priority, :status) "
                "returning id"
            ),
            {"source": source, "title": title, "url": url, "priority": priority, "status": status},
        ).scalar_one()


def set_setting(key, value):
    import json

    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into settings (key, value) values (:key, cast(:value as jsonb)) "
                "on conflict (key) do update set value = excluded.value"
            ),
            {"key": key, "value": json.dumps(value)},
        )


def read_job(job_id):
    with engine.connect() as connection:
        return connection.execute(
            text("select dismissed_at, pipeline_status, opened_at from jobs where id = :id"),
            {"id": job_id},
        ).one()


def count_applications():
    with engine.connect() as connection:
        return connection.execute(text("select count(*) from applications")).scalar_one()


def listed_ids(client, headers, query):
    response = client.get(f"/jobs?{query}", headers=headers)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def queue_ids():
    with SessionLocal() as db:
        return [row["id"] for row in scoring.load_queue(db, 50)]


def has_work():
    with SessionLocal() as db:
        return scheduler.scoring_has_work(db)


@pytest.mark.parametrize("action", ["dismiss", "restore"])
def test_dismiss_and_restore_require_the_api_key(client, headers, action):
    job = create(client, headers)
    assert client.post(f"/jobs/{job['id']}/{action}").status_code == 401
    assert client.post(f"/jobs/{job['id']}/{action}", headers={"X-API-Key": "wrong"}).status_code == 401


def test_new_job_has_a_null_dismissed_at(client, headers):
    job = create(client, headers)
    assert job["dismissed_at"] is None
    assert client.get(f"/jobs/{job['id']}", headers=headers).json()["dismissed_at"] is None


def test_dismiss_sets_the_time_and_changes_nothing_else(client, headers):
    job = create(client, headers)
    client.post(f"/jobs/{job['id']}/open", headers=headers)
    before = read_job(job["id"])
    response = client.post(f"/jobs/{job['id']}/dismiss", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["dismissed_at"] is not None
    after = read_job(job["id"])
    assert after.dismissed_at is not None
    assert after.pipeline_status == before.pipeline_status == "new"
    assert after.opened_at == before.opened_at
    assert body["pipeline_status"] == "new"


def test_dismissing_twice_keeps_the_original_time(client, headers):
    job = create(client, headers)
    first = client.post(f"/jobs/{job['id']}/dismiss", headers=headers)
    second = client.post(f"/jobs/{job['id']}/dismiss", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["dismissed_at"] == first.json()["dismissed_at"]


def test_dismiss_and_restore_return_404_for_a_missing_job(client, headers):
    assert client.post("/jobs/999999/dismiss", headers=headers).status_code == 404
    assert client.post("/jobs/999999/restore", headers=headers).status_code == 404


def test_dismiss_returns_409_when_the_job_has_an_application(client, headers):
    job = create(client, headers)
    applied = client.post("/applications", json={"job_id": job["id"]}, headers=headers)
    assert applied.status_code == 201
    response = client.post(f"/jobs/{job['id']}/dismiss", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == HAS_APPLICATION
    assert read_job(job["id"]).dismissed_at is None


def test_restore_clears_the_time(client, headers):
    job = create(client, headers)
    client.post(f"/jobs/{job['id']}/dismiss", headers=headers)
    response = client.post(f"/jobs/{job['id']}/restore", headers=headers)
    assert response.status_code == 200
    assert response.json()["dismissed_at"] is None
    assert read_job(job["id"]).dismissed_at is None


def test_restoring_a_job_that_is_not_dismissed_changes_nothing(client, headers):
    job = create(client, headers)
    response = client.post(f"/jobs/{job['id']}/restore", headers=headers)
    assert response.status_code == 200
    assert response.json()["dismissed_at"] is None


def test_dismissed_filter_true_false_and_missing(client, headers):
    active = create(client, headers, "active")["id"]
    hidden = create(client, headers, "hidden")["id"]
    client.post(f"/jobs/{hidden}/dismiss", headers=headers)
    assert listed_ids(client, headers, "dismissed=true") == [hidden]
    assert listed_ids(client, headers, "dismissed=false") == [active]
    assert sorted(listed_ids(client, headers, "limit=50")) == sorted([active, hidden])


def test_awaiting_apply_excludes_dismissed_jobs(client, headers):
    job = create(client, headers)
    client.post(f"/jobs/{job['id']}/open", headers=headers)
    assert listed_ids(client, headers, "awaiting_apply=true") == [job["id"]]
    client.post(f"/jobs/{job['id']}/dismiss", headers=headers)
    assert listed_ids(client, headers, "awaiting_apply=true") == []
    client.post(f"/jobs/{job['id']}/restore", headers=headers)
    assert listed_ids(client, headers, "awaiting_apply=true") == [job["id"]]


def test_client_cannot_set_dismissed_at_on_create_or_update(client, headers):
    created = client.post(
        "/jobs",
        json={
            "source": "manual",
            "title": "Python Developer",
            "company": "Acme",
            "url": f"{BASE}/forbidden",
            "dismissed_at": "2026-11-07T00:00:00Z",
        },
        headers=headers,
    )
    assert created.status_code == 422
    job = create(client, headers)
    updated = client.patch(
        f"/jobs/{job['id']}", json={"dismissed_at": "2026-11-07T00:00:00Z"}, headers=headers
    )
    assert updated.status_code == 422
    assert read_job(job["id"]).dismissed_at is None


def test_applying_to_a_dismissed_job_returns_409(client, headers):
    job = create(client, headers)
    client.post(f"/jobs/{job['id']}/dismiss", headers=headers)
    response = client.post("/applications", json={"job_id": job["id"]}, headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == DISMISSED_CONFLICT
    assert count_applications() == 0
    client.post(f"/jobs/{job['id']}/restore", headers=headers)
    again = client.post("/applications", json={"job_id": job["id"]}, headers=headers)
    assert again.status_code == 201


def test_scoring_queue_skips_dismissed_jobs_until_restored(client, headers):
    job = create(client, headers)
    assert queue_ids() == [job["id"]]
    client.post(f"/jobs/{job['id']}/dismiss", headers=headers)
    assert queue_ids() == []
    assert read_job(job["id"]).pipeline_status == "new"
    client.post(f"/jobs/{job['id']}/restore", headers=headers)
    assert queue_ids() == [job["id"]]


def test_scheduler_sees_no_scoring_work_when_only_dismissed_jobs_remain(client, headers):
    job = create(client, headers)
    assert has_work() is True
    client.post(f"/jobs/{job['id']}/dismiss", headers=headers)
    assert has_work() is False
    client.post(f"/jobs/{job['id']}/restore", headers=headers)
    assert has_work() is True


def test_title_filter_leaves_dismissed_jobs_untouched(client, headers):
    set_setting("title_exclude_regex", EXCLUDE_REGEX)
    set_setting("title_include_keywords", INCLUDE_KEYWORDS)
    dismissed = add_raw_job(title="Plumber")
    active = add_raw_job(title="Plumber")
    with engine.begin() as connection:
        connection.execute(
            text("update jobs set dismissed_at = now() where id = :id"), {"id": dismissed}
        )
    with SessionLocal() as db:
        summary = apply_title_filter(db)
    assert summary["filtered_out"] == 1
    assert read_job(dismissed).pipeline_status == "new"
    assert read_job(active).pipeline_status == "filtered_out"