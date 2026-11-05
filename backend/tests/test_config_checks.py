import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.settings import DEFAULTS, KEYS

SEED = Path(__file__).resolve().parents[2] / "scripts" / "seed.sql"
ALLOWED = "http://localhost:5173"
ALLOWED_ALT = "http://127.0.0.1:5173"
DISALLOWED = "https://example.com"
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
CASES = [("PUT", "/profile"), ("PATCH", "/follow-ups/1"), ("DELETE", "/follow-ups/1")]


def read_seed():
    return SEED.read_text()


def test_seed_has_no_min_score():
    assert "min_score" not in read_seed()


def test_seed_has_19_unique_keywords():
    match = re.search(r"'title_include_keywords', '(\[.*?\])'::jsonb", read_seed())
    assert match is not None
    keywords = json.loads(match.group(1))
    assert len(keywords) == 19
    assert len(set(keywords)) == 19
    assert "developer" in keywords
    assert "tester" in keywords


def test_seed_daily_score_cap_matches_defaults():
    assert "('daily_score_cap', '100'::jsonb)" in read_seed()
    assert DEFAULTS["daily_score_cap"] == 100


def test_seed_only_uses_known_setting_keys():
    keys = re.findall(r"^\s+\('([a-z_]+)',.*jsonb", read_seed(), re.M)
    assert len(keys) == 16
    assert set(keys) <= set(KEYS)


def test_seed_ends_with_conflict_clause_and_newline():
    assert read_seed().endswith("ON CONFLICT (key) DO NOTHING;\n")


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def preflight(client, origin, method, path):
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "X-API-Key, Content-Type",
        },
    )


@pytest.mark.parametrize("origin", [ALLOWED, ALLOWED_ALT])
@pytest.mark.parametrize("method,path", CASES)
def test_preflight_from_allowed_origin_is_accepted(client, origin, method, path):
    response = preflight(client, origin, method, path)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    allowed_methods = [item.strip() for item in response.headers["access-control-allow-methods"].split(",")]
    assert method in allowed_methods
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "x-api-key" in allowed_headers
    assert "content-type" in allowed_headers
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize("method,path", CASES)
def test_preflight_from_other_origin_is_not_allowed(client, method, path):
    response = preflight(client, DISALLOWED, method, path)
    assert "access-control-allow-origin" not in response.headers
    assert response.status_code != 200


def test_allowed_methods_are_the_explicit_list(client):
    response = preflight(client, ALLOWED, "PUT", "/profile")
    methods = {item.strip() for item in response.headers["access-control-allow-methods"].split(",")}
    assert methods == METHODS


def test_no_wildcard_origin_and_no_credentials(client):
    config = get_settings()
    assert config.cors_origins == [ALLOWED, ALLOWED_ALT]
    assert "*" not in config.cors_origins
    response = preflight(client, ALLOWED, "PUT", "/profile")
    assert response.headers["access-control-allow-origin"] != "*"
    actual = client.get("/health", headers={"Origin": ALLOWED})
    assert actual.headers["access-control-allow-origin"] == ALLOWED
    assert "access-control-allow-credentials" not in actual.headers