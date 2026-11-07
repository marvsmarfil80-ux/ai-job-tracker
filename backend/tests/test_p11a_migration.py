import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE = "jobtracker_test"
NEW_TYPE = "email_sync_failed"


def assert_test_database():
    with engine.connect() as connection:
        name = connection.execute(text("select current_database()")).scalar_one()
    if name != TEST_DATABASE:
        pytest.exit("Refusing to run: connected to the wrong database", returncode=2)


def run_alembic(*args):
    env = {**os.environ, "POSTGRES_DB": TEST_DATABASE}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]


def current_revision():
    with engine.connect() as connection:
        return connection.execute(text("select version_num from alembic_version")).scalar_one()


def dismissed_column():
    with engine.connect() as connection:
        return connection.execute(
            text(
                "select is_nullable, data_type from information_schema.columns "
                "where table_name = 'jobs' and column_name = 'dismissed_at'"
            )
        ).first()


def type_constraint():
    with engine.connect() as connection:
        return connection.execute(
            text(
                "select pg_get_constraintdef(oid) from pg_constraint "
                "where conname = 'ck_notifications_type_valid'"
            )
        ).scalar_one()


def insert_failed_notification():
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into notifications (type, message) "
                "values (:type, 'Email check failed: migration test')"
            ),
            {"type": NEW_TYPE},
        )


def count_failed_notifications():
    with engine.connect() as connection:
        return connection.execute(
            text("select count(*) from notifications where type = :type"), {"type": NEW_TYPE}
        ).scalar_one()


def test_head_has_the_dismissed_column_and_the_new_type():
    assert_test_database()
    assert current_revision() == "0005"
    assert tuple(dismissed_column()) == ("YES", "timestamp with time zone")
    assert NEW_TYPE in type_constraint()
    insert_failed_notification()
    assert count_failed_notifications() == 1


def test_downgrade_then_upgrade_again_works():
    assert_test_database()
    insert_failed_notification()
    try:
        run_alembic("downgrade", "-1")
        assert current_revision() == "0004"
        assert dismissed_column() is None
        assert NEW_TYPE not in type_constraint()
        assert count_failed_notifications() == 0
        with pytest.raises(IntegrityError):
            insert_failed_notification()
    finally:
        run_alembic("upgrade", "head")
    assert current_revision() == "0005"
    assert tuple(dismissed_column()) == ("YES", "timestamp with time zone")
    assert NEW_TYPE in type_constraint()
    insert_failed_notification()
    assert count_failed_notifications() == 1