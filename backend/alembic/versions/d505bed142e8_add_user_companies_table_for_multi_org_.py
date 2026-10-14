"""add user_companies table for multi-org support

Revision ID: d505bed142e8
Revises: 73c5191fd99e
Create Date: 2026-10-14 15:39:38.008248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd505bed142e8'
down_revision: Union[str, None] = '73c5191fd99e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'user_companies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='member'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'company_id', name='uq_user_company'),
    )
    op.create_index('ix_user_companies_user_id', 'user_companies', ['user_id'])
    op.create_index('ix_user_companies_company_id', 'user_companies', ['company_id'])


def downgrade():
    op.drop_index('ix_user_companies_company_id')
    op.drop_index('ix_user_companies_user_id')
    op.drop_table('user_companies')