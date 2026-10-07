"""add rental_id and commission_rate

Revision ID: 7abdb69cb597
Revises: c88261b247a6
Create Date: 2026-10-07 16:15:32.495175

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from decimal import Decimal

# revision identifiers, used by Alembic.
revision: str = '7abdb69cb597'
down_revision: Union[str, None] = 'c88261b247a6'
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