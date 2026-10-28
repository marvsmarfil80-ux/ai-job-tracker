import os
os.environ["POSTGRES_DB"] = "jobtracker_test"
os.environ["SCHEDULER_THREAD_ENABLED"] = "false"

import pytest
from sqlalchemy import text

from app.config import get_settings
from app.db import engine

TEST_DATABASE = "jobtracker_test"

if get_settings().postgres_db != TEST_DATABASE:
    pytest.exit("Refusing to run: tests must use the jobtracker_test database", returncode=2)


def _assert_test_database(connection):
    name = connection.execute(text("select current_database()")).scalar_one()
    if name != TEST_DATABASE:
        pytest.exit("Refusing to run: connected to the wrong database", returncode=2)


def _clean(connection):
    _assert_test_database(connection)
    connection.execute(text("truncate table jobs restart identity cascade"))
    connection.execute(text("delete from notifications"))

@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    with engine.begin() as connection:
        _assert_test_database(connection)
        connection.execute(
            text(
                "insert into settings (key, value) values "
                "('apply_threshold', cast('70' as jsonb)), "
                "('maybe_threshold', cast('40' as jsonb)) "
                "on conflict (key) do update set value = excluded.value"
            )
        )
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as connection:
        _clean(connection)
    yield
    with engine.begin() as connection:
        _clean(connection)

