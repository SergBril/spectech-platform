"""add max_chat_id to users table

Revision ID: h6k1f4g8i0d3
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'h6k1f4g8i0d3'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('max_chat_id', sa.String(100), nullable=True))


def downgrade():
    op.drop_column('users', 'max_chat_id')
