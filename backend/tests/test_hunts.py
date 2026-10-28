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
SOURCES = ["weworkremotely", "remoteok", "remotive"]
HOSTS = {
    "weworkremotely.com": "weworkremotely",
    "remoteok.com": "remoteok",
    "remotive.com": "remotive",
}


def wwr_xml(suffix=""):
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        "<item><title>Acme: Support Agent</title><region>Anywhere</region>"
        "<description>&lt;p&gt;Help &lt;b&gt;users&lt;/b&gt;&lt;/p&gt;</description>"
        "<pubDate>Tue, 27 Oct 2026 07:30:50 +0000</pubDate>"
        f"<link>https://weworkremotely.com/remote-jobs/acme-support{suffix}</link></item>"
        "<item><title>Beta: Admin Helper</title>"
        f"<link>https://weworkremotely.com/remote-jobs/beta-admin{suffix}</link></item>"
        "</channel></rss>"
    ).encode()


REMOTEOK_BODY = json.dumps(
    [
        {"last_updated": "1793001612", "legal": "Fake legal notice"},
        {
            "position": "Data Entry Clerk",
            "company": "Gamma",
            "url": "https://remoteok.com/remote-jobs/data-entry-1",
            "date": "2026-10-26T08:00:12+00:00",
            "description": "<p>Enter data</p>",
            "location": "",
        },
        {"company": "NoTitle", "url": "https://remoteok.com/remote-jobs/no-title"},
    ]
).encode()

REMOTIVE_BODY = json.dumps(
    {
        "00-warning": "Fake warning",
        "0-legal-notice": "Fake legal notice",
        "jobs": [
            {
                "url": "https://remotive.com/remote-jobs/support/agent-1",
                "title": "Support Agent",
                "company_name": "Delta",
                "publication_date": "2026-10-22T18:40:19",
                "candidate_required_location": "Worldwide",
                "description": "<p>Answer tickets</p>",
            }
        ],
    }
).encode()


class FeedControl:
    def __init__(self):
        self.modes = {}
        self.bodies = {
            "weworkremotely": wwr_xml(),
            "remoteok": REMOTEOK_BODY,
            "remotive": REMOTIVE_BODY,
        }
        self.calls = []
        self.client = httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        source = HOSTS[request.url.host]
        self.calls.append(source)
        mode = self.modes.get(source, "ok")
        if mode == "timeout":
            raise httpx.ConnectTimeout("timeout")
        if isinstance(mode, int):
            return httpx.Response(mode, content=b"SECRET BODY")
        return httpx.Response(200, content=self.bodies[source])


def reset_tables():
    with engine.begin() as connection:
        name = connection.execute(text("select current_database()")).scalar_one()
        if name != TEST_DATABASE:
            pytest.exit("Refusing to run: connected to the wrong database", returncode=2)
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
def hunt_environment():
    reset_tables()
    yield
    reset_tables()


@pytest.fixture
def feeds():
    control = FeedControl()
    app.dependency_overrides[feed_client] = lambda: control.client
    yield control
    app.dependency_overrides.pop(feed_client, None)
    control.client.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def hunt(control, requested=None):
    with SessionLocal() as db:
        return run_hunt(db, control.client, requested)


def steps_by_source(result):
    return {step["source"]: step for step in result["steps"]}


def job_rows():
    with engine.connect() as connection:
        return connection.execute(
            text("select source, priority, pipeline_status, work_mode from jobs order by id")
        ).all()


def count_jobs():
    with engine.connect() as connection:
        return connection.execute(text("select count(*) from jobs")).scalar_one()


def event_rows():
    with engine.connect() as connection:
        return connection.execute(
            text("select component, level, run_id, message from system_events order by id")
        ).all()


def source_row(name):
    with engine.connect() as connection:
        return connection.execute(
            text("select enabled, last_run_at from sources where name = :name"),
            {"name": name},
        ).one()


def test_all_sources_succeed(feeds):
    result = hunt(feeds)
    assert result["status"] == "done"
    assert result["trigger"] == "manual"
    assert result["finished_at"] is not None
    assert result["total_new"] == 4
    steps = steps_by_source(result)
    assert set(steps) == set(SOURCES)
    assert steps["weworkremotely"]["status"] == "done"
    assert steps["weworkremotely"]["found"] == 2
    assert steps["weworkremotely"]["new"] == 2
    assert steps["weworkremotely"]["message"] is None
    assert steps["remoteok"]["found"] == 1
    assert steps["remoteok"]["new"] == 1
    assert steps["remotive"]["found"] == 1
    assert steps["remotive"]["new"] == 1


def test_remoteok_invalid_item_is_counted_as_skipped(feeds):
    steps = steps_by_source(hunt(feeds))
    assert steps["remoteok"]["message"] == "Skipped 1 invalid items"


def test_feed_jobs_have_expected_fields(feeds):
    hunt(feeds)
    rows = job_rows()
    assert len(rows) == 4
    assert {row.source for row in rows} == set(SOURCES)
    assert all(row.priority == 0 for row in rows)
    assert all(row.pipeline_status == "new" for row in rows)
    assert all(row.work_mode == "remote" for row in rows)


def test_second_run_adds_no_duplicates(feeds):
    first = hunt(feeds)
    second = hunt(feeds)
    assert first["total_new"] == 4
    assert second["total_new"] == 0
    assert all(step["new"] == 0 for step in second["steps"])
    assert steps_by_source(second)["weworkremotely"]["found"] == 2
    assert count_jobs() == 4


def test_different_tracking_params_are_the_same_job(feeds):
    hunt(feeds, ["weworkremotely"])
    feeds.bodies["weworkremotely"] = wwr_xml("?utm_source=zzz&amp;ref=abc")
    second = hunt(feeds, ["weworkremotely"])
    assert steps_by_source(second)["weworkremotely"]["found"] == 2
    assert second["total_new"] == 0
    assert count_jobs() == 2


def test_one_failing_source_does_not_stop_the_others(feeds):
    feeds.modes["remoteok"] = 503
    result = hunt(feeds)
    steps = steps_by_source(result)
    assert result["status"] == "done"
    assert steps["remoteok"]["status"] == "error"
    assert steps["remoteok"]["message"] == "Feed returned HTTP 503"
    assert steps["weworkremotely"]["status"] == "done"
    assert steps["remotive"]["status"] == "done"
    assert result["total_new"] == 3
    events = event_rows()
    assert len(events) == 1
    assert events[0].component == "feeds"
    assert events[0].level == "error"
    assert events[0].run_id == result["id"]
    assert events[0].message == "remoteok: Feed returned HTTP 503"
    assert "SECRET BODY" not in events[0].message


def test_all_sources_failing_makes_the_run_error(feeds):
    for name in SOURCES:
        feeds.modes[name] = "timeout"
    result = hunt(feeds)
    assert result["status"] == "error"
    assert result["total_new"] == 0
    assert all(step["status"] == "error" for step in result["steps"])
    assert all(step["message"] == "Feed request timed out" for step in result["steps"])
    assert len(event_rows()) == 3


def test_fifth_remotive_run_is_skipped(feeds):
    for _ in range(4):
        result = hunt(feeds, ["remotive"])
        assert steps_by_source(result)["remotive"]["status"] == "done"
    fifth = hunt(feeds, ["remotive"])
    step = steps_by_source(fifth)["remotive"]
    assert step["status"] == "skipped"
    assert step["message"] == "Daily run limit reached"
    assert step["found"] == 0
    assert step["new"] == 0
    assert feeds.calls.count("remotive") == 4
    assert fifth["status"] == "done"


def test_null_limit_is_treated_as_four(feeds):
    for _ in range(4):
        hunt(feeds, ["remoteok"])
    step = steps_by_source(hunt(feeds, ["remoteok"]))["remoteok"]
    assert step["status"] == "skipped"
    assert step["message"] == "Daily run limit reached"


def test_lower_limit_is_respected(feeds):
    with engine.begin() as connection:
        connection.execute(text("update sources set max_runs_per_day = 1 where name = 'remoteok'"))
    hunt(feeds, ["remoteok"])
    step = steps_by_source(hunt(feeds, ["remoteok"]))["remoteok"]
    assert step["status"] == "skipped"
    assert feeds.calls.count("remoteok") == 1


def test_disabled_source_is_skipped_when_requested(feeds):
    with engine.begin() as connection:
        connection.execute(text("update sources set enabled = false where name = 'remoteok'"))
    result = hunt(feeds, ["remoteok"])
    step = steps_by_source(result)["remoteok"]
    assert step["status"] == "skipped"
    assert step["message"] == "Source is disabled"
    assert "remoteok" not in feeds.calls


def test_disabled_source_is_left_out_by_default(feeds):
    with engine.begin() as connection:
        connection.execute(text("update sources set enabled = false where name = 'remoteok'"))
    result = hunt(feeds)
    assert set(steps_by_source(result)) == {"weworkremotely", "remotive"}
    assert "remoteok" not in feeds.calls


def test_last_run_at_is_set_only_for_attempted_sources(feeds):
    with engine.begin() as connection:
        connection.execute(text("update sources set enabled = false where name = 'remoteok'"))
    hunt(feeds, ["remoteok", "remotive"])
    assert source_row("remotive").last_run_at is not None
    assert source_row("remoteok").last_run_at is None
    assert source_row("weworkremotely").last_run_at is None


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/hunts"),
        ("post", "/hunts"),
        ("get", "/hunts/1"),
        ("get", "/sources"),
        ("patch", "/sources/1"),
    ],
)
def test_endpoints_require_api_key(client, feeds, method, path):
    assert getattr(client, method)(path).status_code == 401
    wrong = {"X-API-Key": "wrong-key"}
    assert getattr(client, method)(path, headers=wrong).status_code == 401


def test_post_hunts_returns_run(client, headers, feeds):
    response = client.post("/hunts", headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "done"
    assert body["total_new"] == 4
    assert len(body["steps"]) == 3
    assert set(body["steps"][0]) == {"source", "status", "found", "new", "message"}


def test_post_hunts_with_selected_sources(client, headers, feeds):
    response = client.post("/hunts", headers=headers, json={"sources": ["remotive"]})
    assert response.status_code == 201
    assert [step["source"] for step in response.json()["steps"]] == ["remotive"]
    assert feeds.calls == ["remotive"]


@pytest.mark.parametrize(
    "payload",
    [
        {"sources": ["linkedin_email"]},
        {"sources": ["bogus"]},
        {"sources": []},
        {"sources": ["remotive"], "url": "https://evil.example/feed"},
        {"url": "https://evil.example/feed"},
    ],
)
def test_post_hunts_rejects_invalid_body(client, headers, feeds, payload):
    assert client.post("/hunts", headers=headers, json=payload).status_code == 422
    assert feeds.calls == []


def test_get_hunts_lists_newest_first(client, headers, feeds):
    first = client.post("/hunts", headers=headers, json={"sources": ["remotive"]}).json()
    second = client.post("/hunts", headers=headers, json={"sources": ["remoteok"]}).json()
    body = client.get("/hunts", headers=headers).json()
    assert body["total"] == 2
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert [item["id"] for item in body["items"]] == [second["id"], first["id"]]
    assert body["items"][0]["steps"][0]["source"] == "remoteok"
    limited = client.get("/hunts?limit=1&offset=1", headers=headers).json()
    assert limited["total"] == 2
    assert [item["id"] for item in limited["items"]] == [first["id"]]


def test_get_hunts_validates_paging(client, headers):
    assert client.get("/hunts?limit=0", headers=headers).status_code == 422
    assert client.get("/hunts?limit=101", headers=headers).status_code == 422
    assert client.get("/hunts?offset=-1", headers=headers).status_code == 422


def test_get_hunt_by_id_and_404(client, headers, feeds):
    created = client.post("/hunts", headers=headers).json()
    found = client.get(f"/hunts/{created['id']}", headers=headers)
    assert found.status_code == 200
    assert found.json()["id"] == created["id"]
    assert len(found.json()["steps"]) == 3
    missing = client.get("/hunts/999999", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Hunt not found"


def test_get_sources(client, headers, feeds):
    client.post("/hunts", headers=headers, json={"sources": ["remotive"]})
    body = client.get("/sources", headers=headers).json()
    assert body["total"] == 3
    by_name = {item["name"]: item for item in body["items"]}
    assert set(by_name) == set(SOURCES)
    assert by_name["remotive"]["runs_today"] == 1
    assert by_name["remotive"]["last_run_at"] is not None
    assert by_name["remoteok"]["runs_today"] == 0
    assert by_name["remoteok"]["max_runs_per_day"] is None
    assert by_name["remoteok"]["effective_max_runs_per_day"] == 4
    assert by_name["remotive"]["effective_max_runs_per_day"] == 4
    assert set(by_name["remotive"]) == {
        "id",
        "name",
        "badge",
        "enabled",
        "keywords",
        "max_runs_per_day",
        "last_run_at",
        "effective_max_runs_per_day",
        "runs_today",
    }


def source_id(client, headers, name):
    items = client.get("/sources", headers=headers).json()["items"]
    return next(item["id"] for item in items if item["name"] == name)


def test_patch_source_allowed_fields(client, headers):
    sid = source_id(client, headers, "remoteok")
    response = client.patch(
        f"/sources/{sid}",
        headers=headers,
        json={"enabled": False, "max_runs_per_day": 2, "keywords": ["support", " admin ", "support"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["max_runs_per_day"] == 2
    assert body["effective_max_runs_per_day"] == 2
    assert body["keywords"] == ["support", "admin"]
    assert body["name"] == "remoteok"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "hacked"},
        {"badge": "Hacked"},
        {"id": 99},
        {"url": "https://evil.example/feed"},
        {"feed_url": "https://evil.example/feed"},
        {"last_run_at": "2026-01-01T00:00:00Z"},
        {"max_runs_per_day": 5},
        {"max_runs_per_day": 0},
        {"max_runs_per_day": None},
        {"max_runs_per_day": "3"},
        {"enabled": "yes"},
        {"enabled": None},
        {"keywords": ["x" * 51]},
        {"keywords": [""]},
        {"keywords": ["k"] * 21},
        {"keywords": None},
        {},
    ],
)
def test_patch_source_rejects_bad_payloads(client, headers, payload):
    sid = source_id(client, headers, "remoteok")
    assert client.patch(f"/sources/{sid}", headers=headers, json=payload).status_code == 422
    unchanged = client.get("/sources", headers=headers).json()["items"]
    row = next(item for item in unchanged if item["id"] == sid)
    assert row["name"] == "remoteok"
    assert row["badge"] == "RemoteOK"
    assert row["max_runs_per_day"] is None
    assert row["enabled"] is True


def test_patch_source_404(client, headers):
    response = client.patch("/sources/999999", headers=headers, json={"enabled": False})
    assert response.status_code == 404
    assert response.json()["detail"] == "Source not found"


def test_patch_cannot_change_what_gets_fetched(client, headers, feeds):
    sid = source_id(client, headers, "remoteok")
    client.patch(f"/sources/{sid}", headers=headers, json={"keywords": ["support"]})
    client.post("/hunts", headers=headers, json={"sources": ["remoteok"]})
    assert feeds.calls == ["remoteok"]


def test_jobs_endpoint_shows_feed_jobs(client, headers, feeds):
    client.post("/hunts", headers=headers)
    body = client.get("/jobs", headers=headers).json()
    assert body["total"] == 4
    assert {item["source"] for item in body["items"]} == set(SOURCES)
    assert all(item["priority"] == 0 for item in body["items"])
    assert all(item["pipeline_status"] == "new" for item in body["items"])
    assert all(item["work_mode"] == "remote" for item in body["items"])
    only = client.get("/jobs?source=remotive", headers=headers).json()
    assert only["total"] == 1
    assert only["items"][0]["location"] == "Worldwide"
    assert only["items"][0]["company"] == "Delta"