"""add email processing columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-31 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('emails', sa.Column('confidence', sa.SmallInteger(), nullable=True))
    op.add_column('emails', sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f('ck_emails_confidence_valid'),
        'emails',
        'confidence IS NULL OR confidence BETWEEN 0 AND 100',
    )
    op.create_index(op.f('ix_emails_processed_at'), 'emails', ['processed_at'], unique=False)
    op.add_column(
        'application_events',
        sa.Column('source', sa.Text(), server_default='manual', nullable=False),
    )
    op.add_column('application_events', sa.Column('email_id', sa.BigInteger(), nullable=True))
    op.create_check_constraint(
        op.f('ck_application_events_source_valid'),
        'application_events',
        "source IN ('manual', 'email', 'undo')",
    )
    op.create_foreign_key(
        op.f('fk_application_events_email_id_emails'),
        'application_events',
        'emails',
        ['email_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('fk_application_events_email_id_emails'), 'application_events', type_='foreignkey'
    )
    op.drop_constraint(
        op.f('ck_application_events_source_valid'), 'application_events', type_='check'
    )
    op.drop_column('application_events', 'email_id')
    op.drop_column('application_events', 'source')
    op.drop_index(op.f('ix_emails_processed_at'), table_name='emails')
    op.drop_constraint(op.f('ck_emails_confidence_valid'), 'emails', type_='check')
    op.drop_column('emails', 'processed_at')
    op.drop_column('emails', 'confidence')