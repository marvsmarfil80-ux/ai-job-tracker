import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.main import app

BASE = "https://example.com/p5a-test"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def make_payload(slug="job-1", **overrides):
    payload = {
        "source": "manual",
        "title": "Python Developer",
        "company": "Acme",
        "url": f"{BASE}/{slug}",
    }
    payload.update(overrides)
    return payload


def create(client, headers, slug="job-1", **overrides):
    response = client.post("/jobs", json=make_payload(slug, **overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def add_score(job_id, score, scored_at="now()", prompt_version="v1"):
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into job_scores (job_id, score, model, prompt_version, scored_at) "
                f"values (:job_id, :score, 'test-model', :pv, {scored_at})"
            ),
            {"job_id": job_id, "score": score, "pv": prompt_version},
        )


def set_job_column(job_id, column, value):
    with engine.begin() as connection:
        connection.execute(
            text(f"update jobs set {column} = :value where id = :id"),
            {"value": value, "id": job_id},
        )


def count_jobs():
    with engine.connect() as connection:
        return connection.execute(text("select count(*) from jobs")).scalar_one()


def test_auth_required_on_every_endpoint(client, headers):
    job = create(client, headers)
    calls = [
        ("post", "/jobs", make_payload("auth-1")),
        ("get", "/jobs", None),
        ("get", f"/jobs/{job['id']}", None),
        ("patch", f"/jobs/{job['id']}", {"title": "New"}),
    ]
    for method, path, body in calls:
        for bad_headers in ({}, {"X-API-Key": "wrong"}):
            response = getattr(client, method)(path, headers=bad_headers, **({"json": body} if body else {}))
            assert response.status_code == 401, (method, path)
    assert count_jobs() == 1


def test_create_success(client, headers):
    job = create(client, headers, location="Manila", work_mode="remote")
    assert job["pipeline_status"] == "new"
    assert job["priority"] == 1
    assert job["source"] == "manual"
    assert job["score"] is None
    assert job["verdict"] is None
    assert job["url_normalized"] == f"{BASE}/job-1"
    assert job["work_mode"] == "remote"


def test_create_extension_source_has_high_priority(client, headers):
    job = create(client, headers, "ext-1", source="extension")
    assert job["priority"] == 1


def test_duplicate_returns_409_with_existing_id(client, headers):
    first = create(client, headers)
    response = client.post("/jobs", json=make_payload(), headers=headers)
    assert response.status_code == 409
    assert response.json() == {"detail": "Job already exists", "existing_id": first["id"]}
    assert count_jobs() == 1


def test_duplicate_with_different_tracking_params(client, headers):
    first = create(client, headers)
    other = make_payload(url="HTTPS://EXAMPLE.COM/p5a-test/job-1/?utm_source=x&fbclid=y#top")
    response = client.post("/jobs", json=other, headers=headers)
    assert response.status_code == 409
    assert response.json()["existing_id"] == first["id"]
    assert count_jobs() == 1


@pytest.mark.parametrize("source", ["weworkremotely", "remoteok", "remotive", "linkedin_email", "banana"])
def test_create_rejects_other_sources(client, headers, source):
    response = client.post("/jobs", json=make_payload(source=source), headers=headers)
    assert response.status_code == 422
    assert count_jobs() == 0


@pytest.mark.parametrize("url", ["ftp://example.com/p5a-test/a", "javascript:alert(1)", "example.com/p5a-test/a", "https://"])
def test_create_rejects_bad_urls(client, headers, url):
    response = client.post("/jobs", json=make_payload(url=url), headers=headers)
    assert response.status_code == 422


def test_create_rejects_long_title_and_company(client, headers):
    assert client.post("/jobs", json=make_payload(title="x" * 201), headers=headers).status_code == 422
    assert client.post("/jobs", json=make_payload(company="x" * 201), headers=headers).status_code == 422
    assert client.post("/jobs", json=make_payload("ok-title", title="x" * 200), headers=headers).status_code == 201


def test_create_rejects_long_description(client, headers):
    response = client.post("/jobs", json=make_payload(description="x" * 4001), headers=headers)
    assert response.status_code == 422
    assert client.post("/jobs", json=make_payload("ok-desc", description="x" * 4000), headers=headers).status_code == 201


def test_create_requires_company(client, headers):
    payload = make_payload()
    del payload["company"]
    assert client.post("/jobs", json=payload, headers=headers).status_code == 422


def test_create_rejects_client_set_server_fields(client, headers):
    for field, value in [("priority", 0), ("pipeline_status", "scored"), ("url_normalized", "x"), ("id", 5)]:
        response = client.post("/jobs", json=make_payload(**{field: value}), headers=headers)
        assert response.status_code == 422, field


def test_create_removes_html(client, headers):
    html = "<p>Hello <b>world</b></p><script>alert(1)</script><div>Second&nbsp;line &amp; more</div>"
    job = create(client, headers, description=html)
    assert "<" not in job["description"]
    assert "alert" not in job["description"]
    assert "Hello world" in job["description"]
    assert "&" in job["description"]


def test_create_truncates_description_to_1500(client, headers):
    job = create(client, headers, description="a" * 3000)
    assert len(job["description"]) == 1500
    fetched = client.get(f"/jobs/{job['id']}", headers=headers).json()
    assert len(fetched["description"]) == 1500


def test_get_one_and_404(client, headers):
    job = create(client, headers)
    response = client.get(f"/jobs/{job['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == job["id"]
    missing = client.get("/jobs/999999", headers=headers)
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Job not found"}
    assert client.get("/jobs/abc", headers=headers).status_code == 422


@pytest.mark.parametrize(
    "score,expected",
    [(100, "apply"), (70, "apply"), (69, "maybe"), (40, "maybe"), (39, "skip"), (0, "skip")],
)
def test_verdict_boundaries(client, headers, score, expected):
    job = create(client, headers)
    add_score(job["id"], score)
    fetched = client.get(f"/jobs/{job['id']}", headers=headers).json()
    assert fetched["score"] == score
    assert fetched["verdict"] == expected
    listed = client.get("/jobs", headers=headers).json()["items"][0]
    assert listed["score"] == score
    assert listed["verdict"] == expected


def test_verdict_uses_thresholds_from_settings(client, headers):
    job = create(client, headers)
    add_score(job["id"], 60)
    with engine.begin() as connection:
        connection.execute(text("update settings set value = cast('50' as jsonb) where key = 'apply_threshold'"))
    try:
        assert client.get(f"/jobs/{job['id']}", headers=headers).json()["verdict"] == "apply"
    finally:
        with engine.begin() as connection:
            connection.execute(text("update settings set value = cast('70' as jsonb) where key = 'apply_threshold'"))
    assert client.get(f"/jobs/{job['id']}", headers=headers).json()["verdict"] == "maybe"


def test_latest_score_wins(client, headers):
    job = create(client, headers)
    add_score(job["id"], 85, "now() - interval '2 days'", "v1")
    add_score(job["id"], 55, "now()", "v2")
    fetched = client.get(f"/jobs/{job['id']}", headers=headers).json()
    assert fetched["score"] == 55
    assert fetched["verdict"] == "maybe"
    listed = client.get("/jobs?min_score=60", headers=headers).json()
    assert listed["total"] == 0


def test_list_response_shape_and_unscored_job(client, headers):
    create(client, headers)
    body = client.get("/jobs", headers=headers).json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert body["total"] == 1
    assert body["items"][0]["score"] is None
    assert body["items"][0]["verdict"] is None


def test_unscored_job_hidden_by_score_and_verdict_filters(client, headers):
    create(client, headers)
    assert client.get("/jobs?min_score=0", headers=headers).json()["total"] == 0
    for verdict in ("apply", "maybe", "skip"):
        assert client.get(f"/jobs?verdict={verdict}", headers=headers).json()["total"] == 0
    assert client.get("/jobs", headers=headers).json()["total"] == 1


def test_filter_min_score(client, headers):
    low = create(client, headers, "low")
    high = create(client, headers, "high")
    add_score(low["id"], 30)
    add_score(high["id"], 80)
    ids = [item["id"] for item in client.get("/jobs?min_score=50", headers=headers).json()["items"]]
    assert ids == [high["id"]]
    assert client.get("/jobs?min_score=30", headers=headers).json()["total"] == 2


def test_filter_verdict(client, headers):
    jobs = {}
    for slug, score in [("a", 90), ("m", 50), ("s", 10)]:
        jobs[slug] = create(client, headers, slug)
        add_score(jobs[slug]["id"], score)
    for verdict, slug in [("apply", "a"), ("maybe", "m"), ("skip", "s")]:
        body = client.get(f"/jobs?verdict={verdict}", headers=headers).json()
        assert [item["id"] for item in body["items"]] == [jobs[slug]["id"]]


def test_filter_source(client, headers):
    manual = create(client, headers, "m1")
    extension = create(client, headers, "e1", source="extension")
    body = client.get("/jobs?source=extension", headers=headers).json()
    assert [item["id"] for item in body["items"]] == [extension["id"]]
    body = client.get("/jobs?source=manual", headers=headers).json()
    assert [item["id"] for item in body["items"]] == [manual["id"]]
    assert client.get("/jobs?source=remoteok", headers=headers).json()["total"] == 0


def test_filter_pipeline_status(client, headers):
    first = create(client, headers, "p1")
    create(client, headers, "p2")
    set_job_column(first["id"], "pipeline_status", "scored")
    body = client.get("/jobs?pipeline_status=scored", headers=headers).json()
    assert [item["id"] for item in body["items"]] == [first["id"]]
    assert client.get("/jobs?pipeline_status=new", headers=headers).json()["total"] == 1


def test_filter_q_searches_title_and_company_case_insensitive(client, headers):
    by_title = create(client, headers, "t1", title="Senior Django Engineer", company="Zeta")
    by_company = create(client, headers, "c1", title="Writer", company="DjangoWorks")
    create(client, headers, "n1", title="Cook", company="Kitchen")
    ids = {item["id"] for item in client.get("/jobs?q=djAngo", headers=headers).json()["items"]}
    assert ids == {by_title["id"], by_company["id"]}


def test_filter_q_escapes_wildcards(client, headers):
    percent = create(client, headers, "w1", title="100% Remote")
    create(client, headers, "w2", title="Plain role")
    underscore = create(client, headers, "w3", title="snake_case dev")
    create(client, headers, "w4", title="snakeXcase dev")
    assert [i["id"] for i in client.get("/jobs?q=%25", headers=headers).json()["items"]] == [percent["id"]]
    assert [i["id"] for i in client.get("/jobs?q=snake_case", headers=headers).json()["items"]] == [underscore["id"]]


@pytest.mark.parametrize(
    "query",
    [
        "min_score=101",
        "min_score=-1",
        "min_score=abc",
        "source=banana",
        "verdict=banana",
        "pipeline_status=banana",
        "limit=0",
        "limit=201",
        "offset=-1",
    ],
)
def test_list_invalid_filters_are_422(client, headers, query):
    response = client.get(f"/jobs?{query}", headers=headers)
    assert response.status_code == 422


def test_pagination(client, headers):
    ids = [create(client, headers, f"pg-{n}")["id"] for n in range(5)]
    first = client.get("/jobs?limit=2&offset=0", headers=headers).json()
    second = client.get("/jobs?limit=2&offset=2", headers=headers).json()
    third = client.get("/jobs?limit=2&offset=4", headers=headers).json()
    assert first["total"] == 5
    assert first["limit"] == 2
    assert second["offset"] == 2
    assert len(first["items"]) == 2
    assert len(second["items"]) == 2
    assert len(third["items"]) == 1
    seen = [item["id"] for page in (first, second, third) for item in page["items"]]
    assert sorted(seen) == sorted(ids)
    assert len(set(seen)) == 5


def test_ordering_priority_then_created_at_then_id(client, headers):
    low_old = create(client, headers, "o1")
    high_mid = create(client, headers, "o2")
    low_new = create(client, headers, "o3")
    high_new = create(client, headers, "o4")
    for job_id, priority, age in [
        (low_old["id"], 0, "3 hours"),
        (high_mid["id"], 1, "2 hours"),
        (low_new["id"], 0, "1 hour"),
        (high_new["id"], 1, "30 minutes"),
    ]:
        with engine.begin() as connection:
            connection.execute(
                text(f"update jobs set priority = :p, created_at = now() - interval '{age}' where id = :id"),
                {"p": priority, "id": job_id},
            )
    ids = [item["id"] for item in client.get("/jobs", headers=headers).json()["items"]]
    assert ids == [high_new["id"], high_mid["id"], low_new["id"], low_old["id"]]


def test_ordering_id_breaks_ties(client, headers):
    first = create(client, headers, "t1")
    second = create(client, headers, "t2")
    with engine.begin() as connection:
        connection.execute(text("update jobs set created_at = '2026-01-01T00:00:00+00', priority = 1"))
    ids = [item["id"] for item in client.get("/jobs", headers=headers).json()["items"]]
    assert ids == [second["id"], first["id"]]


def test_patch_success(client, headers):
    job = create(client, headers)
    response = client.patch(
        f"/jobs/{job['id']}",
        json={"title": "Backend Engineer", "company": "Beta", "location": "Cebu", "work_mode": "hybrid", "description": "<p>New text</p>"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Backend Engineer"
    assert body["company"] == "Beta"
    assert body["location"] == "Cebu"
    assert body["work_mode"] == "hybrid"
    assert body["description"] == "New text"
    assert body["url"] == job["url"]
    assert body["priority"] == job["priority"]
    assert body["pipeline_status"] == "new"


def test_patch_partial_leaves_other_fields(client, headers):
    job = create(client, headers, location="Manila")
    body = client.patch(f"/jobs/{job['id']}", json={"title": "Only Title"}, headers=headers).json()
    assert body["title"] == "Only Title"
    assert body["company"] == "Acme"
    assert body["location"] == "Manila"


def test_patch_can_clear_optional_fields(client, headers):
    job = create(client, headers, location="Manila", work_mode="remote")
    body = client.patch(f"/jobs/{job['id']}", json={"location": None, "work_mode": None}, headers=headers).json()
    assert body["location"] is None
    assert body["work_mode"] is None


def test_patch_returns_score_and_verdict(client, headers):
    job = create(client, headers)
    add_score(job["id"], 75)
    body = client.patch(f"/jobs/{job['id']}", json={"title": "Scored Job"}, headers=headers).json()
    assert body["score"] == 75
    assert body["verdict"] == "apply"


@pytest.mark.parametrize(
    "field,value",
    [
        ("source", "remoteok"),
        ("url", "https://example.com/p5a-test/other"),
        ("url_normalized", "x"),
        ("priority", 0),
        ("pipeline_status", "scored"),
        ("id", 99),
        ("created_at", "2026-01-01T00:00:00Z"),
    ],
)
def test_patch_forbidden_fields_are_422(client, headers, field, value):
    job = create(client, headers)
    response = client.patch(f"/jobs/{job['id']}", json={field: value}, headers=headers)
    assert response.status_code == 422
    fetched = client.get(f"/jobs/{job['id']}", headers=headers).json()
    assert fetched[field] == job[field]


def test_patch_empty_body_is_422(client, headers):
    job = create(client, headers)
    assert client.patch(f"/jobs/{job['id']}", json={}, headers=headers).status_code == 422


def test_patch_null_title_or_company_is_422(client, headers):
    job = create(client, headers)
    assert client.patch(f"/jobs/{job['id']}", json={"title": None}, headers=headers).status_code == 422
    assert client.patch(f"/jobs/{job['id']}", json={"company": None}, headers=headers).status_code == 422


def test_patch_validation_limits(client, headers):
    job = create(client, headers)
    assert client.patch(f"/jobs/{job['id']}", json={"title": "x" * 201}, headers=headers).status_code == 422
    assert client.patch(f"/jobs/{job['id']}", json={"description": "x" * 4001}, headers=headers).status_code == 422
    assert client.patch(f"/jobs/{job['id']}", json={"work_mode": "banana"}, headers=headers).status_code == 422


def test_patch_404(client, headers):
    response = client.patch("/jobs/999999", json={"title": "x"}, headers=headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_no_delete_endpoint(client, headers):
    job = create(client, headers)
    assert client.delete(f"/jobs/{job['id']}", headers=headers).status_code == 405
    assert count_jobs() == 1
