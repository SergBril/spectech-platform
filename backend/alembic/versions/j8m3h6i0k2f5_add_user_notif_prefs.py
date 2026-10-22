"""add user_notification_preferences table

Revision ID: j8m3h6i0k2f5
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'j8m3h6i0k2f5'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('user_notification_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notify_role_change_max', sa.Boolean(), nullable=True),
        sa.Column('notify_role_change_email', sa.Boolean(), nullable=True),
        sa.Column('notify_overdue_max', sa.Boolean(), nullable=True),
        sa.Column('notify_overdue_email', sa.Boolean(), nullable=True),
        sa.Column('notify_act_signed_max', sa.Boolean(), nullable=True),
        sa.Column('notify_act_signed_email', sa.Boolean(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )


def downgrade():
    op.drop_table('user_notification_preferences')
