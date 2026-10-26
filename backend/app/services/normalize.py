import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"ref", "fbclid", "gclid", "trk", "trackingid", "refid"}

LINKEDIN_JOB_PATH = re.compile(r"^/(?:comm/)?jobs/view/(\d+)/?$")


def _is_tracking_param(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith("utm_") or lowered in TRACKING_PARAMS


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = parts.netloc.lower()

    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        match = LINKEDIN_JOB_PATH.match(parts.path)
        if match:
            return f"https://www.linkedin.com/jobs/view/{match.group(1)}/"

    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"
    if not path:
        path = "/"

    pairs = [
        (name, value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_param(name)
    ]
    query = urlencode(sorted(pairs))

    return urlunsplit((scheme, host, path, query, ""))