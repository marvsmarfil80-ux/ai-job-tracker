import logging
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine
from app.main import app
from app.services.profile import NOT_SET_DETAIL, get_profile_text

BACKEND_DIR = Path(__file__).resolve().parents[1]
SAMPLE = "Skills: Python basics, n8n automation"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def headers():
    return {"X-API-Key": get_settings().api_key.get_secret_value()}


def put(client, headers, content):
    return client.put("/profile", headers=headers, json={"content": content})


def test_get_empty_profile_returns_200(client, headers):
    response = client.get("/profile", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["content"] == ""
    assert body["char_count"] == 0
    assert body["groq_view"] == ""
    assert body["redactions"] == {"emails": 0, "phones": 0, "lines": 0}
    assert body["warnings"] == []


def test_put_then_get_round_trip(client, headers):
    response = put(client, headers, SAMPLE)
    assert response.status_code == 200
    body = response.json()
    assert body["content"] == SAMPLE
    assert body["char_count"] == len(SAMPLE)
    assert body["groq_view"] == SAMPLE
    assert body["updated_at"] is not None
    got = client.get("/profile", headers=headers).json()
    assert got["content"] == SAMPLE
    assert got["updated_at"] == body["updated_at"]


def test_put_strips_outer_whitespace(client, headers):
    response = put(client, headers, f"  \n{SAMPLE}\n  ")
    assert response.status_code == 200
    assert response.json()["content"] == SAMPLE


def test_put_replaces_whole_content_and_updates_timestamp(client, headers):
    first = put(client, headers, SAMPLE).json()
    second = put(client, headers, "Skills: SQL").json()
    assert second["content"] == "Skills: SQL"
    assert second["updated_at"] > first["updated_at"]
    with engine.begin() as connection:
        assert connection.execute(text("select count(*) from profile")).scalar_one() == 1


def test_stored_content_is_exact_and_groq_view_is_sanitized(client, headers):
    content = "Skills: Python\nPhone: 555-0100\nMail test@example.com or call 0900-555-0100"
    body = put(client, headers, content).json()
    assert body["content"] == content
    assert "test@example.com" in body["content"]
    assert "@" not in body["groq_view"]
    assert "555" not in body["groq_view"]
    assert "[removed]" in body["groq_view"]
    assert body["redactions"] == {"emails": 1, "phones": 1, "lines": 1}
    assert client.get("/profile", headers=headers).json()["groq_view"] == body["groq_view"]


def test_put_address_warning_does_not_change_content(client, headers):
    content = "Skills: Python\nLives near Main Street"
    body = put(client, headers, content).json()
    assert body["content"] == content
    assert body["warnings"] == ["The text may contain an address. Remove it before use."]


def test_put_accepts_exactly_2000_characters(client, headers):
    response = put(client, headers, "a" * 2000)
    assert response.status_code == 200
    assert response.json()["char_count"] == 2000


@pytest.mark.parametrize(
    "content",
    ["", "   ", "\n\t  \n", "a" * 2001, "ab\x00cd"],
)
def test_put_rejects_invalid_content(client, headers, content):
    assert put(client, headers, content).status_code == 422
    assert client.get("/profile", headers=headers).json()["content"] == ""


@pytest.mark.parametrize("body", [{"content": 123}, {"content": None}, {}, {"content": "x", "extra": 1}])
def test_put_rejects_bad_bodies(client, headers, body):
    assert client.put("/profile", headers=headers, json=body).status_code == 422


def test_put_rejects_non_object_body(client, headers):
    assert client.put("/profile", headers=headers, json=["x"]).status_code == 422


def test_failed_put_keeps_previous_content(client, headers):
    put(client, headers, SAMPLE)
    assert put(client, headers, "").status_code == 422
    assert client.get("/profile", headers=headers).json()["content"] == SAMPLE


@pytest.mark.parametrize("key", [None, "wrong-key"])
def test_requires_api_key(client, key):
    request_headers = {} if key is None else {"X-API-Key": key}
    assert client.get("/profile", headers=request_headers).status_code == 401
    response = client.put("/profile", headers=request_headers, json={"content": SAMPLE})
    assert response.status_code == 401
    with engine.begin() as connection:
        assert connection.execute(text("select count(*) from profile")).scalar_one() == 0


def test_patch_and_delete_are_not_allowed(client, headers):
    assert client.patch("/profile", headers=headers, json={"content": "x"}).status_code == 405
    assert client.delete("/profile", headers=headers).status_code == 405


def test_put_does_not_log_content(client, headers, caplog):
    marker = "UNIQUE-MARKER-TEXT test@example.com 555-0100"
    caplog.set_level(logging.DEBUG)
    put(client, headers, marker)
    client.get("/profile", headers=headers)
    assert "UNIQUE-MARKER-TEXT" not in caplog.text


def test_get_profile_text_reads_database_and_sanitizes():
    with engine.begin() as connection:
        connection.execute(
            text("insert into profile (id, content) values (1, :content)"),
            {"content": "Skills: Python\nEmail: test@example.com\nCall 0900-555-0100"},
        )
    with Session(engine) as db:
        result = get_profile_text(db)
    assert "Python" in result
    assert "test@example.com" not in result
    assert "555" not in result
    assert "[removed]" in result


@pytest.mark.parametrize("content", [None, "", "   ", "Email: test@example.com\nPhone: 555-0100"])
def test_get_profile_text_blank_raises_not_set(content):
    if content is not None:
        with engine.begin() as connection:
            connection.execute(
                text("insert into profile (id, content) values (1, :content)"),
                {"content": content},
            )
    with Session(engine) as db:
        with pytest.raises(HTTPException) as info:
            get_profile_text(db)
    assert info.value.status_code == 500
    assert info.value.detail == NOT_SET_DETAIL
    assert info.value.detail.startswith("Profile is not set")


def alembic(*args):
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )


def profile_columns():
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                "select column_name from information_schema.columns "
                "where table_schema = 'public' and table_name = 'profile'"
            )
        ).all()
    return {row[0] for row in rows}


def test_migration_0002_downgrade_and_upgrade():
    try:
        assert "content" in profile_columns()
        down = alembic("downgrade", "0001")
        assert down.returncode == 0
        assert "content" not in profile_columns()
        up = alembic("upgrade", "head")
        assert up.returncode == 0
        assert "content" in profile_columns()
    finally:
        alembic("upgrade", "head")
    assert "content" in profile_columns()
