from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.main import app
from app.services.clock import get_now, manila_today
from app.services.follow_ups import is_overdue

BASE = "https://example.com/p8b-test"
FAKE_NOW = datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc)
FAKE_TODAY = date(2026, 10, 31)

ITEM_KEYS = {
    "id",
    "application_id",
    "title",
    "due_date",
    "status",
    "completed_at",
    "created_at",
    "is_overdue",
}
DETAIL_KEYS = ITEM_KEYS | {"application"}

ENDPOINTS = [
    ("POST", "/follow-ups", {"application_id": 1, "title": "x"}),
    ("GET", "/follow-ups", None),
    ("GET", "/follow-ups/1", None),
    ("PATCH", "/follow-ups/1", {"title": "x"}),
    ("DELETE", "/follow-ups/1", None),
]


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


@pytest.fixture(autouse=True)
def fixed_now():
    app.dependency_overrides[get_now] = lambda: FAKE_NOW
    yield
    app.dependency_overrides.pop(get_now, None)


def parse_dt(value):
    return datetime.fromisoformat(value)


def make_job(client, headers, slug, title="Python Developer", company="Acme"):
    response = client.post(
        "/jobs",
        json={
            "source": "manual",
            "title": title,
            "company": company,
            "url": f"{BASE}/{slug}",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def make_application(client, headers, slug, title="Python Developer", company="Acme"):
    job_id = make_job(client, headers, slug, title, company)
    response = client.post("/applications", json={"job_id": job_id}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def make_follow_up(client, headers, application_id, title="Follow up", due_date=None):
    body = {"application_id": application_id, "title": title}
    if due_date is not None:
        body["due_date"] = due_date
    response = client.post("/follow-ups", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def count_rows(table):
    with engine.connect() as connection:
        return connection.execute(text(f"select count(*) from {table}")).scalar_one()


def force_completed(follow_up_id, completed_at):
    with engine.begin() as connection:
        connection.execute(
            text(
                "update follow_ups set status = 'completed', completed_at = :completed_at "
                "where id = :id"
            ),
            {"completed_at": completed_at, "id": follow_up_id},
        )


def read_follow_up_row(follow_up_id):
    with engine.connect() as connection:
        return connection.execute(
            text(
                "select title, due_date, status, completed_at from follow_ups where id = :id"
            ),
            {"id": follow_up_id},
        ).one()


def seed_list_data(client, headers):
    app_a = make_application(client, headers, "alpha", "Alpha Role", "Alpha Co")
    app_b = make_application(client, headers, "beta", "Beta Role", "Beta Co")
    f1 = make_follow_up(client, headers, app_a, "overdue old", "2026-10-01")["id"]
    f2 = make_follow_up(client, headers, app_a, "due today", "2026-10-31")["id"]
    f3 = make_follow_up(client, headers, app_a, "future", "2026-11-15")["id"]
    f4 = make_follow_up(client, headers, app_b, "no date")["id"]
    f5 = make_follow_up(client, headers, app_b, "overdue recent", "2026-10-30")["id"]
    f6 = make_follow_up(client, headers, app_b, "done older", "2026-10-01")["id"]
    f7 = make_follow_up(client, headers, app_a, "done newer", "2026-10-02")["id"]
    force_completed(f6, datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc))
    force_completed(f7, datetime(2026, 10, 25, 8, 0, tzinfo=timezone.utc))
    return {
        "app_a": app_a,
        "app_b": app_b,
        "f1": f1,
        "f2": f2,
        "f3": f3,
        "f4": f4,
        "f5": f5,
        "f6": f6,
        "f7": f7,
    }


def list_ids(client, headers, query=""):
    response = client.get(f"/follow-ups{query}", headers=headers)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_requires_api_key(client, method, path, body):
    response = client.request(method, path, json=body)
    assert response.status_code == 401


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_rejects_wrong_api_key(client, method, path, body):
    response = client.request(method, path, json=body, headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_create_success(client, headers):
    application_id = make_application(client, headers, "create-ok")
    response = client.post(
        "/follow-ups",
        json={
            "application_id": application_id,
            "title": "Email the recruiter",
            "due_date": "2026-11-05",
        },
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert set(data) == ITEM_KEYS
    assert data["application_id"] == application_id
    assert data["title"] == "Email the recruiter"
    assert data["due_date"] == "2026-11-05"
    assert data["status"] == "pending"
    assert data["completed_at"] is None
    assert data["is_overdue"] is False
    assert data["created_at"]
    assert count_rows("follow_ups") == 1


def test_create_without_due_date(client, headers):
    application_id = make_application(client, headers, "create-nodate")
    data = make_follow_up(client, headers, application_id)
    assert data["due_date"] is None
    assert data["is_overdue"] is False


def test_create_with_past_due_date_is_overdue(client, headers):
    application_id = make_application(client, headers, "create-past")
    data = make_follow_up(client, headers, application_id, due_date="2026-10-01")
    assert data["due_date"] == "2026-10-01"
    assert data["is_overdue"] is True
    assert data["status"] == "pending"


def test_create_trims_title(client, headers):
    application_id = make_application(client, headers, "create-trim")
    data = make_follow_up(client, headers, application_id, title="  padded title  ")
    assert data["title"] == "padded title"


def test_create_title_of_exactly_200_chars_is_accepted(client, headers):
    application_id = make_application(client, headers, "create-200")
    data = make_follow_up(client, headers, application_id, title="x" * 200)
    assert len(data["title"]) == 200


@pytest.mark.parametrize("title", ["", "   ", "x" * 201])
def test_create_rejects_bad_titles(client, headers, title):
    application_id = make_application(client, headers, "create-badtitle")
    response = client.post(
        "/follow-ups",
        json={"application_id": application_id, "title": title},
        headers=headers,
    )
    assert response.status_code == 422
    assert count_rows("follow_ups") == 0


@pytest.mark.parametrize(
    "due_date",
    [
        "2019-12-31",
        "2099-01-01",
        "10/31/2026",
        "2026-13-01",
        "2026-10-31T00:00:00",
        20261031,
        "",
    ],
)
def test_create_rejects_bad_due_dates(client, headers, due_date):
    application_id = make_application(client, headers, "create-baddate")
    response = client.post(
        "/follow-ups",
        json={"application_id": application_id, "title": "x", "due_date": due_date},
        headers=headers,
    )
    assert response.status_code == 422
    assert count_rows("follow_ups") == 0


def test_create_due_date_boundaries(client, headers):
    application_id = make_application(client, headers, "create-bounds")
    lowest = make_follow_up(client, headers, application_id, due_date="2020-01-01")
    assert lowest["due_date"] == "2020-01-01"
    limit = manila_today() + timedelta(days=5 * 365 + 1)
    highest = make_follow_up(client, headers, application_id, due_date=limit.isoformat())
    assert highest["due_date"] == limit.isoformat()
    too_far = limit + timedelta(days=1)
    response = client.post(
        "/follow-ups",
        json={"application_id": application_id, "title": "x", "due_date": too_far.isoformat()},
        headers=headers,
    )
    assert response.status_code == 422


def test_create_unknown_application_is_404(client, headers):
    response = client.post(
        "/follow-ups", json={"application_id": 99999, "title": "x"}, headers=headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"
    assert count_rows("follow_ups") == 0


@pytest.mark.parametrize(
    "extra",
    [
        {"status": "completed"},
        {"completed_at": "2026-10-30T00:00:00Z"},
        {"id": 5},
        {"created_at": "2026-10-30T00:00:00Z"},
        {"is_overdue": True},
        {"unknown": 1},
    ],
)
def test_create_rejects_extra_fields(client, headers, extra):
    application_id = make_application(client, headers, "create-extra")
    response = client.post(
        "/follow-ups",
        json={"application_id": application_id, "title": "x", **extra},
        headers=headers,
    )
    assert response.status_code == 422
    assert count_rows("follow_ups") == 0


@pytest.mark.parametrize(
    "body",
    [
        {"title": "x"},
        {"application_id": 1},
        {"application_id": 0, "title": "x"},
        {"application_id": "1", "title": "x"},
        {"application_id": 1, "title": None},
        {},
    ],
)
def test_create_rejects_missing_or_wrong_fields(client, headers, body):
    response = client.post("/follow-ups", json=body, headers=headers)
    assert response.status_code == 422


def test_list_empty(client, headers):
    response = client.get("/follow-ups", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_default_ordering(client, headers):
    ids = seed_list_data(client, headers)
    assert list_ids(client, headers) == [
        ids["f1"],
        ids["f5"],
        ids["f2"],
        ids["f3"],
        ids["f4"],
        ids["f7"],
        ids["f6"],
    ]


def test_list_filter_by_status(client, headers):
    ids = seed_list_data(client, headers)
    assert list_ids(client, headers, "?status=pending") == [
        ids["f1"],
        ids["f5"],
        ids["f2"],
        ids["f3"],
        ids["f4"],
    ]
    assert list_ids(client, headers, "?status=completed") == [ids["f7"], ids["f6"]]


def test_list_filter_by_application(client, headers):
    ids = seed_list_data(client, headers)
    assert list_ids(client, headers, f"?application_id={ids['app_a']}") == [
        ids["f1"],
        ids["f2"],
        ids["f3"],
        ids["f7"],
    ]
    assert list_ids(client, headers, f"?application_id={ids['app_b']}") == [
        ids["f5"],
        ids["f4"],
        ids["f6"],
    ]
    assert list_ids(client, headers, "?application_id=99999") == []


def test_list_overdue_true_and_false(client, headers):
    ids = seed_list_data(client, headers)
    assert list_ids(client, headers, "?overdue=true") == [ids["f1"], ids["f5"]]
    assert list_ids(client, headers, "?overdue=false") == [
        ids["f2"],
        ids["f3"],
        ids["f4"],
        ids["f7"],
        ids["f6"],
    ]


def test_list_combined_filters(client, headers):
    ids = seed_list_data(client, headers)
    query = f"?status=pending&overdue=true&application_id={ids['app_b']}"
    assert list_ids(client, headers, query) == [ids["f5"]]
    assert list_ids(client, headers, "?status=completed&overdue=true") == []


def test_list_pagination(client, headers):
    ids = seed_list_data(client, headers)
    first = client.get("/follow-ups?limit=3&offset=0", headers=headers).json()
    second = client.get("/follow-ups?limit=3&offset=3", headers=headers).json()
    third = client.get("/follow-ups?limit=3&offset=6", headers=headers).json()
    assert first["total"] == second["total"] == third["total"] == 7
    assert (first["limit"], first["offset"]) == (3, 0)
    assert [item["id"] for item in first["items"]] == [ids["f1"], ids["f5"], ids["f2"]]
    assert [item["id"] for item in second["items"]] == [ids["f3"], ids["f4"], ids["f7"]]
    assert [item["id"] for item in third["items"]] == [ids["f6"]]


@pytest.mark.parametrize(
    "query",
    [
        "?limit=0",
        "?limit=201",
        "?offset=-1",
        "?status=done",
        "?overdue=maybe",
        "?application_id=0",
        "?application_id=abc",
    ],
)
def test_list_rejects_bad_query(client, headers, query):
    response = client.get(f"/follow-ups{query}", headers=headers)
    assert response.status_code == 422


def test_list_items_have_application_summary_and_is_overdue(client, headers):
    ids = seed_list_data(client, headers)
    response = client.get("/follow-ups", headers=headers)
    items = {item["id"]: item for item in response.json()["items"]}
    assert all(set(item) == DETAIL_KEYS for item in items.values())
    assert items[ids["f1"]]["application"] == {
        "application_id": ids["app_a"],
        "application_status": "applied",
        "job_title": "Alpha Role",
        "job_company": "Alpha Co",
    }
    assert items[ids["f4"]]["application"] == {
        "application_id": ids["app_b"],
        "application_status": "applied",
        "job_title": "Beta Role",
        "job_company": "Beta Co",
    }
    assert items[ids["f1"]]["is_overdue"] is True
    assert items[ids["f5"]]["is_overdue"] is True
    assert items[ids["f2"]]["is_overdue"] is False
    assert items[ids["f3"]]["is_overdue"] is False
    assert items[ids["f4"]]["is_overdue"] is False
    assert items[ids["f6"]]["is_overdue"] is False
    assert items[ids["f7"]]["is_overdue"] is False


def test_get_one_returns_follow_up_with_summary(client, headers):
    application_id = make_application(client, headers, "get-one", "Gamma Role", "Gamma Co")
    created = make_follow_up(client, headers, application_id, "Call them", "2026-10-20")
    response = client.get(f"/follow-ups/{created['id']}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert set(data) == DETAIL_KEYS
    assert data["title"] == "Call them"
    assert data["is_overdue"] is True
    assert data["application"] == {
        "application_id": application_id,
        "application_status": "applied",
        "job_title": "Gamma Role",
        "job_company": "Gamma Co",
    }


def test_get_one_missing_is_404(client, headers):
    response = client.get("/follow-ups/99999", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Follow-up not found"


@pytest.mark.parametrize("follow_up_id", ["0", "-1", "abc"])
def test_get_one_rejects_bad_id(client, headers, follow_up_id):
    response = client.get(f"/follow-ups/{follow_up_id}", headers=headers)
    assert response.status_code == 422


def test_patch_to_completed_sets_completed_at(client, headers):
    application_id = make_application(client, headers, "patch-complete")
    created = make_follow_up(client, headers, application_id, due_date="2026-10-01")
    assert created["is_overdue"] is True
    response = client.patch(
        f"/follow-ups/{created['id']}", json={"status": "completed"}, headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert parse_dt(data["completed_at"]) == FAKE_NOW
    assert data["is_overdue"] is False
    assert data["application"]["application_id"] == application_id
    row = read_follow_up_row(created["id"])
    assert row.status == "completed"
    assert row.completed_at == FAKE_NOW


def test_patch_back_to_pending_clears_completed_at(client, headers):
    application_id = make_application(client, headers, "patch-reopen")
    created = make_follow_up(client, headers, application_id, due_date="2026-10-01")
    client.patch(
        f"/follow-ups/{created['id']}", json={"status": "completed"}, headers=headers
    )
    response = client.patch(
        f"/follow-ups/{created['id']}", json={"status": "pending"}, headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["completed_at"] is None
    assert data["is_overdue"] is True
    assert read_follow_up_row(created["id"]).completed_at is None


def test_patch_same_status_keeps_completed_at(client, headers):
    application_id = make_application(client, headers, "patch-same")
    created = make_follow_up(client, headers, application_id)
    response = client.patch(
        f"/follow-ups/{created['id']}", json={"status": "pending"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["completed_at"] is None
    older = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
    force_completed(created["id"], older)
    response = client.patch(
        f"/follow-ups/{created['id']}",
        json={"status": "completed", "title": "Renamed"},
        headers=headers,
    )
    assert response.status_code == 200
    assert parse_dt(response.json()["completed_at"]) == older
    assert read_follow_up_row(created["id"]).completed_at == older


def test_patch_due_date_can_be_cleared(client, headers):
    application_id = make_application(client, headers, "patch-clear")
    created = make_follow_up(client, headers, application_id, due_date="2026-10-01")
    response = client.patch(
        f"/follow-ups/{created['id']}", json={"due_date": None}, headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["due_date"] is None
    assert data["is_overdue"] is False
    assert read_follow_up_row(created["id"]).due_date is None


def test_patch_title_and_due_date(client, headers):
    application_id = make_application(client, headers, "patch-fields")
    created = make_follow_up(client, headers, application_id, "Old", "2026-10-01")
    response = client.patch(
        f"/follow-ups/{created['id']}",
        json={"title": "  New title  ", "due_date": "2026-12-01"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New title"
    assert data["due_date"] == "2026-12-01"
    assert data["is_overdue"] is False
    assert data["status"] == "pending"


@pytest.mark.parametrize(
    "body",
    [
        {"id": 5},
        {"application_id": 1},
        {"completed_at": "2026-10-30T00:00:00Z"},
        {"created_at": "2026-10-30T00:00:00Z"},
        {"is_overdue": True},
        {"unknown": 1},
    ],
)
def test_patch_rejects_forbidden_fields(client, headers, body):
    application_id = make_application(client, headers, "patch-forbidden")
    created = make_follow_up(client, headers, application_id, "Keep", "2026-11-01")
    response = client.patch(f"/follow-ups/{created['id']}", json=body, headers=headers)
    assert response.status_code == 422
    row = read_follow_up_row(created["id"])
    assert row.title == "Keep"
    assert row.status == "pending"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"title": None},
        {"status": None},
        {"title": ""},
        {"title": "x" * 201},
        {"status": "done"},
        {"due_date": "2019-12-31"},
        {"due_date": "2099-01-01"},
        {"due_date": "not-a-date"},
        {"due_date": 20261031},
    ],
)
def test_patch_rejects_bad_bodies(client, headers, body):
    application_id = make_application(client, headers, "patch-badbody")
    created = make_follow_up(client, headers, application_id, "Keep", "2026-11-01")
    response = client.patch(f"/follow-ups/{created['id']}", json=body, headers=headers)
    assert response.status_code == 422
    row = read_follow_up_row(created["id"])
    assert row.title == "Keep"
    assert row.status == "pending"
    assert row.due_date == date(2026, 11, 1)


def test_patch_missing_is_404(client, headers):
    response = client.patch("/follow-ups/99999", json={"title": "x"}, headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Follow-up not found"


def test_delete_removes_only_the_follow_up(client, headers):
    application_id = make_application(client, headers, "delete-ok")
    created = make_follow_up(client, headers, application_id)
    response = client.delete(f"/follow-ups/{created['id']}", headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/follow-ups/{created['id']}", headers=headers).status_code == 404
    assert count_rows("follow_ups") == 0
    assert count_rows("applications") == 1


def test_delete_missing_is_404(client, headers):
    response = client.delete("/follow-ups/99999", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Follow-up not found"


def test_is_overdue_boundary_due_today_is_not_overdue(client, headers):
    application_id = make_application(client, headers, "boundary-today")
    today_item = make_follow_up(client, headers, application_id, due_date="2026-10-31")
    yesterday_item = make_follow_up(client, headers, application_id, due_date="2026-10-30")
    assert today_item["is_overdue"] is False
    assert yesterday_item["is_overdue"] is True


def test_overdue_uses_manila_date_not_utc(client, headers):
    assert FAKE_NOW.date() == date(2026, 10, 30)
    application_id = make_application(client, headers, "boundary-manila")
    created = make_follow_up(client, headers, application_id, due_date="2026-10-30")
    assert created["is_overdue"] is True
    assert list_ids(client, headers, "?overdue=true") == [created["id"]]


def test_manila_today_switches_at_16_utc():
    before = datetime(2026, 10, 30, 15, 59, 59, tzinfo=timezone.utc)
    after = datetime(2026, 10, 30, 16, 0, 0, tzinfo=timezone.utc)
    assert manila_today(before) == date(2026, 10, 30)
    assert manila_today(after) == date(2026, 10, 31)


def test_manila_today_requires_timezone():
    with pytest.raises(ValueError):
        manila_today(datetime(2026, 10, 30, 12, 0))


def test_is_overdue_function_rules():
    today = date(2026, 10, 31)
    assert is_overdue("pending", date(2026, 10, 30), today) is True
    assert is_overdue("pending", date(2026, 10, 31), today) is False
    assert is_overdue("pending", date(2026, 11, 1), today) is False
    assert is_overdue("pending", None, today) is False
    assert is_overdue("completed", date(2026, 10, 1), today) is False


def test_truncating_jobs_cascades_to_follow_ups(client, headers):
    application_id = make_application(client, headers, "cascade")
    make_follow_up(client, headers, application_id)
    assert count_rows("follow_ups") == 1
    with engine.begin() as connection:
        name = connection.execute(text("select current_database()")).scalar_one()
        assert name == "jobtracker_test"
        connection.execute(text("truncate table jobs restart identity cascade"))
    assert count_rows("follow_ups") == 0
    assert count_rows("applications") == 0
    assert count_rows("jobs") == 0


def test_tables_start_empty_after_previous_test_left_rows(client, headers):
    assert count_rows("jobs") == 0
    assert count_rows("applications") == 0
    assert count_rows("follow_ups") == 0