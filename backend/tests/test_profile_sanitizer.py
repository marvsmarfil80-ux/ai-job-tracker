import pytest

from app.services.profile_sanitizer import (
    ADDRESS_WARNING,
    MAX_OUTPUT_CHARS,
    REMOVED,
    address_warnings,
    sanitize_profile,
)


def test_removes_email():
    result = sanitize_profile("Reach me at test@example.com for work")
    assert result.text == f"Reach me at {REMOVED} for work"
    assert result.emails == 1
    assert result.phones == 0
    assert result.lines == 0


@pytest.mark.parametrize(
    "raw",
    [
        "+63 900 555 0100",
        "0900-555-0100",
        "(02) 5550 0100",
        "555-0100",
        "09005550100",
        "+1 (555) 010-0100",
    ],
)
def test_removes_phone_forms(raw):
    result = sanitize_profile(f"Call {raw} anytime")
    assert result.text == f"Call {REMOVED} anytime"
    assert result.phones == 1


def test_keeps_short_numbers_and_versions():
    content = "Python 3.12, 4 projects, 120 users, 6 months"
    result = sanitize_profile(content)
    assert result.text == content
    assert result.phones == 0


def test_keeps_year_ranges():
    content = "Worked 2020-2024 on internal APIs"
    result = sanitize_profile(content)
    assert result.text == content
    assert result.phones == 0


def test_removes_label_lines():
    content = (
        "Name line\n"
        "Address: 1 Fake Road\n"
        "PHONE - 555-0100\n"
        "mobile: none\n"
        "Email: test@example.com\n"
        "  contact: someone\n"
        "Tel: 5\n"
        "Skills: Python"
    )
    result = sanitize_profile(content)
    assert result.text == "Name line\nSkills: Python"
    assert result.lines == 6
    assert result.emails == 0
    assert result.phones == 0


def test_keeps_lines_that_only_start_with_similar_words():
    content = "Email automation with n8n\nTelegram: bot projects\nContactless payments demo"
    result = sanitize_profile(content)
    assert result.text == content
    assert result.lines == 0


def test_keeps_urls():
    content = "GitHub: https://github.com/example-user\nPortfolio: portfolio.example.com/me"
    result = sanitize_profile(content)
    assert result.text == content
    assert result.emails == 0
    assert result.phones == 0


def test_counts_each_kind():
    content = (
        "Phone: 555-0100\n"
        "Mail test@example.com and other@example.org\n"
        "Call 0900-555-0100\n"
        "Skills: Python"
    )
    result = sanitize_profile(content)
    assert (result.emails, result.phones, result.lines) == (2, 1, 1)
    assert "@" not in result.text
    assert "555" not in result.text


def test_empty_input():
    result = sanitize_profile("")
    assert result.text == ""
    assert (result.emails, result.phones, result.lines) == (0, 0, 0)


def test_is_idempotent():
    once = sanitize_profile("Mail test@example.com, call 555-0100\nSkills: Python")
    twice = sanitize_profile(once.text)
    assert twice.text == once.text
    assert (twice.emails, twice.phones, twice.lines) == (0, 0, 0)


def test_result_never_exceeds_limit_after_replacements():
    result = sanitize_profile("5550100\n" * 400)
    assert result.phones == 400
    assert len(result.text) <= MAX_OUTPUT_CHARS


def test_result_never_exceeds_limit_for_plain_text():
    result = sanitize_profile("a" * 5000)
    assert len(result.text) == MAX_OUTPUT_CHARS


@pytest.mark.parametrize(
    "word",
    ["street", "St.", "Brgy", "barangay", "Avenue", "Subdivision", "City"],
)
def test_address_warning_words(word):
    assert address_warnings(f"I live near {word} somewhere") == [ADDRESS_WARNING]


def test_no_address_warning_for_plain_text():
    assert address_warnings("Python developer building automation with n8n") == []
    assert address_warnings("Streaming pipelines and capacity planning") == []
