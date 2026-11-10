import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.main import app

BASE = "https://example.com/p12a-dash"
KEYS = {
    "total_applications",
    "interviews",
    "pending_follow_ups",
    "jobs_discovered",
    "recommended_jobs",
}


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def make_job(client, headers, slug):
    response = client.post(
        "/jobs",
        json={
            "source": "manual",
            "title": "Python Developer",
            "company": "Acme",
            "url": f"{BASE}/{slug}",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_score(job_id, score, scored_at=None, prompt_version="v1"):
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into job_scores "
                "(job_id, score, reason, red_flags, model, prompt_version, scored_at) "
                "values (:job_id, :score, 'r', cast(:flags as jsonb), "
                "'test-model', :pv, coalesce(:scored_at, now()))"
            ),
            {
                "job_id": job_id,
                "score": score,
                "flags": json.dumps([]),
                "pv": prompt_version,
                "scored_at": scored_at,
            },
        )


def set_pipeline_status(job_id, value):
    with engine.begin() as connection:
        connection.execute(
            text("update jobs set pipeline_status = :value where id = :id"),
            {"value": value, "id": job_id},
        )


def apply_to(client, headers, job_id):
    response = client.post("/applications", json={"job_id": job_id}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_follow_up(client, headers, application_id):
    response = client.post(
        "/follow-ups",
        json={"application_id": application_id, "title": "Check in"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def summary(client, headers):
    response = client.get("/dashboard/summary", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def recommended_total(client, headers):
    response = client.get(
        "/jobs?verdict=apply&dismissed=false&has_application=false&limit=1",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["total"]


def test_auth_required(client, headers):
    for bad_headers in ({}, {"X-API-Key": "wrong"}):
        response = client.get("/dashboard/summary", headers=bad_headers)
        assert response.status_code == 401


def test_empty_database_gives_zeros(client, headers):
    body = summary(client, headers)
    assert body == {key: 0 for key in KEYS}


def test_response_has_exactly_five_integer_fields(client, headers):
    body = summary(client, headers)
    assert set(body.keys()) == KEYS
    for value in body.values():
        assert isinstance(value, int)
        assert not isinstance(value, bool)


def test_counts_with_mixed_data(client, headers):
    dismissed = make_job(client, headers, "d-dismissed")
    filtered = make_job(client, headers, "d-filtered")
    applied = make_job(client, headers, "d-applied")
    recommended = make_job(client, headers, "d-recommended")
    maybe = make_job(client, headers, "d-maybe")
    dismissed_high = make_job(client, headers, "d-dismissed-high")

    client.post(f"/jobs/{dismissed}/dismiss", headers=headers)
    set_pipeline_status(filtered, "filtered_out")
    add_score(applied, 85)
    add_score(recommended, 80)
    add_score(maybe, 50)
    add_score(dismissed_high, 90)
    client.post(f"/jobs/{dismissed_high}/dismiss", headers=headers)

    application_id = apply_to(client, headers, applied)
    response = client.patch(
        f"/applications/{application_id}", json={"status": "interview"}, headers=headers
    )
    assert response.status_code == 200, response.text
    pending_id = add_follow_up(client, headers, application_id)
    done_id = add_follow_up(client, headers, application_id)
    response = client.patch(
        f"/follow-ups/{done_id}", json={"status": "completed"}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert pending_id != done_id

    body = summary(client, headers)
    assert body["total_applications"] == 1
    assert body["interviews"] == 1
    assert body["pending_follow_ups"] == 1
    assert body["jobs_discovered"] == 3
    assert body["recommended_jobs"] == 1


def test_interviews_follow_current_status(client, headers):
    first = make_job(client, headers, "i-1")
    second = make_job(client, headers, "i-2")
    first_app = apply_to(client, headers, first)
    second_app = apply_to(client, headers, second)
    client.patch(f"/applications/{first_app}", json={"status": "interview"}, headers=headers)
    client.patch(f"/applications/{second_app}", json={"status": "interview"}, headers=headers)
    assert summary(client, headers)["interviews"] == 2
    client.patch(f"/applications/{second_app}", json={"status": "offer"}, headers=headers)
    body = summary(client, headers)
    assert body["interviews"] == 1
    assert body["total_applications"] == 2


def test_recommended_uses_threshold_boundary(client, headers):
    at_threshold = make_job(client, headers, "t-70")
    below_threshold = make_job(client, headers, "t-69")
    add_score(at_threshold, 70)
    add_score(below_threshold, 69)
    assert summary(client, headers)["recommended_jobs"] == 1


def test_recommended_uses_latest_score(client, headers):
    job = make_job(client, headers, "latest-1")
    other = make_job(client, headers, "latest-2")
    add_score(job, 95, datetime(2026, 1, 1, tzinfo=timezone.utc), "v1")
    add_score(job, 10, datetime(2026, 1, 2, tzinfo=timezone.utc), "v2")
    add_score(other, 20, datetime(2026, 1, 1, tzinfo=timezone.utc), "v1")
    add_score(other, 88, datetime(2026, 1, 2, tzinfo=timezone.utc), "v2")
    assert summary(client, headers)["recommended_jobs"] == 1


def test_recommended_matches_jobs_list_total(client, headers):
    ids = [make_job(client, headers, f"match-{index}") for index in range(7)]
    add_score(ids[0], 95)
    add_score(ids[1], 70)
    add_score(ids[2], 40)
    add_score(ids[3], 99)
    add_score(ids[4], 99)
    add_score(ids[5], 80, datetime(2026, 1, 1, tzinfo=timezone.utc), "v1")
    add_score(ids[5], 20, datetime(2026, 1, 2, tzinfo=timezone.utc), "v2")
    client.post(f"/jobs/{ids[3]}/dismiss", headers=headers)
    apply_to(client, headers, ids[4])
    expected = recommended_total(client, headers)
    assert expected == 2
    assert summary(client, headers)["recommended_jobs"] == expected


def test_dismissing_and_restoring_changes_counts(client, headers):
    job = make_job(client, headers, "toggle-1")
    add_score(job, 90)
    before = summary(client, headers)
    assert before["jobs_discovered"] == 1
    assert before["recommended_jobs"] == 1
    client.post(f"/jobs/{job}/dismiss", headers=headers)
    during = summary(client, headers)
    assert during["jobs_discovered"] == 0
    assert during["recommended_jobs"] == 0
    client.post(f"/jobs/{job}/restore", headers=headers)
    assert summary(client, headers) == before


def test_summary_is_read_only(client, headers):
    response = client.post("/dashboard/summary", json={"interviews": 5}, headers=headers)
    assert response.status_code == 405
    assert summary(client, headers)["interviews"] == 0