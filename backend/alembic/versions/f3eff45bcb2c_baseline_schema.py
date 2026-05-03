"""baseline_schema

Revision ID: f3eff45bcb2c
Revises: 
Create Date: 2026-04-26 09:44:21.805286

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f3eff45bcb2c'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=50), server_default='user', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.create_table(
        'meetings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('transcript_text', sa.Text(), nullable=False),
        sa.Column('transcript_hash', sa.String(length=64), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('action_items', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_meeting_user_created', 'meetings', ['user_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_meetings_created_at'), 'meetings', ['created_at'], unique=False)
    op.create_index(op.f('ix_meetings_transcript_hash'), 'meetings', ['transcript_hash'], unique=True)
    op.create_index(op.f('ix_meetings_user_id'), 'meetings', ['user_id'], unique=False)

    op.create_table(
        'usage_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('meeting_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_name', sa.String(length=50), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('estimated_cost', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_usage_meeting_created', 'usage_records', ['meeting_id', 'created_at'], unique=False)
    op.create_index('idx_usage_user_created', 'usage_records', ['user_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_usage_records_created_at'), 'usage_records', ['created_at'], unique=False)
    op.create_index(op.f('ix_usage_records_meeting_id'), 'usage_records', ['meeting_id'], unique=False)
    op.create_index(op.f('ix_usage_records_user_id'), 'usage_records', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('usage_records')
    op.drop_table('meetings')
    op.drop_table('users')
