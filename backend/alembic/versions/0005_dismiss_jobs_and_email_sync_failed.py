"""add jobs.dismissed_at and the email_sync_failed notification type

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-07 21:30:00.000000

The downgrade first deletes every notification whose type is
email_sync_failed, because the old constraint does not allow that type.
It then restores the old constraint and drops jobs.dismissed_at, so any
dismissed state is lost.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint(op.f('ck_notifications_type_valid'), 'notifications', type_='check')
    op.create_check_constraint(
        op.f('ck_notifications_type_valid'),
        'notifications',
        "type IN ('hunt_done', 'follow_up_overdue', 'status_changed', "
        "'email_needs_review', 'email_sync_failed')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE type = 'email_sync_failed'")
    op.drop_constraint(op.f('ck_notifications_type_valid'), 'notifications', type_='check')
    op.create_check_constraint(
        op.f('ck_notifications_type_valid'),
        'notifications',
        "type IN ('hunt_done', 'follow_up_overdue', 'status_changed', "
        "'email_needs_review')",
    )
    op.drop_column('jobs', 'dismissed_at')