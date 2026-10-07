"""add rental_id to payouts and commission_rate to rentals

Revision ID: 92744cb7b597
Revises: 7abdb69cb597
Create Date: 2026-10-07 16:26:39.893206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '92744cb7b597'
down_revision: Union[str, None] = '7abdb69cb597'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Делаем vehicle_id nullable в payouts
    op.alter_column('payouts', 'vehicle_id',
               existing_type=sa.Integer(),
               nullable=True)
    
    # 2. Добавляем rental_id в payouts
    op.add_column('payouts', sa.Column('rental_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'payouts_rental_id_fkey',
        'payouts', 'rentals',
        ['rental_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # 3. Добавляем commission_rate в rentals
    op.add_column('rentals', sa.Column(
        'commission_rate',
        sa.Numeric(5, 2),
        nullable=False,
        server_default='10.00',
        comment='Процент комиссии платформы для выплат собственникам'
    ))


def downgrade() -> None:
    op.drop_column('rentals', 'commission_rate')
    op.drop_constraint('payouts_rental_id_fkey', 'payouts', type_='foreignkey')
    op.drop_column('payouts', 'rental_id')
    op.alter_column('payouts', 'vehicle_id',
               existing_type=sa.Integer(),
               nullable=False)