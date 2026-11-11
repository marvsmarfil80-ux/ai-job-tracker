import httpx
import pytest
from sqlalchemy import text

from app.db import SessionLocal, engine
from app.services.feeds import SOURCE_URLS
from app.services.hunts import run_hunt

TEST_DATABASE = "jobtracker_test"
SLUGS = ("remote-customer-support-jobs", "remote-programming-jobs", "all-other-remote-jobs")
WWR_URLS = (
    "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/all-other-remote-jobs.rss",
)
ENTITY_BODY = b'<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY a "b">]><rss><channel></channel></rss>'
REMOTEOK_BODY = (
    b'[{"position": "Data Entry Clerk", "company": "Gamma", '
    b'"url": "https://remoteok.com/remote-jobs/clerk-1"}]'
)
REMOTIVE_BODY = (
    b'{"jobs": [{"url": "https://remotive.com/remote-jobs/support/agent-1", '
    b'"title": "Support Agent", "company_name": "Delta"}]}'
)
OK_MESSAGE = (
    "3 of 3 feed URLs ok: remote-customer-support-jobs found 2 new 2, "
    "remote-programming-jobs found 2 new 0, all-other-remote-jobs found 2 new 0"
)


def wwr_body(*names):
    items = "".join(
        f"<item><title>Acme: {name}</title>"
        f"<link>https://weworkremotely.com/remote-jobs/{name}</link></item>"
        for name in names
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        f"{items}</channel></rss>"
    ).encode()


class FeedControl:
    def __init__(self):
        self.bodies = {slug: wwr_body() for slug in SLUGS}
        self.modes = {}
        self.calls = []
        self.client = httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        host = request.url.host
        if host == "weworkremotely.com":
            key = request.url.path.rsplit("/", 1)[-1].removesuffix(".rss")
            body = self.bodies[key]
        elif host == "remoteok.com":
            key = "remoteok"
            body = REMOTEOK_BODY
        else:
            key = "remotive"
            body = REMOTIVE_BODY
        self.calls.append(key)
        mode = self.modes.get(key, "ok")
        if mode == "timeout":
            raise httpx.ConnectTimeout("timeout")
        if mode == "entity":
            return httpx.Response(200, content=ENTITY_BODY)
        if isinstance(mode, int):
            headers = {"Location": "https://evil.example/x"} if 300 <= mode < 400 else {}
            return httpx.Response(mode, content=b"SECRET BODY", headers=headers)
        return httpx.Response(200, content=body)


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
    yield control
    control.client.close()


def hunt(control, requested=("weworkremotely",)):
    with SessionLocal() as db:
        return run_hunt(db, control.client, list(requested) if requested else None)


def count_jobs():
    with engine.connect() as connection:
        return connection.execute(text("select count(*) from jobs")).scalar_one()


def job_rows():
    with engine.connect() as connection:
        return connection.execute(
            text("select source, priority, work_mode from jobs order by id")
        ).all()


def event_rows():
    with engine.connect() as connection:
        return connection.execute(
            text("select run_id, message from system_events order by id")
        ).all()


def test_source_urls_are_the_approved_ones():
    assert SOURCE_URLS["weworkremotely"] == WWR_URLS
    assert SOURCE_URLS["remoteok"] == ("https://remoteok.com/api",)
    assert SOURCE_URLS["remotive"] == ("https://remotive.com/api/remote-jobs",)


def test_three_urls_ok_make_one_step_with_unique_counts(feeds):
    feeds.bodies[SLUGS[0]] = wwr_body("s1", "s2")
    feeds.bodies[SLUGS[1]] = wwr_body("p1", "p2", "p3")
    feeds.bodies[SLUGS[2]] = wwr_body("o1")
    result = hunt(feeds)
    assert result["status"] == "done"
    assert result["total_new"] == 6
    assert len(result["steps"]) == 1
    step = result["steps"][0]
    assert step["source"] == "weworkremotely"
    assert step["status"] == "done"
    assert step["found"] == 6
    assert step["new"] == 6
    assert step["message"] == (
        "3 of 3 feed URLs ok: remote-customer-support-jobs found 2 new 2, "
        "remote-programming-jobs found 3 new 3, all-other-remote-jobs found 1 new 1"
    )
    assert feeds.calls == list(SLUGS)
    rows = job_rows()
    assert len(rows) == 6
    assert all(row.source == "weworkremotely" for row in rows)
    assert all(row.priority == 0 for row in rows)
    assert all(row.work_mode == "remote" for row in rows)
    assert event_rows() == []


def test_same_job_in_two_urls_is_inserted_and_counted_once(feeds):
    feeds.bodies[SLUGS[0]] = wwr_body("a", "b")
    feeds.bodies[SLUGS[1]] = wwr_body("b", "c")
    feeds.bodies[SLUGS[2]] = wwr_body("c", "d")
    result = hunt(feeds)
    step = result["steps"][0]
    assert result["status"] == "done"
    assert step["status"] == "done"
    assert step["found"] == 4
    assert step["new"] == 4
    assert step["message"] == (
        "3 of 3 feed URLs ok: remote-customer-support-jobs found 2 new 2, "
        "remote-programming-jobs found 2 new 1, all-other-remote-jobs found 2 new 1"
    )
    assert count_jobs() == 4
    assert event_rows() == []


@pytest.mark.parametrize("mode", [503, 302, "timeout", "entity"])
def test_one_failing_url_keeps_the_step_done(feeds, mode):
    feeds.bodies[SLUGS[0]] = wwr_body("s1", "s2")
    feeds.bodies[SLUGS[2]] = wwr_body("o1")
    feeds.modes[SLUGS[1]] = mode
    result = hunt(feeds)
    step = result["steps"][0]
    assert result["status"] == "done"
    assert step["status"] == "done"
    assert step["found"] == 3
    assert step["new"] == 3
    assert step["message"] == (
        "2 of 3 feed URLs ok: remote-customer-support-jobs found 2 new 2, "
        "remote-programming-jobs failed, all-other-remote-jobs found 1 new 1"
    )
    assert "SECRET BODY" not in step["message"]
    assert feeds.calls == list(SLUGS)
    assert count_jobs() == 3
    assert event_rows() == []


def test_all_urls_failing_with_the_same_reason_makes_the_step_error(feeds):
    for slug in SLUGS:
        feeds.modes[slug] = "timeout"
    result = hunt(feeds)
    step = result["steps"][0]
    assert step["status"] == "error"
    assert step["found"] == 0
    assert step["new"] == 0
    assert step["message"] == "Feed request timed out"
    assert result["status"] == "error"
    assert [row.message for row in event_rows()] == ["weworkremotely: Feed request timed out"]
    assert count_jobs() == 0


def test_all_urls_failing_with_different_reasons_uses_a_generic_message(feeds):
    feeds.modes[SLUGS[0]] = 503
    feeds.modes[SLUGS[1]] = "timeout"
    feeds.modes[SLUGS[2]] = "entity"
    result = hunt(feeds)
    step = result["steps"][0]
    assert step["status"] == "error"
    assert step["message"] == "All feed URLs failed"
    assert "SECRET BODY" not in step["message"]
    assert result["status"] == "error"
    assert len(event_rows()) == 1


def test_full_hunt_sends_one_request_to_remotive_and_remoteok(feeds):
    result = hunt(feeds, None)
    assert len(result["steps"]) == 3
    assert feeds.calls.count("remotive") == 1
    assert feeds.calls.count("remoteok") == 1
    for slug in SLUGS:
        assert feeds.calls.count(slug) == 1


def test_daily_limit_counts_runs_not_urls(feeds):
    for _ in range(4):
        assert hunt(feeds)["steps"][0]["status"] == "done"
    fifth = hunt(feeds)["steps"][0]
    assert fifth["status"] == "skipped"
    assert fifth["message"] == "Daily run limit reached"
    assert len(feeds.calls) == 12


def test_lower_limit_counts_runs_not_urls(feeds):
    with engine.begin() as connection:
        connection.execute(
            text("update sources set max_runs_per_day = 2 where name = 'weworkremotely'")
        )
    assert hunt(feeds)["steps"][0]["status"] == "done"
    assert hunt(feeds)["steps"][0]["status"] == "done"
    third = hunt(feeds)["steps"][0]
    assert third["status"] == "skipped"
    assert len(feeds.calls) == 6


def test_pause_happens_between_urls_only(feeds, monkeypatch):
    sleeps = []

    class FakeTime:
        @staticmethod
        def sleep(seconds):
            sleeps.append(seconds)

    monkeypatch.setattr("app.services.hunts.PAUSE_BETWEEN_URLS_SECONDS", 1.0)
    monkeypatch.setattr("app.services.hunts.time", FakeTime)
    hunt(feeds)
    assert sleeps == [1.0, 1.0]
    hunt(feeds, ["remotive"])
    assert sleeps == [1.0, 1.0]