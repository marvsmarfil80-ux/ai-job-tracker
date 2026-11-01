import re
from email.utils import parseaddr

from sqlalchemy import text
from sqlalchemy.orm import Session

MIN_COMPANY_CHARS = 3
MAX_ADDRESS_CHARS = 200
NON_WORD = re.compile(r"[\W_]+")

SELECT_CANDIDATES = text(
    "select a.id, a.status, j.title, j.company "
    "from applications a join jobs j on j.id = a.job_id "
    "where a.status <> 'withdrawn' and j.company is not null "
    "order by a.id"
)
SELECT_ALLOWED = text(
    "select 1 from allowed_senders "
    "where lower(sender) = :sender and kind = :kind and enabled limit 1"
)


def normalize_text(value: str | None) -> str:
    return NON_WORD.sub(" ", (value or "").lower()).strip()


def company_matches(company: str | None, haystack: str) -> bool:
    name = normalize_text(company)
    if len(name) < MIN_COMPANY_CHARS:
        return False
    return f" {name} " in f" {haystack} "


def find_candidates(db: Session, subject: str | None, snippet: str | None) -> list[dict]:
    haystack = normalize_text(f"{subject or ''} {snippet or ''}")
    rows = db.execute(SELECT_CANDIDATES).mappings().all()
    return [dict(row) for row in rows if company_matches(row["company"], haystack)]


def extract_address(sender: str | None) -> str:
    if not sender:
        return ""
    address = parseaddr(sender[:500])[1].strip().lower()
    if "@" not in address or len(address) > MAX_ADDRESS_CHARS:
        return ""
    if any(character.isspace() for character in address):
        return ""
    return address


def sender_is_allowed(db: Session, sender: str | None, kind: str) -> bool:
    address = extract_address(sender)
    if not address:
        return False
    row = db.execute(SELECT_ALLOWED, {"sender": address, "kind": kind}).first()
    return row is not None