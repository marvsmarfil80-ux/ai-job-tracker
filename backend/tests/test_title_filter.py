import json
import re
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.db import SessionLocal, engine
from app.models import Job
from app.services.title_filter import (
    EXCLUDE_REASON,
    NO_INCLUDE_REASON,
    FilterSettings,
    apply_title_filter,
    load_filter_settings,
    title_filter_reason,
)

SEED_EXCLUDE_REGEX = (
    "senior|director|head of|principal|vice president|manager|architect|"
    "(?<![a-z])staff(?![a-z])|recruiter|sales|nurse|physician|"
    "(?<!non-)(?<!non )(?<!non)voice|call center|(?<![a-z])lead(?![a-z])"
)
SEED_INCLUDE_KEYWORDS = ["assistant", "data entry", "support", "admin", "junior", "entry", "automation"]
SEED_FILE = Path(__file__).resolve().parents[2] / "scripts" / "seed.sql"


def set_setting(key, value):
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into settings (key, value) values (:key, cast(:value as jsonb)) "
                "on conflict (key) do update set value = excluded.value"
            ),
            {"key": key, "value": json.dumps(value)},
        )


def make_settings():
    return FilterSettings(
        exclude=re.compile(SEED_EXCLUDE_REGEX, re.IGNORECASE),
        include_keywords=tuple(SEED_INCLUDE_KEYWORDS),
    )


@pytest.fixture(autouse=True)
def seed_filter_settings():
    set_setting("title_exclude_regex", SEED_EXCLUDE_REGEX)
    set_setting("title_include_keywords", SEED_INCLUDE_KEYWORDS)
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def remotive_keywords():
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into sources (name, badge, keywords) "
                "values ('remotive', 'Remotive', array['python']) "
                "on conflict (name) do update set keywords = excluded.keywords"
            )
        )
    yield
    with engine.begin() as connection:
        connection.execute(text("update sources set keywords = '{}' where name = 'remotive'"))


def insert_job(db, title, slug, source="remotive", priority=0, status="new"):
    url = f"https://example.com/p5b/{slug}"
    job = Job(
        source=source,
        title=title,
        company="Acme",
        url=url,
        url_normalized=url,
        priority=priority,
        pipeline_status=status,
    )
    db.add(job)
    db.commit()
    return job.id


def state_of(db, job_id):
    return db.execute(
        text("select pipeline_status, filter_reason from jobs where id = :id"),
        {"id": job_id},
    ).one()


@pytest.mark.parametrize(
    "title",
    [
        "Senior Python Developer",
        "Head of Support",
        "Call Center Agent",
        "Voice Support Agent",
        "Team Lead",
        "Lead Engineer",
        "Sales Assistant",
        "Staff Engineer",
        "SENIOR admin",
    ],
)
def test_exclude_pattern_filters_title(title):
    assert title_filter_reason(title, 0, make_settings()) == EXCLUDE_REASON


@pytest.mark.parametrize(
    "title",
    ["Non-Voice Customer Support", "Non Voice Support Agent", "Nonvoice Chat Support"],
)
def test_non_voice_titles_are_not_excluded(title):
    assert title_filter_reason(title, 0, make_settings()) is None


@pytest.mark.parametrize(
    "title",
    ["Virtual Assistant", "Data Entry Clerk", "Junior Python Developer", "ADMIN Officer"],
)
def test_include_keyword_passes_title(title):
    assert title_filter_reason(title, 0, make_settings()) is None


@pytest.mark.parametrize("title", ["Python Developer", "Backend Engineer"])
def test_title_without_include_keyword_is_filtered(title):
    assert title_filter_reason(title, 0, make_settings()) == NO_INCLUDE_REASON


@pytest.mark.parametrize("title", ["Senior Director of Sales", "Python Developer"])
def test_priority_one_bypasses_both_rules(title):
    assert title_filter_reason(title, 1, make_settings()) is None


def test_extra_source_keywords_are_used():
    settings = make_settings()
    assert title_filter_reason("Python Developer", 0, settings, ["python"]) is None
    assert title_filter_reason("Python Developer", 0, settings, ["  "]) == NO_INCLUDE_REASON


def test_apply_title_filter_updates_only_new_jobs(db):
    excluded = insert_job(db, "Senior Support Specialist", "a")
    no_keyword = insert_job(db, "Python Developer", "b")
    passed = insert_job(db, "Virtual Assistant", "c")
    manual = insert_job(db, "Senior Python Developer", "d", source="manual", priority=1)
    already_scored = insert_job(db, "Senior Manager", "e", status="scored")

    result = apply_title_filter(db)

    assert result == {"checked": 4, "filtered_out": 2, "passed": 2}
    assert state_of(db, excluded) == ("filtered_out", EXCLUDE_REASON)
    assert state_of(db, no_keyword) == ("filtered_out", NO_INCLUDE_REASON)
    assert state_of(db, passed) == ("new", None)
    assert state_of(db, manual) == ("new", None)
    assert state_of(db, already_scored) == ("scored", None)


def test_apply_title_filter_uses_source_keywords(db, remotive_keywords):
    from_remotive = insert_job(db, "Python Developer", "r", source="remotive")
    from_remoteok = insert_job(db, "Python Developer", "o", source="remoteok")

    apply_title_filter(db)

    assert state_of(db, from_remotive) == ("new", None)
    assert state_of(db, from_remoteok) == ("filtered_out", NO_INCLUDE_REASON)


def test_apply_title_filter_is_repeatable(db):
    insert_job(db, "Senior Manager", "x")
    assert apply_title_filter(db)["filtered_out"] == 1
    assert apply_title_filter(db) == {"checked": 0, "filtered_out": 0, "passed": 0}


@pytest.mark.parametrize(
    "key, value",
    [
        ("title_exclude_regex", "(unclosed"),
        ("title_exclude_regex", ""),
        ("title_exclude_regex", 5),
        ("title_include_keywords", []),
        ("title_include_keywords", ["  "]),
        ("title_include_keywords", "support"),
        ("title_include_keywords", ["support", 3]),
    ],
)
def test_invalid_settings_raise_clear_error(db, key, value):
    set_setting(key, value)
    with pytest.raises(HTTPException) as error:
        load_filter_settings(db)
    assert error.value.status_code == 500
    assert key in error.value.detail


def test_seed_file_contains_the_tested_default_regex():
    assert SEED_EXCLUDE_REGEX in SEED_FILE.read_text(encoding="utf-8")