import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.main import app
from app.services.jobs import get_thresholds
from app.services.title_filter import load_filter_settings

BASELINE = {
    "daily_score_cap": 150,
    "apply_threshold": 70,
    "maybe_threshold": 40,
    "min_score": 40,
    "title_exclude_regex": "senior|manager",
    "title_include_keywords": ["support", "admin"],
    "scheduler_enabled": False,
    "hunt_interval_hours": 6,
    "score_interval_minutes": 30,
    "score_batch_limit": 10,
    "followup_reminders_enabled": True,
    "email_auto_status_enabled": True,
    "email_auto_status_min_confidence": 85,
    "email_classify_daily_cap": 30,
}
PUBLIC_KEYS = sorted(key for key in BASELINE if key != "min_score")


def write_baseline():
    with engine.begin() as connection:
        for key, value in BASELINE.items():
            connection.execute(
                text(
                    "insert into settings (key, value) values (:key, cast(:value as jsonb)) "
                    "on conflict (key) do update set value = excluded.value"
                ),
                {"key": key, "value": json.dumps(value)},
            )


def read_db(key):
    with engine.connect() as connection:
        return connection.execute(
            text("select value from settings where key = :key"), {"key": key}
        ).scalar_one()


@pytest.fixture(autouse=True)
def baseline_settings():
    write_baseline()
    yield
    write_baseline()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def patch(client, headers, body):
    return client.patch("/settings", json=body, headers=headers)


def test_get_requires_key(client):
    assert client.get("/settings").status_code == 401


def test_patch_requires_key(client):
    response = client.patch("/settings", json={"daily_score_cap": 100})
    assert response.status_code == 401
    assert read_db("daily_score_cap") == 150


def test_get_lists_whitelisted_keys_only(client, headers):
    response = client.get("/settings", headers=headers)
    assert response.status_code == 200
    data = response.json()["settings"]
    assert sorted(data) == PUBLIC_KEYS
    assert "min_score" not in data
    assert data["daily_score_cap"]["value"] == 150
    assert data["scheduler_enabled"]["value"] is False
    assert all(item["description"] for item in data.values())


def test_patch_valid_change_is_saved_and_returned(client, headers):
    response = patch(
        client,
        headers,
        {"daily_score_cap": 120, "scheduler_enabled": True, "score_batch_limit": 3},
    )
    assert response.status_code == 200
    data = response.json()["settings"]
    assert data["daily_score_cap"]["value"] == 120
    assert data["scheduler_enabled"]["value"] is True
    assert data["score_batch_limit"]["value"] == 3
    assert read_db("daily_score_cap") == 120
    assert read_db("scheduler_enabled") is True
    again = client.get("/settings", headers=headers).json()["settings"]
    assert again["score_batch_limit"]["value"] == 3


def test_patch_swapping_both_thresholds_in_one_request(client, headers):
    response = patch(client, headers, {"apply_threshold": 90, "maybe_threshold": 60})
    assert response.status_code == 200
    assert read_db("apply_threshold") == 90
    assert read_db("maybe_threshold") == 60


def test_unknown_key_is_rejected(client, headers):
    response = patch(client, headers, {"not_a_setting": 1})
    assert response.status_code == 422


def test_min_score_is_not_changeable_and_not_written(client, headers):
    response = patch(client, headers, {"min_score": 90})
    assert response.status_code == 422
    assert read_db("min_score") == 40


def test_empty_body_is_rejected(client, headers):
    assert patch(client, headers, {}).status_code == 422


def test_null_value_is_rejected(client, headers):
    response = patch(client, headers, {"daily_score_cap": None})
    assert response.status_code == 422
    assert read_db("daily_score_cap") == 150


@pytest.mark.parametrize(
    "body",
    [
        {"apply_threshold": 40},
        {"apply_threshold": 30},
        {"maybe_threshold": 70},
        {"maybe_threshold": 80},
    ],
)
def test_apply_must_be_greater_than_maybe_using_final_state(client, headers, body):
    response = patch(client, headers, body)
    assert response.status_code == 422
    assert response.json()["detail"] == "apply_threshold must be greater than maybe_threshold"
    assert read_db("apply_threshold") == 70
    assert read_db("maybe_threshold") == 40


@pytest.mark.parametrize(
    "body",
    [
        {"daily_score_cap": 0},
        {"daily_score_cap": 301},
        {"apply_threshold": 0},
        {"apply_threshold": 101},
        {"maybe_threshold": -1},
        {"maybe_threshold": 100},
        {"hunt_interval_hours": 0},
        {"hunt_interval_hours": 25},
        {"score_interval_minutes": 4},
        {"score_interval_minutes": 241},
        {"score_batch_limit": 0},
        {"score_batch_limit": 21},
    ],
)
def test_out_of_range_values_are_rejected(client, headers, body):
    assert patch(client, headers, body).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"daily_score_cap": True},
        {"daily_score_cap": "100"},
        {"daily_score_cap": 100.5},
        {"scheduler_enabled": 1},
        {"scheduler_enabled": "true"},
        {"title_exclude_regex": 5},
        {"title_include_keywords": "support"},
        {"title_include_keywords": [1, 2]},
    ],
)
def test_wrong_types_are_rejected(client, headers, body):
    assert patch(client, headers, body).status_code == 422


@pytest.mark.parametrize(
    "value",
    ["", "   ", "(unclosed", "[a-", "a" * 501],
)
def test_bad_regex_is_rejected(client, headers, value):
    response = patch(client, headers, {"title_exclude_regex": value})
    assert response.status_code == 422
    assert read_db("title_exclude_regex") == "senior|manager"


def test_regex_of_exactly_500_chars_is_accepted(client, headers):
    value = "a" * 500
    assert patch(client, headers, {"title_exclude_regex": value}).status_code == 200
    assert read_db("title_exclude_regex") == value


@pytest.mark.parametrize(
    "value",
    [
        [],
        ["a"] * 2,
        ["Support", "support"],
        ["ok", ""],
        ["ok", "   "],
        ["x" * 51],
        [f"kw{number}" for number in range(51)],
    ],
)
def test_bad_keyword_lists_are_rejected(client, headers, value):
    response = patch(client, headers, {"title_include_keywords": value})
    assert response.status_code == 422
    assert read_db("title_include_keywords") == ["support", "admin"]


def test_keywords_are_trimmed_and_boundaries_accepted(client, headers):
    value = [" Alpha ", "x" * 50] + [f"kw{number}" for number in range(48)]
    response = patch(client, headers, {"title_include_keywords": value})
    assert response.status_code == 200
    stored = read_db("title_include_keywords")
    assert stored[0] == "Alpha"
    assert len(stored) == 50


def test_batch_with_one_invalid_value_writes_nothing(client, headers):
    response = patch(
        client,
        headers,
        {"daily_score_cap": 200, "scheduler_enabled": True, "hunt_interval_hours": 99},
    )
    assert response.status_code == 422
    assert read_db("daily_score_cap") == 150
    assert read_db("scheduler_enabled") is False
    assert read_db("hunt_interval_hours") == 6


def test_batch_failing_cross_field_check_writes_nothing(client, headers):
    response = patch(client, headers, {"daily_score_cap": 200, "apply_threshold": 30})
    assert response.status_code == 422
    assert read_db("daily_score_cap") == 150
    assert read_db("apply_threshold") == 70


def test_threshold_change_is_seen_by_get_thresholds(client, headers):
    assert patch(client, headers, {"apply_threshold": 80, "maybe_threshold": 50}).status_code == 200
    with SessionLocal() as session:
        assert get_thresholds(session) == (80, 50)


def test_title_filter_settings_change_is_seen_by_the_filter(client, headers):
    body = {"title_exclude_regex": "foo|bar", "title_include_keywords": [" Alpha ", "Beta"]}
    assert patch(client, headers, body).status_code == 200
    with SessionLocal() as session:
        loaded = load_filter_settings(session)
    assert loaded.exclude.search("a FOO b")
    assert loaded.include_keywords == ("alpha", "beta")


def test_get_returns_defaults_for_missing_scheduler_keys(client, headers):
    with engine.begin() as connection:
        connection.execute(
            text(
                "delete from settings where key in "
                "('scheduler_enabled', 'hunt_interval_hours', "
                "'score_interval_minutes', 'score_batch_limit')"
            )
        )
    data = client.get("/settings", headers=headers).json()["settings"]
    assert data["scheduler_enabled"]["value"] is False
    assert data["hunt_interval_hours"]["value"] == 6
    assert data["score_interval_minutes"]["value"] == 30
    assert data["score_batch_limit"]["value"] == 10


def test_get_shows_followup_reminders_setting(client, headers):
    response = client.get("/settings", headers=headers)
    assert response.status_code == 200
    item = response.json()["settings"]["followup_reminders_enabled"]
    assert item["value"] is True
    assert item["description"]


def test_followup_reminders_default_is_true_when_row_is_missing(client, headers):
    with engine.begin() as connection:
        connection.execute(
            text("delete from settings where key = 'followup_reminders_enabled'")
        )
    response = client.get("/settings", headers=headers)
    assert response.status_code == 200
    assert response.json()["settings"]["followup_reminders_enabled"]["value"] is True


def test_patch_followup_reminders_boolean_is_saved(client, headers):
    response = patch(client, headers, {"followup_reminders_enabled": False})
    assert response.status_code == 200
    assert response.json()["settings"]["followup_reminders_enabled"]["value"] is False
    assert read_db("followup_reminders_enabled") is False
    response = patch(client, headers, {"followup_reminders_enabled": True})
    assert response.status_code == 200
    assert read_db("followup_reminders_enabled") is True


@pytest.mark.parametrize("value", ["true", "false", 1, 0, None])
def test_patch_followup_reminders_rejects_non_boolean(client, headers, value):
    response = patch(client, headers, {"followup_reminders_enabled": value})
    assert response.status_code == 422
    assert read_db("followup_reminders_enabled") is True


def test_followup_reminders_is_part_of_the_atomic_patch(client, headers):
    response = patch(
        client, headers, {"followup_reminders_enabled": False, "daily_score_cap": 0}
    )
    assert response.status_code == 422
    assert read_db("followup_reminders_enabled") is True
    assert read_db("daily_score_cap") == 150
    response = patch(
        client, headers, {"followup_reminders_enabled": False, "score_batch_limit": 3}
    )
    assert response.status_code == 200
    assert read_db("followup_reminders_enabled") is False
    assert read_db("score_batch_limit") == 3