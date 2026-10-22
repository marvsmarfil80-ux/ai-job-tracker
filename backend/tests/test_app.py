import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.config import Settings, get_settings
from app.db import engine, get_db
from app.main import app as main_app
from app.models import Base
from app.security import require_api_key


def make_settings(**overrides):
    values = dict(
        _env_file=None,
        postgres_db="d",
        postgres_user="u",
        postgres_password="secret-pw-123",
        api_key="secret-key-456",
        n8n_writer_password="secret-n8n-789",
    )
    values.update(overrides)
    return Settings(**values)


class BrokenSession:
    def execute(self, *args, **kwargs):
        raise RuntimeError("database down")


def broken_db():
    yield BrokenSession()


@pytest.fixture
def client():
    with TestClient(main_app) as test_client:
        yield test_client
    main_app.dependency_overrides.clear()


@pytest.fixture
def protected_client():
    protected = FastAPI()

    @protected.get("/protected", dependencies=[Depends(require_api_key)])
    def protected_route() -> dict[str, str]:
        return {"ok": "yes"}

    return TestClient(protected)


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_database_is_down(client):
    main_app.dependency_overrides[get_db] = broken_db
    response = client.get("/health")
    assert response.status_code == 503


def test_docs_are_disabled(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_missing_api_key_is_rejected(protected_client):
    response = protected_client.get("/protected")
    assert response.status_code == 401


def test_wrong_api_key_is_rejected(protected_client):
    response = protected_client.get("/protected", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_correct_api_key_is_accepted(protected_client):
    key = get_settings().api_key.get_secret_value()
    response = protected_client.get("/protected", headers={"X-API-Key": key})
    assert response.status_code == 200


def test_groq_mock_flag_is_parsed():
    settings = make_settings(groq_mock="true")
    assert settings.groq_mock is True
    assert settings.groq_api_key is None
    assert make_settings().groq_mock is False


def test_secrets_are_hidden_in_settings_repr():
    text = repr(make_settings())
    assert "secret-pw-123" not in text
    assert "secret-key-456" not in text
    assert "secret-n8n-789" not in text


def test_all_fourteen_tables_are_registered():
    assert len(Base.metadata.tables) == 14


def test_database_has_all_tables():
    with engine.connect() as connection:
        names = set(inspect(connection).get_table_names())
    assert set(Base.metadata.tables) <= names

