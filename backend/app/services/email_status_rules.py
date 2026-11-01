from dataclasses import dataclass

STATUS_RANK = {
    "applied": 0,
    "under_review": 1,
    "assessment": 2,
    "interview": 3,
    "offer": 4,
}
TERMINAL_STATUSES = frozenset({"rejected", "offer", "withdrawn"})
REJECTABLE_STATUSES = frozenset({"applied", "under_review", "assessment", "interview"})
CLASS_TO_STATUS = {
    "interview": "interview",
    "assessment": "assessment",
    "rejection": "rejected",
    "offer": "offer",
}

REASON_INFO_REQUESTED = "Information requested"
REASON_AUTO_DISABLED = "Auto status is disabled"
REASON_SENDER_NOT_ALLOWED = "Sender is not allowed"
REASON_LOW_CONFIDENCE = "Low confidence"
REASON_CHANGE_NOT_ALLOWED = "Status change not allowed"


@dataclass(frozen=True)
class Decision:
    action: str
    new_status: str | None = None
    reason: str | None = None


def transition_allowed(current_status: str, target_status: str) -> bool:
    if current_status in TERMINAL_STATUSES:
        return False
    if target_status == "rejected":
        return current_status in REJECTABLE_STATUSES
    if current_status not in STATUS_RANK or target_status not in STATUS_RANK:
        return False
    return STATUS_RANK[target_status] > STATUS_RANK[current_status]


def decide(
    label: str,
    confidence: int,
    current_status: str,
    auto_enabled: bool,
    min_confidence: int,
    sender_allowed: bool,
) -> Decision:
    if label == "info_request":
        return Decision("review", None, REASON_INFO_REQUESTED)
    target = CLASS_TO_STATUS.get(label)
    if target is None:
        return Decision("none")
    if current_status == target:
        return Decision("none")
    if not auto_enabled:
        return Decision("review", None, REASON_AUTO_DISABLED)
    if not sender_allowed:
        return Decision("review", None, REASON_SENDER_NOT_ALLOWED)
    if confidence < min_confidence:
        return Decision("review", None, REASON_LOW_CONFIDENCE)
    if not transition_allowed(current_status, target):
        return Decision("review", None, REASON_CHANGE_NOT_ALLOWED)
    return Decision("change", target)