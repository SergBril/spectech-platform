"""add company_cost_rates table

Revision ID: c1f6a9b3d5e8
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'c1f6a9b3d5e8'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('company_cost_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('fuel_price_per_liter', sa.Float(), nullable=True, server_default='65.0'),
        sa.Column('hourly_wage', sa.Float(), nullable=True, server_default='500.0'),
        sa.Column('amortization_per_hour', sa.Float(), nullable=True, server_default='300.0'),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Add edo_message_id to acts table
    op.add_column('acts', sa.Column('edo_message_id', sa.String(200), nullable=True))


def downgrade():
    op.drop_column('acts', 'edo_message_id')
    op.drop_table('company_cost_rates')
