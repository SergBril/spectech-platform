"""add device_tokens table

Revision ID: e7b2c5d3f9a1
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'e7b2c5d3f9a1'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('device_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(500), nullable=False),
        sa.Column('platform', sa.String(20), nullable=True, server_default='web'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_device_tokens_user_id', 'device_tokens', ['user_id'])


def downgrade():
    op.drop_index('ix_device_tokens_user_id', table_name='device_tokens')
    op.drop_table('device_tokens')
