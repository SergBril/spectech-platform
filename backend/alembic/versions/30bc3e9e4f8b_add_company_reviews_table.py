"""add_company_reviews_table

Revision ID: 30bc3e9e4f8b
Revises: 3d5ce7627a74
Create Date: 2026-10-12 10:00:09.842361

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '30bc3e9e4f8b'
down_revision: Union[str, None] = '3d5ce7627a74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'company_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_contractor_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_user_id', sa.Integer(), nullable=True),
        sa.Column('request_id', sa.Integer(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('responded_by', sa.Integer(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_contractor_id'], ['contractors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['request_id'], ['requests.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['responded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range')
    )
    
    op.create_index('ix_company_reviews_company_id', 'company_reviews', ['company_id'])
    op.create_index('ix_company_reviews_reviewer_contractor_id', 'company_reviews', ['reviewer_contractor_id'])
    op.create_index('ix_company_reviews_rating', 'company_reviews', ['rating'])
    op.create_index('ix_company_reviews_created_at', 'company_reviews', ['created_at'])
    
    # Уникальность: один отзыв от одного контрагента на одну компанию
    op.create_unique_constraint(
        'uq_company_review_per_contractor',
        'company_reviews',
        ['company_id', 'reviewer_contractor_id']
    )


def downgrade():
    op.drop_constraint('uq_company_review_per_contractor', 'company_reviews')
    op.drop_index('ix_company_reviews_created_at')
    op.drop_index('ix_company_reviews_rating')
    op.drop_index('ix_company_reviews_reviewer_contractor_id')
    op.drop_index('ix_company_reviews_company_id')
    op.drop_table('company_reviews')