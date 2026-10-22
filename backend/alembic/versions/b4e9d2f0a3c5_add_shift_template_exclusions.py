"""add shift_template_exclusions table

Revision ID: b4e9d2f0a3c5
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'b4e9d2f0a3c5'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('shift_template_exclusions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('exclusion_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.String(200), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['shift_templates.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('shift_template_exclusions')
