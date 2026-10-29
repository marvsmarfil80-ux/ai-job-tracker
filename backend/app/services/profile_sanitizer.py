import re
from dataclasses import dataclass

REMOVED = "[removed]"
MAX_OUTPUT_CHARS = 2000
MIN_PHONE_DIGITS = 7
ADDRESS_WARNING = "The text may contain an address. Remove it before use."

_LABEL_LINE = re.compile(
    r"^[ \t]*(?:address|phone|mobile|email|contact|tel)[ \t]*[:\-]", re.IGNORECASE
)
_EMAIL = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}"
)
_PHONE = re.compile(r"(?<!\w)\+?\(?\d[\d \t\-()]*\d(?!\w)")
_YEAR_RANGE = re.compile(r"(?:19|20)\d{2}[ \t]*-[ \t]*(?:19|20)\d{2}")
_ADDRESS_WORDS = re.compile(
    r"(?<!\w)(?:street|st\.|brgy|barangay|avenue|subdivision|city)(?!\w)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SanitizeResult:
    text: str
    emails: int
    phones: int
    lines: int


def _remove_phones(text: str) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        value = match.group(0)
        if sum(char.isdigit() for char in value) < MIN_PHONE_DIGITS:
            return value
        if _YEAR_RANGE.fullmatch(value):
            return value
        count += 1
        return REMOVED

    return _PHONE.sub(replace, text), count


def sanitize_profile(content: str) -> SanitizeResult:
    kept = []
    removed_lines = 0
    for line in content.splitlines():
        if _LABEL_LINE.match(line):
            removed_lines += 1
        else:
            kept.append(line)
    text = "\n".join(kept)
    text, emails = _EMAIL.subn(REMOVED, text)
    text, phones = _remove_phones(text)
    text = text.strip()[:MAX_OUTPUT_CHARS].strip()
    return SanitizeResult(text=text, emails=emails, phones=phones, lines=removed_lines)


def address_warnings(text: str) -> list[str]:
    if _ADDRESS_WORDS.search(text):
        return [ADDRESS_WARNING]
    return []
