import json
from datetime import timedelta

import httpx
import pytest

from app.services import feeds
from app.services.feeds import (
    FEED_URLS,
    FeedError,
    fetch_feed,
    parse_remoteok,
    parse_remotive,
    parse_weworkremotely,
)

WWR_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
<title>Acme: Support Agent</title>
<region>Anywhere in the World</region>
<country>Canada</country>
<description>&lt;p&gt;Hello &lt;b&gt;team&lt;/b&gt;&lt;script&gt;alert(1)&lt;/script&gt;&lt;/p&gt;</description>
<pubDate>Tue, 27 Oct 2026 07:30:50 +0000</pubDate>
<link>https://weworkremotely.com/remote-jobs/acme-support-agent?utm_source=x</link>
</item>
<item><title></title><link>https://weworkremotely.com/remote-jobs/no-title</link></item>
<item><title>Bad: Link</title><link>javascript:alert(1)</link></item>
</channel></rss>"""

REMOTEOK_JSON = json.dumps(
    [
        {"last_updated": "1793001612", "legal": "Fake legal notice"},
        {
            "position": "Data Entry Clerk",
            "company": "Acme",
            "url": "https://remoteOK.com/remote-jobs/data-entry-1?ref=abc",
            "date": "2026-10-26T08:00:12+00:00",
            "description": "About us<p>We need <i>help</i></p>",
            "location": "",
        },
        {"company": "NoTitle", "url": "https://remoteok.com/remote-jobs/no-title-2"},
    ]
).encode()

REMOTIVE_JSON = json.dumps(
    {
        "00-warning": "Fake warning",
        "0-legal-notice": "Fake legal notice",
        "job-count": 1,
        "jobs": [
            {
                "id": 1,
                "url": "https://remotive.com/remote-jobs/support/agent-1",
                "title": "Support Agent",
                "company_name": "Acme",
                "publication_date": "2026-10-22T18:40:19",
                "candidate_required_location": "Worldwide",
                "description": "<p dir=\"ltr\"><span>Answer tickets</span></p>",
            }
        ],
    }
).encode()


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_wwr_valid_item_and_skipped_items():
    parsed = parse_weworkremotely(WWR_XML)
    assert len(parsed.jobs) == 1
    assert parsed.skipped == 2
    job = parsed.jobs[0]
    assert job.source == "weworkremotely"
    assert job.company == "Acme"
    assert job.title == "Support Agent"
    assert job.location == "Anywhere in the World, Canada"
    assert job.url_normalized == "https://weworkremotely.com/remote-jobs/acme-support-agent"
    assert job.published is not None and job.published.year == 2026
    assert job.published.tzinfo is not None


def test_wwr_html_is_removed_from_description():
    job = parse_weworkremotely(WWR_XML).jobs[0]
    assert job.description == "Hello team"


def test_wwr_title_without_colon_keeps_full_title():
    raw = b"<rss><channel><item><title>Support Agent</title><link>https://example.com/a</link></item></channel></rss>"
    job = parse_weworkremotely(raw).jobs[0]
    assert job.company is None
    assert job.title == "Support Agent"


def test_wwr_long_fields_are_clipped_not_rejected():
    raw = (
        "<rss><channel><item>"
        f"<title>{'c' * 300}: {'t' * 500}</title>"
        f"<region>{'r' * 300}</region>"
        "<link>https://example.com/a</link>"
        "</item></channel></rss>"
    ).encode()
    parsed = parse_weworkremotely(raw)
    assert parsed.skipped == 0
    job = parsed.jobs[0]
    assert len(job.title) == 200
    assert len(job.company) == 200
    assert len(job.location) == 200


def test_wwr_description_is_limited_to_1500_chars():
    raw = (
        "<rss><channel><item><title>A: B</title><link>https://example.com/a</link>"
        f"<description>{'word ' * 1000}</description></item></channel></rss>"
    ).encode()
    assert len(parse_weworkremotely(raw).jobs[0].description) <= 1500


def test_wwr_rejects_xml_entities():
    raw = b'<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY a "b">]><rss><channel></channel></rss>'
    with pytest.raises(FeedError, match="entities"):
        parse_weworkremotely(raw)


def test_wwr_invalid_xml():
    with pytest.raises(FeedError, match="not valid XML"):
        parse_weworkremotely(b"<rss><channel>")


def test_remoteok_legal_notice_removed_and_invalid_skipped():
    parsed = parse_remoteok(REMOTEOK_JSON)
    assert len(parsed.jobs) == 1
    assert parsed.skipped == 1
    job = parsed.jobs[0]
    assert job.source == "remoteok"
    assert job.title == "Data Entry Clerk"
    assert job.company == "Acme"
    assert job.location is None
    assert job.url_normalized == "https://remoteok.com/remote-jobs/data-entry-1"
    assert job.description == "About us We need help"
    assert job.published is not None


def test_remoteok_removes_nul_characters():
    raw = json.dumps(
        [{"position": "Data\u0000 Entry", "company": "Ac\u0000me", "url": "https://remoteok.com/a"}]
    ).encode()
    job = parse_remoteok(raw).jobs[0]
    assert job.title == "Data Entry"
    assert job.company == "Acme"


def test_remoteok_rejects_non_http_url():
    raw = json.dumps([{"position": "X", "url": "ftp://remoteok.com/a"}]).encode()
    parsed = parse_remoteok(raw)
    assert parsed.jobs == []
    assert parsed.skipped == 1


def test_remoteok_unexpected_format():
    with pytest.raises(FeedError, match="Unexpected feed format"):
        parse_remoteok(b'{"not": "a list"}')


def test_remoteok_invalid_json():
    with pytest.raises(FeedError, match="not valid JSON"):
        parse_remoteok(b"not json")


def test_remotive_reads_jobs_key_and_location():
    parsed = parse_remotive(REMOTIVE_JSON)
    assert parsed.skipped == 0
    job = parsed.jobs[0]
    assert job.source == "remotive"
    assert job.title == "Support Agent"
    assert job.company == "Acme"
    assert job.location == "Worldwide"
    assert job.description == "Answer tickets"
    assert job.published.utcoffset() == timedelta(0)


def test_remotive_missing_jobs_key():
    with pytest.raises(FeedError, match="Unexpected feed format"):
        parse_remotive(b'{"job-count": 0}')


def test_fetch_returns_body_and_sends_user_agent():
    seen = {}

    def handler(request):
        seen["agent"] = request.headers.get("user-agent")
        seen["url"] = str(request.url)
        return httpx.Response(200, content=b"abc")

    body = fetch_feed(client_for(handler), "remoteok")
    assert body == b"abc"
    assert seen["agent"] == feeds.USER_AGENT
    assert seen["url"] == FEED_URLS["remoteok"]


@pytest.mark.parametrize("code", [403, 429, 503])
def test_fetch_rejects_non_200(code):
    client = client_for(lambda request: httpx.Response(code, content=b"secret body text"))
    with pytest.raises(FeedError) as info:
        fetch_feed(client, "remotive")
    assert str(info.value) == f"Feed returned HTTP {code}"


def test_fetch_does_not_follow_redirects():
    client = client_for(
        lambda request: httpx.Response(302, headers={"Location": "https://evil.example/x"})
    )
    with pytest.raises(FeedError) as info:
        fetch_feed(client, "remoteok")
    assert str(info.value) == "Feed returned HTTP 302"


def test_fetch_rejects_too_large_response(monkeypatch):
    monkeypatch.setattr(feeds, "MAX_RESPONSE_BYTES", 10)
    client = client_for(lambda request: httpx.Response(200, content=b"x" * 50))
    with pytest.raises(FeedError, match="too large"):
        fetch_feed(client, "weworkremotely")


def test_fetch_timeout():
    def handler(request):
        raise httpx.ConnectTimeout("timeout")

    with pytest.raises(FeedError, match="timed out"):
        fetch_feed(client_for(handler), "remoteok")


def test_fetch_network_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(FeedError, match="request failed"):
        fetch_feed(client_for(handler), "remoteok")