"""add signature fields to acts table

Revision ID: d2g7b0c4e6f9
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'd2g7b0c4e6f9'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('acts', sa.Column('signature', sa.Text(), nullable=True))
    op.add_column('acts', sa.Column('signed_at', sa.DateTime(), nullable=True))
    op.add_column('acts', sa.Column('signed_by', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('acts', 'signed_by')
    op.drop_column('acts', 'signed_at')
    op.drop_column('acts', 'signature')
