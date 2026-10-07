"""add reviews and company ratings

Revision ID: 58f0c2e7d2b3
Revises: 931a50fe9bcf
Create Date: 2026-10-07 22:32:54.429478

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '58f0c2e7d2b3'
down_revision: Union[str, None] = '931a50fe9bcf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === 1. Создаём таблицу reviews ===
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('rental_id', sa.Integer(), sa.ForeignKey('rentals.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('reviewer_contractor_id', sa.Integer(), sa.ForeignKey('contractors.id'), nullable=False, index=True),
        sa.Column('reviewed_company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False, index=True),
        sa.Column('review_type', sa.String(30), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('pros', sa.Text(), nullable=True),
        sa.Column('cons', sa.Text(), nullable=True),
        sa.Column('photos', sa.JSON(), nullable=True),
        sa.Column('quality_rating', sa.Integer(), nullable=True),
        sa.Column('punctuality_rating', sa.Integer(), nullable=True),
        sa.Column('communication_rating', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='approved'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('helpful_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_anonymous', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('reviewed_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # === 2. Добавляем поля в companies (с server_default, чтобы не падало на существующих записях) ===
    op.add_column('companies', sa.Column(
        'average_rating', sa.Numeric(3, 2), nullable=True,
        comment='Средний рейтинг компании (1.00 - 5.00)'
    ))
    op.add_column('companies', sa.Column(
        'total_reviews', sa.Integer(), nullable=False, server_default='0',
        comment='Общее количество отзывов'
    ))
    op.add_column('companies', sa.Column(
        'rating_distribution', sa.JSON(), nullable=True,
        comment='Распределение оценок: {"5": 10, "4": 3, "3": 1, "2": 0, "1": 0}'
    ))


def downgrade() -> None:
    op.drop_column('companies', 'rating_distribution')
    op.drop_column('companies', 'total_reviews')
    op.drop_column('companies', 'average_rating')
    op.drop_table('reviews')