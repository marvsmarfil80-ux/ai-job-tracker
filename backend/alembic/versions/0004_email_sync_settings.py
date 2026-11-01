"""add email sync settings

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-01 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO settings (key, value) VALUES "
        "('email_sync_lookback_days', '7'::jsonb), "
        "('email_sync_timeout_seconds', '300'::jsonb), "
        "('email_sync_interval_minutes', '120'::jsonb) "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM settings WHERE key IN "
        "('email_sync_lookback_days', 'email_sync_timeout_seconds', "
        "'email_sync_interval_minutes')"
    )