import pytest

from app.db import SessionLocal
from app.services.email_matching import (
    extract_address,
    find_candidates,
    normalize_text,
    sender_is_allowed,
)
from tests.email_helpers import add_allowed_sender, make_application


def candidate_ids(subject, snippet=""):
    with SessionLocal() as db:
        return [row["id"] for row in find_candidates(db, subject, snippet)]


def allowed(sender, kind="application"):
    with SessionLocal() as db:
        return sender_is_allowed(db, sender, kind)


def test_single_candidate_is_found_in_subject():
    application_id = make_application("Example Corp")
    assert candidate_ids("Update from Example Corp") == [application_id]


def test_match_is_case_and_punctuation_insensitive():
    application_id = make_application("Acme, Inc.")
    assert candidate_ids("Your application to ACME INC!") == [application_id]


def test_company_can_be_found_in_snippet():
    application_id = make_application("Example Corp")
    assert candidate_ids("Application update", "Thanks for applying to Example Corp today") == [
        application_id
    ]


def test_no_match_gives_no_candidates():
    make_application("Example Corp")
    assert candidate_ids("Weekly newsletter", "Nothing here") == []


def test_two_applications_with_the_same_company_are_both_candidates():
    first = make_application("Example Corp", title="Support Agent")
    second = make_application("Example Corp", title="Data Entry Clerk")
    assert candidate_ids("News from Example Corp") == [first, second]


def test_short_company_names_are_not_matched():
    make_application("AB")
    assert candidate_ids("AB team update", "AB") == []


def test_withdrawn_applications_are_not_candidates():
    make_application("Example Corp", status="withdrawn")
    assert candidate_ids("Update from Example Corp") == []


def test_rejected_applications_are_still_candidates():
    application_id = make_application("Example Corp", status="rejected")
    assert candidate_ids("Update from Example Corp") == [application_id]


def test_only_whole_words_match():
    make_application("Acme")
    assert candidate_ids("Acmeville update", "Acmes and Superacme") == []


def test_normalize_text():
    assert normalize_text("Acme, Inc.!") == "acme inc"
    assert normalize_text(None) == ""
    assert normalize_text("  A_B  ") == "a b"


@pytest.mark.parametrize(
    "sender,expected",
    [
        ("Recruiter <Jobs@Example.com>", "jobs@example.com"),
        ("jobs@example.com", "jobs@example.com"),
        ("  HR@EXAMPLE.COM ", "hr@example.com"),
        ("not an address", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_extract_address(sender, expected):
    assert extract_address(sender) == expected


def test_sender_allowed_uses_the_exact_address():
    add_allowed_sender("jobs@example.com")
    assert allowed("Recruiter <Jobs@Example.com>") is True
    assert allowed("jobs@example.com") is True


def test_sender_not_listed_is_not_allowed():
    add_allowed_sender("jobs@example.com")
    assert allowed("other@example.com") is False
    assert allowed("jobs@example.com.evil.example.org") is False
    assert allowed("x@jobs@example.com") is False


def test_domain_entry_does_not_allow_every_address():
    add_allowed_sender("example.com")
    assert allowed("jobs@example.com") is False


def test_disabled_sender_is_not_allowed():
    add_allowed_sender("jobs@example.com", enabled=False)
    assert allowed("jobs@example.com") is False


def test_sender_kind_must_match():
    add_allowed_sender("jobs@example.com", kind="job_alert")
    assert allowed("jobs@example.com", kind="application") is False
    assert allowed("jobs@example.com", kind="job_alert") is True


def test_empty_sender_is_not_allowed():
    assert allowed("") is False
    assert allowed(None) is False