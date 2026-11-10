import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from app.config import get_settings
from app.db import engine
from app.main import app

BASE = "https://example.com/p12a-test"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def make_job(client, headers, slug, **overrides):
    payload = {
        "source": "manual",
        "title": "Python Developer",
        "company": "Acme",
        "url": f"{BASE}/{slug}",
    }
    payload.update(overrides)
    response = client.post("/jobs", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def add_score(job_id, score, reason=None, red_flags=None, scored_at=None, prompt_version="v1"):
    flags = None if red_flags is None else json.dumps(red_flags)
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into job_scores "
                "(job_id, score, reason, red_flags, model, prompt_version, scored_at) "
                "values (:job_id, :score, :reason, cast(:flags as jsonb), "
                "'test-model', :pv, coalesce(:scored_at, now()))"
            ),
            {
                "job_id": job_id,
                "score": score,
                "reason": reason,
                "flags": flags,
                "pv": prompt_version,
                "scored_at": scored_at,
            },
        )


def set_job_column(job_id, column, value):
    with engine.begin() as connection:
        connection.execute(
            text(f"update jobs set {column} = :value where id = :id"),
            {"value": value, "id": job_id},
        )


def apply_to(client, headers, job_id):
    response = client.post("/applications", json={"job_id": job_id}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def listed(client, headers, query=""):
    response = client.get(f"/jobs?{query}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def listed_ids(client, headers, query=""):
    return [item["id"] for item in listed(client, headers, query)["items"]]


def count_statements(client, headers, path):
    statements = []

    def listener(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", listener)
    try:
        response = client.get(path, headers=headers)
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    assert response.status_code == 200, response.text
    return len(statements)


def test_new_fields_are_null_without_score_or_application(client, headers):
    created = make_job(client, headers, "null-1")
    for body in (
        created,
        client.get(f"/jobs/{created['id']}", headers=headers).json(),
        listed(client, headers)["items"][0],
    ):
        assert body["reason"] is None
        assert body["red_flags"] is None
        assert body["application_id"] is None


def test_fields_come_from_latest_score(client, headers):
    job = make_job(client, headers, "latest-1")
    now = datetime.now(timezone.utc)
    add_score(job["id"], 20, "old reason", ["old flag"], now - timedelta(hours=1), "v1")
    add_score(job["id"], 80, "new reason", ["new flag", "second flag"], now, "v2")
    single = client.get(f"/jobs/{job['id']}", headers=headers).json()
    from_list = listed(client, headers)["items"][0]
    for body in (single, from_list):
        assert body["score"] == 80
        assert body["reason"] == "new reason"
        assert body["red_flags"] == ["new flag", "second flag"]


def test_latest_score_tie_breaks_by_highest_id(client, headers):
    job = make_job(client, headers, "tie-1")
    same_moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
    add_score(job["id"], 30, "first", ["a"], same_moment, "v1")
    add_score(job["id"], 60, "second", ["b"], same_moment, "v2")
    single = client.get(f"/jobs/{job['id']}", headers=headers).json()
    from_list = listed(client, headers)["items"][0]
    for body in (single, from_list):
        assert body["reason"] == "second"
        assert body["red_flags"] == ["b"]


def test_empty_red_flags_list_is_kept(client, headers):
    job = make_job(client, headers, "flags-1")
    add_score(job["id"], 55, "fine", [])
    body = client.get(f"/jobs/{job['id']}", headers=headers).json()
    assert body["red_flags"] == []
    assert body["reason"] == "fine"


def test_score_without_reason_or_flags_gives_nulls(client, headers):
    job = make_job(client, headers, "bare-1")
    add_score(job["id"], 55)
    body = client.get(f"/jobs/{job['id']}", headers=headers).json()
    assert body["score"] == 55
    assert body["reason"] is None
    assert body["red_flags"] is None


def test_application_id_and_same_shape_on_all_job_endpoints(client, headers):
    job = make_job(client, headers, "app-1")
    add_score(job["id"], 75, "good", ["remote only"])
    application = apply_to(client, headers, job["id"])
    job_id = job["id"]
    bodies = [
        client.get(f"/jobs/{job_id}", headers=headers).json(),
        listed(client, headers)["items"][0],
        client.patch(f"/jobs/{job_id}", json={"title": "Renamed"}, headers=headers).json(),
        client.post(f"/jobs/{job_id}/open", headers=headers).json(),
        client.post(f"/jobs/{job_id}/restore", headers=headers).json(),
    ]
    keys = set(bodies[0].keys())
    assert {"reason", "red_flags", "application_id"} <= keys
    for body in bodies:
        assert set(body.keys()) == keys
        assert body["application_id"] == application["id"]
        assert body["reason"] == "good"
        assert body["red_flags"] == ["remote only"]
        assert body["score"] == 75


def test_dismiss_endpoint_has_same_shape(client, headers):
    first = make_job(client, headers, "shape-1")
    second = make_job(client, headers, "shape-2")
    add_score(second["id"], 65, "ok", ["x"])
    dismissed = client.post(f"/jobs/{second['id']}/dismiss", headers=headers).json()
    reference = client.get(f"/jobs/{first['id']}", headers=headers).json()
    assert set(dismissed.keys()) == set(reference.keys())
    assert dismissed["reason"] == "ok"
    assert dismissed["red_flags"] == ["x"]
    assert dismissed["application_id"] is None


def test_list_query_count_does_not_grow_with_rows(client, headers):
    job = make_job(client, headers, "n1-1")
    add_score(job["id"], 50, "r", ["f"])
    one_row = count_statements(client, headers, "/jobs")
    for index in range(2, 7):
        extra = make_job(client, headers, f"n1-{index}")
        add_score(extra["id"], 50 + index, "r", ["f"])
        apply_to(client, headers, extra["id"])
    many_rows = count_statements(client, headers, "/jobs")
    assert many_rows == one_row


def test_has_application_filter(client, headers):
    with_app = make_job(client, headers, "has-1")
    without_app = make_job(client, headers, "has-2")
    apply_to(client, headers, with_app["id"])

    only_with = listed(client, headers, "has_application=true")
    only_without = listed(client, headers, "has_application=false")
    everything = listed(client, headers)

    assert [item["id"] for item in only_with["items"]] == [with_app["id"]]
    assert only_with["total"] == 1
    assert [item["id"] for item in only_without["items"]] == [without_app["id"]]
    assert only_without["total"] == 1
    assert everything["total"] == 2


def test_has_application_works_with_other_filters(client, headers):
    first = make_job(client, headers, "combo-1")
    second = make_job(client, headers, "combo-2")
    third = make_job(client, headers, "combo-3")
    for job in (first, second, third):
        add_score(job["id"], 90)
    apply_to(client, headers, first["id"])
    client.post(f"/jobs/{third['id']}/dismiss", headers=headers)

    result = listed(
        client, headers, "verdict=apply&dismissed=false&has_application=false"
    )
    assert [item["id"] for item in result["items"]] == [second["id"]]
    assert result["total"] == 1


def test_has_application_total_follows_pagination(client, headers):
    for index in range(3):
        job = make_job(client, headers, f"page-{index}")
        if index < 2:
            apply_to(client, headers, job["id"])
    page = listed(client, headers, "has_application=true&limit=1")
    assert len(page["items"]) == 1
    assert page["total"] == 2


@pytest.mark.parametrize("value", ["maybe", "2", "", "yes-please"])
def test_has_application_invalid_value_is_422(client, headers, value):
    response = client.get(f"/jobs?has_application={value}", headers=headers)
    assert response.status_code == 422


def build_sort_set(client, headers):
    a = make_job(client, headers, "sort-a")
    b = make_job(client, headers, "sort-b")
    c = make_job(client, headers, "sort-c")
    d = make_job(client, headers, "sort-d")
    add_score(a["id"], 90)
    add_score(b["id"], 50)
    add_score(d["id"], 90)
    set_job_column(a["id"], "created_at", datetime(2026, 1, 2, tzinfo=timezone.utc))
    set_job_column(b["id"], "created_at", datetime(2026, 1, 3, tzinfo=timezone.utc))
    set_job_column(c["id"], "created_at", datetime(2026, 1, 4, tzinfo=timezone.utc))
    set_job_column(d["id"], "created_at", datetime(2026, 1, 1, tzinfo=timezone.utc))
    return a["id"], b["id"], c["id"], d["id"]


def test_sort_score_desc_orders_with_nulls_last(client, headers):
    a, b, c, d = build_sort_set(client, headers)
    assert listed_ids(client, headers, "sort=score_desc") == [a, d, b, c]


def test_sort_score_desc_tie_breaks_by_id_when_created_at_is_equal(client, headers):
    first = make_job(client, headers, "tb-1")
    second = make_job(client, headers, "tb-2")
    same_moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for job in (first, second):
        add_score(job["id"], 70)
        set_job_column(job["id"], "created_at", same_moment)
    assert listed_ids(client, headers, "sort=score_desc") == [second["id"], first["id"]]


def test_sort_score_desc_uses_latest_score(client, headers):
    low_now = make_job(client, headers, "latest-sort-1")
    high_now = make_job(client, headers, "latest-sort-2")
    now = datetime.now(timezone.utc)
    add_score(low_now["id"], 95, scored_at=now - timedelta(hours=2), prompt_version="v1")
    add_score(low_now["id"], 10, scored_at=now, prompt_version="v2")
    add_score(high_now["id"], 60)
    assert listed_ids(client, headers, "sort=score_desc") == [high_now["id"], low_now["id"]]


def test_default_sort_is_unchanged(client, headers):
    a, b, c, d = build_sort_set(client, headers)
    set_job_column(d, "priority", 5)
    assert listed_ids(client, headers) == [d, c, b, a]
    assert listed_ids(client, headers, "sort=default") == [d, c, b, a]
    assert listed_ids(client, headers, "sort=score_desc") == [a, d, b, c]


def test_sort_score_desc_works_with_pagination(client, headers):
    a, b, c, d = build_sort_set(client, headers)
    first_page = listed_ids(client, headers, "sort=score_desc&limit=2")
    second_page = listed_ids(client, headers, "sort=score_desc&limit=2&offset=2")
    assert first_page + second_page == [a, d, b, c]


@pytest.mark.parametrize("value", ["newest", "score_asc", "SCORE_DESC", ""])
def test_sort_invalid_value_is_422(client, headers, value):
    response = client.get(f"/jobs?sort={value}", headers=headers)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [("reason", "x"), ("red_flags", ["x"]), ("application_id", 1)],
)
def test_client_cannot_set_new_fields_on_create(client, headers, field, value):
    payload = {
        "source": "manual",
        "title": "Python Developer",
        "company": "Acme",
        "url": f"{BASE}/forbidden-{field}",
        field: value,
    }
    response = client.post("/jobs", json=payload, headers=headers)
    assert response.status_code == 422
    assert listed(client, headers)["total"] == 0


@pytest.mark.parametrize(
    "field,value",
    [("reason", "x"), ("red_flags", ["x"]), ("application_id", 1)],
)
def test_client_cannot_set_new_fields_on_update(client, headers, field, value):
    job = make_job(client, headers, f"patch-{field}")
    response = client.patch(f"/jobs/{job['id']}", json={field: value}, headers=headers)
    assert response.status_code == 422
    body = client.get(f"/jobs/{job['id']}", headers=headers).json()
    assert body[field] is None


def test_datetime_fields_use_utc_with_z_suffix(client, headers):
    job = make_job(client, headers, "dt-1")
    body = client.get(f"/jobs/{job['id']}", headers=headers).json()
    assert body["created_at"].endswith("Z")
    parsed = datetime.fromisoformat(body["created_at"])
    assert parsed.utcoffset() == timedelta(0)