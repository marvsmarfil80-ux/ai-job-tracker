import pytest

from app.services.email_status_rules import decide, transition_allowed


def run(**overrides):
    values = {
        "label": "interview",
        "confidence": 90,
        "current_status": "applied",
        "auto_enabled": True,
        "min_confidence": 85,
        "sender_allowed": True,
    }
    values.update(overrides)
    return decide(**values)


@pytest.mark.parametrize(
    "label,current,expected",
    [
        ("interview", "applied", "interview"),
        ("interview", "under_review", "interview"),
        ("assessment", "applied", "assessment"),
        ("assessment", "under_review", "assessment"),
        ("rejection", "applied", "rejected"),
        ("rejection", "under_review", "rejected"),
        ("rejection", "assessment", "rejected"),
        ("rejection", "interview", "rejected"),
        ("offer", "applied", "offer"),
        ("offer", "interview", "offer"),
    ],
)
def test_allowed_changes(label, current, expected):
    decision = run(label=label, current_status=current)
    assert decision.action == "change"
    assert decision.new_status == expected
    assert decision.reason is None


def test_confirmation_never_changes_status():
    decision = run(label="confirmation")
    assert decision.action == "none"
    assert decision.new_status is None


def test_unknown_label_does_nothing():
    assert run(label="unknown").action == "none"


def test_info_request_is_a_review_even_with_low_confidence():
    decision = run(label="info_request", confidence=10, auto_enabled=False)
    assert decision.action == "review"
    assert decision.reason == "Information requested"


def test_confidence_equal_to_minimum_is_allowed():
    assert run(confidence=85).action == "change"


def test_low_confidence_needs_review():
    decision = run(confidence=84)
    assert decision.action == "review"
    assert decision.reason == "Low confidence"


def test_auto_status_disabled_needs_review():
    decision = run(auto_enabled=False)
    assert decision.action == "review"
    assert decision.reason == "Auto status is disabled"


def test_sender_not_allowed_needs_review():
    decision = run(sender_allowed=False)
    assert decision.action == "review"
    assert decision.reason == "Sender is not allowed"


@pytest.mark.parametrize(
    "label,current",
    [
        ("assessment", "interview"),
        ("interview", "offer"),
        ("assessment", "offer"),
        ("rejection", "offer"),
        ("interview", "rejected"),
        ("offer", "rejected"),
        ("rejection", "withdrawn"),
        ("interview", "withdrawn"),
        ("offer", "withdrawn"),
    ],
)
def test_backward_or_terminal_changes_need_review(label, current):
    decision = run(label=label, current_status=current)
    assert decision.action == "review"
    assert decision.reason == "Status change not allowed"


@pytest.mark.parametrize(
    "label,current",
    [
        ("interview", "interview"),
        ("assessment", "assessment"),
        ("rejection", "rejected"),
        ("offer", "offer"),
    ],
)
def test_same_status_does_nothing_even_when_auto_is_off(label, current):
    decision = run(label=label, current_status=current, auto_enabled=False, sender_allowed=False)
    assert decision.action == "none"
    assert decision.reason is None


def test_transition_allowed_unknown_status_is_false():
    assert transition_allowed("applied", "mystery") is False
    assert transition_allowed("mystery", "interview") is False