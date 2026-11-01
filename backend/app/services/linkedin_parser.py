import re
from dataclasses import dataclass
from html.parser import HTMLParser

from app.services.normalize import normalize_url

MAX_JOBS = 50
MAX_FIELD_CHARS = 200
MAX_HTML_CHARS = 2_000_000
SEPARATOR = "\x1f"
CANONICAL_PREFIX = "https://www.linkedin.com/jobs/view/"

JOB_LINK = re.compile(
    r"^https?://(?:[a-z0-9-]+\.)*linkedin\.com/(?:comm/)?jobs/view/\d{1,20}/?(?:[?#].*)?$",
    re.IGNORECASE,
)
WORK_MODE_PATTERN = re.compile(
    r"\s*\((remote|hybrid|on-site|on site|onsite)\)\s*$", re.IGNORECASE
)
WORK_MODES = {
    "remote": "remote",
    "hybrid": "hybrid",
    "on-site": "on_site",
    "on site": "on_site",
    "onsite": "on_site",
}
HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|mso-hide\s*:\s*all"
    r"|max-height\s*:\s*0|font-size\s*:\s*0(?:px|pt|em|%)?\s*(?:;|$)"
    r"|opacity\s*:\s*0(?:\.0+)?\s*(?:;|$)",
    re.IGNORECASE,
)
NEWLINE_SPACE = re.compile(r"\s*[\r\n\t\f\v]\s*")
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
INVISIBLE_CHARS = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
WIDE_GAP = re.compile(r" {2,}")

GENERIC_LINK_TEXT = {
    "view job",
    "view jobs",
    "view",
    "view details",
    "see job",
    "apply",
    "apply now",
}
BLOCK_TAGS = {
    "p", "div", "li", "ul", "ol", "tr", "td", "th", "table", "tbody", "thead",
    "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "body", "center",
}
INLINE_TAGS = {"span", "a", "b", "strong", "em", "i", "u", "font"}
VOID_TAGS = {
    "br", "img", "meta", "link", "input", "hr", "area", "base", "col",
    "embed", "source", "track", "wbr",
}
SKIP_TAGS = {"script", "style", "head", "title", "template", "noscript"}


class LinkedInParseError(Exception):
    pass


@dataclass(frozen=True)
class ParsedJob:
    title: str
    company: str | None
    location: str | None
    work_mode: str | None
    url: str


@dataclass(frozen=True)
class ParseResult:
    jobs: tuple[ParsedJob, ...]
    skipped: int
    truncated: bool


@dataclass(frozen=True)
class _Line:
    parts: tuple[str, ...]
    url: str | None


def _job_url(href: str | None) -> str | None:
    if not href:
        return None
    cleaned = href.strip()
    if len(cleaned) > 2000 or not JOB_LINK.match(cleaned):
        return None
    normalized = normalize_url(cleaned)
    if not normalized.startswith(CANONICAL_PREFIX):
        return None
    return normalized


def _split_parts(raw: str) -> tuple[str, ...]:
    pieces: list[str] = []
    for chunk in raw.split(SEPARATOR):
        chunk = chunk.replace("\xa0", " ")
        chunk = NEWLINE_SPACE.sub(" ", chunk)
        chunk = CONTROL_CHARS.sub("", chunk)
        chunk = INVISIBLE_CHARS.sub("", chunk)
        for piece in WIDE_GAP.split(chunk):
            piece = piece.strip()
            if piece:
                pieces.append(piece)
    return tuple(pieces)


def _is_hidden(attrs: list[tuple[str, str | None]]) -> bool:
    for name, value in attrs:
        if name == "hidden":
            return True
        if name == "style" and value and HIDDEN_STYLE.search(value):
            return True
    return False


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[_Line] = []
        self.buffer: list[str] = []
        self.stack: list[tuple[str, bool]] = []
        self.hidden = 0
        self.pending_url: str | None = None

    def flush(self) -> None:
        parts = _split_parts("".join(self.buffer))
        self.buffer = []
        if parts:
            self.lines.append(_Line(parts, self.pending_url))
            self.pending_url = None

    def close_anchor(self) -> None:
        if self.pending_url is None:
            return
        if not _split_parts("".join(self.buffer)):
            self.lines.append(_Line((), self.pending_url))
            self.pending_url = None
            self.buffer = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            if tag == "br" and not self.hidden:
                self.flush()
            return
        hides = tag in SKIP_TAGS or _is_hidden(attrs)
        self.stack.append((tag, hides))
        if hides:
            self.hidden += 1
        if self.hidden:
            return
        if tag in BLOCK_TAGS:
            self.flush()
        if tag in INLINE_TAGS:
            self.buffer.append(SEPARATOR)
        if tag == "a" and self.pending_url is None:
            self.pending_url = _job_url(dict(attrs).get("href"))

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        index = None
        for position in range(len(self.stack) - 1, -1, -1):
            if self.stack[position][0] == tag:
                index = position
                break
        if index is None:
            return
        popped = self.stack[index:]
        del self.stack[index:]
        for _, hides in popped:
            if hides:
                self.hidden -= 1
        if self.hidden:
            return
        if tag in INLINE_TAGS:
            self.buffer.append(SEPARATOR)
        if tag == "a":
            self.close_anchor()
        if tag in BLOCK_TAGS:
            self.flush()

    def handle_data(self, data):
        if not self.hidden:
            self.buffer.append(data)


def _limit(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:MAX_FIELD_CHARS].strip() or None


def _parse_meta(line: _Line | None) -> tuple[str | None, str | None, str | None]:
    if line is None or not line.parts:
        return None, None, None
    parts = list(line.parts)
    work_mode = None
    match = WORK_MODE_PATTERN.search(parts[-1])
    if match:
        work_mode = WORK_MODES[match.group(1).lower()]
        parts[-1] = parts[-1][: match.start()].strip()
    parts = [part for part in parts if part]
    if not parts:
        return None, None, work_mode
    company = parts[0]
    location = " ".join(parts[1:]) or None
    return _limit(company), _limit(location), work_mode


def _extract(lines: list[_Line]) -> ParseResult:
    jobs: list[ParsedJob] = []
    seen: set[str] = set()
    skipped = 0
    truncated = False
    for index, line in enumerate(lines):
        if line.url is None or line.url in seen:
            continue
        if len(jobs) >= MAX_JOBS:
            truncated = True
            break
        seen.add(line.url)
        link_text = " ".join(line.parts)
        if not link_text:
            skipped += 1
            continue
        if link_text.lower() in GENERIC_LINK_TEXT:
            title_line = lines[index - 2] if index >= 2 else None
            meta_line = lines[index - 1] if index >= 1 else None
            if title_line is None or title_line.url is not None:
                skipped += 1
                continue
            title = " ".join(title_line.parts)
        else:
            title = link_text
            meta_line = lines[index + 1] if index + 1 < len(lines) else None
        if meta_line is not None and meta_line.url is not None:
            meta_line = None
        title = _limit(title)
        if title is None:
            skipped += 1
            continue
        company, location, work_mode = _parse_meta(meta_line)
        jobs.append(
            ParsedJob(
                title=title,
                company=company,
                location=location,
                work_mode=work_mode,
                url=line.url,
            )
        )
    return ParseResult(jobs=tuple(jobs), skipped=skipped, truncated=truncated)


def parse_linkedin_alert(html: str) -> ParseResult:
    if not isinstance(html, str) or not html.strip():
        raise LinkedInParseError("Email body is empty")
    if len(html) > MAX_HTML_CHARS:
        raise LinkedInParseError("Email body is too large")
    collector = _Collector()
    try:
        collector.feed(html)
        collector.close()
        collector.flush()
    except Exception:
        raise LinkedInParseError("Email body could not be parsed")
    result = _extract(collector.lines)
    if not result.jobs:
        raise LinkedInParseError("No jobs found in the alert email")
    return result