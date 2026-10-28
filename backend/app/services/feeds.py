import json
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx

from app.services.jobs import clean_description
from app.services.normalize import normalize_url

FEED_URLS = {
    "weworkremotely": "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
    "remoteok": "https://remoteok.com/api",
    "remotive": "https://remotive.com/api/remote-jobs",
}
USER_AGENT = "Mozilla/5.0 (compatible; JobTrackerPersonal/0.1)"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 20.0
MAX_TOTAL_SECONDS = 30.0
MAX_FIELD_LENGTH = 200
MAX_URL_LENGTH = 2000


class FeedError(Exception):
    pass


@dataclass
class FeedJob:
    source: str
    title: str
    company: str | None
    url: str
    url_normalized: str
    published: datetime | None
    description: str | None
    location: str | None


@dataclass
class ParsedFeed:
    jobs: list[FeedJob] = field(default_factory=list)
    skipped: int = 0


def get_feed_client() -> httpx.Client:
    return httpx.Client(follow_redirects=False)


def fetch_feed(client: httpx.Client, source: str) -> bytes:
    started = time.monotonic()
    chunks: list[bytes] = []
    total = 0
    try:
        with client.stream(
            "GET",
            FEED_URLS[source],
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        ) as response:
            if response.status_code != 200:
                raise FeedError(f"Feed returned HTTP {response.status_code}")
            declared = response.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > MAX_RESPONSE_BYTES:
                raise FeedError("Feed response is too large")
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise FeedError("Feed response is too large")
                if time.monotonic() - started > MAX_TOTAL_SECONDS:
                    raise FeedError("Feed request timed out")
                chunks.append(chunk)
    except httpx.TimeoutException:
        raise FeedError("Feed request timed out") from None
    except httpx.HTTPError:
        raise FeedError("Feed request failed") from None
    return b"".join(chunks)


def as_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.replace("\x00", "").strip()
    return cleaned or None


def clip(value, limit: int = MAX_FIELD_LENGTH) -> str | None:
    text = as_text(value)
    if text is None:
        return None
    return text[:limit].strip() or None


def parse_date(value) -> datetime | None:
    text = as_text(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def build_job(source, title, company, url, published, description, location) -> FeedJob | None:
    clean_title = clip(title)
    link = as_text(url)
    if clean_title is None or link is None or len(link) > MAX_URL_LENGTH:
        return None
    try:
        parts = urlsplit(link)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return None
        normalized = normalize_url(link)
    except ValueError:
        return None
    return FeedJob(
        source=source,
        title=clean_title,
        company=clip(company),
        url=link,
        url_normalized=normalized,
        published=parse_date(published),
        description=clean_description(as_text(description)),
        location=clip(location),
    )


def collect(result: ParsedFeed, job: FeedJob | None) -> None:
    if job is None:
        result.skipped += 1
    else:
        result.jobs.append(job)


def load_json(raw: bytes):
    try:
        return json.loads(raw)
    except (ValueError, RecursionError):
        raise FeedError("Feed is not valid JSON") from None


def parse_weworkremotely(raw: bytes) -> ParsedFeed:
    if b"<!ENTITY" in raw:
        raise FeedError("Feed contains unsupported XML entities")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise FeedError("Feed is not valid XML") from None
    result = ParsedFeed()
    for item in root.iter("item"):
        full_title = as_text(item.findtext("title"))
        company = None
        title = full_title
        if full_title and ": " in full_title:
            head, tail = full_title.split(": ", 1)
            if head.strip() and tail.strip():
                company, title = head, tail
        places = [as_text(item.findtext("region")), as_text(item.findtext("country"))]
        location = ", ".join(dict.fromkeys(p for p in places if p)) or None
        collect(
            result,
            build_job(
                "weworkremotely",
                title,
                company,
                item.findtext("link"),
                item.findtext("pubDate"),
                item.findtext("description"),
                location,
            ),
        )
    return result


def parse_remoteok(raw: bytes) -> ParsedFeed:
    data = load_json(raw)
    if not isinstance(data, list):
        raise FeedError("Unexpected feed format")
    result = ParsedFeed()
    for item in data:
        if not isinstance(item, dict):
            result.skipped += 1
            continue
        if "legal" in item:
            continue
        collect(
            result,
            build_job(
                "remoteok",
                item.get("position"),
                item.get("company"),
                item.get("url"),
                item.get("date"),
                item.get("description"),
                item.get("location"),
            ),
        )
    return result


def parse_remotive(raw: bytes) -> ParsedFeed:
    data = load_json(raw)
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        raise FeedError("Unexpected feed format")
    result = ParsedFeed()
    for item in jobs:
        if not isinstance(item, dict):
            result.skipped += 1
            continue
        collect(
            result,
            build_job(
                "remotive",
                item.get("title"),
                item.get("company_name"),
                item.get("url"),
                item.get("publication_date"),
                item.get("description"),
                item.get("candidate_required_location"),
            ),
        )
    return result


PARSERS = {
    "weworkremotely": parse_weworkremotely,
    "remoteok": parse_remoteok,
    "remotive": parse_remotive,
}
