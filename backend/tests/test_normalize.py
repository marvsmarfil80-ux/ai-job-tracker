import pytest

from app.services.normalize import normalize_url


def test_scheme_and_host_are_lowercased():
    assert normalize_url("HTTPS://Example.COM/Jobs/1") == "https://example.com/Jobs/1"


def test_fragment_is_removed():
    assert normalize_url("https://example.com/jobs/1#apply") == "https://example.com/jobs/1"


def test_trailing_slash_is_removed_but_root_is_kept():
    assert normalize_url("https://example.com/jobs/1/") == "https://example.com/jobs/1"
    assert normalize_url("https://example.com/") == "https://example.com/"
    assert normalize_url("https://example.com") == "https://example.com/"


@pytest.mark.parametrize(
    "param",
    ["utm_source=x", "utm_medium=y", "ref=home", "fbclid=abc", "gclid=abc", "trk=feed", "trackingId=abc", "refId=abc"],
)
def test_tracking_params_are_removed(param):
    assert normalize_url(f"https://example.com/jobs/1?{param}") == "https://example.com/jobs/1"


def test_other_query_params_are_kept_and_sorted():
    result = normalize_url("https://example.com/jobs?id=7&b=2&a=1&utm_source=x")
    assert result == "https://example.com/jobs?a=1&b=2&id=7"


def test_same_job_with_different_tracking_is_equal():
    first = normalize_url("https://example.com/jobs/1/?utm_source=a#top")
    second = normalize_url("https://EXAMPLE.com/jobs/1?fbclid=zzz")
    assert first == second


def test_linkedin_view_url_is_normalized():
    expected = "https://www.linkedin.com/jobs/view/123456/"
    assert normalize_url("https://www.linkedin.com/jobs/view/123456/?trk=email&refId=abc") == expected
    assert normalize_url("https://linkedin.com/comm/jobs/view/123456?trackingId=x") == expected
    assert normalize_url("http://www.linkedin.com/comm/jobs/view/123456/") == expected


def test_non_job_linkedin_url_uses_general_rules():
    assert normalize_url("https://www.linkedin.com/company/acme/?trk=x") == "https://www.linkedin.com/company/acme"
