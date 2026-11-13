import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.hunts import effective_limit

PUBLIC = {("get", "/health")}


def list_operations():
    found = []
    for path, methods in app.openapi()["paths"].items():
        for method in methods:
            found.append((method, path))
    return sorted(found)


OPERATIONS = list_operations()


@pytest.fixture(scope="module")
def route_client():
    with TestClient(app) as test_client:
        yield test_client


def test_route_inventory_is_complete():
    assert len(OPERATIONS) >= 42
    assert ("get", "/health") in OPERATIONS


@pytest.mark.parametrize("method,path", OPERATIONS)
def test_every_route_rejects_missing_and_wrong_keys(route_client, method, path):
    url = re.sub(r"\{[^}]+\}", "1", path)
    if (method, path) in PUBLIC:
        assert route_client.request(method.upper(), url).status_code == 200
        return
    for headers in ({}, {"X-API-Key": "wrong"}):
        response = route_client.request(method.upper(), url, headers=headers)
        assert response.status_code == 401


@pytest.mark.parametrize("value,expected", [(None, 4), (1, 1), (4, 4), (9, 4)])
def test_effective_limit_is_never_above_four(value, expected):
    assert effective_limit(value) == expected