"""add_rentals_and_rental_items_tables

Revision ID: fbfa59b5ac26
Revises: a434f95115a9
Create Date: 2026-10-06 18:10:43.342959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbfa59b5ac26'
down_revision: Union[str, None] = 'a434f95115a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === 1. Таблица rentals (договоры аренды) ===
    op.create_table(
        'rentals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False, comment='Клиент (contractors.id)'),
        sa.Column('request_id', sa.Integer(), nullable=True, comment='Связанная заявка (опционально)'),
        sa.Column('company_id', sa.Integer(), nullable=True, comment='Компания (мультитенантность)'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft', comment='Статус аренды'),
        sa.Column('rate_type', sa.String(length=20), nullable=False, server_default='hourly', comment='Тип тарификации'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actual_return_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hourly_rate', sa.Numeric(precision=10, scale=2), nullable=True, comment='Ставка за моточас'),
        sa.Column('shift_rate', sa.Numeric(precision=10, scale=2), nullable=True, comment='Ставка за смену'),
        sa.Column('trip_rate', sa.Numeric(precision=10, scale=2), nullable=True, comment='Ставка за ходку'),
        sa.Column('volume_rate', sa.Numeric(precision=10, scale=2), nullable=True, comment='Ставка за куб.м'),
        sa.Column('mileage_rate', sa.Numeric(precision=10, scale=2), nullable=True, comment='Ставка за км'),
        sa.Column('base_price', sa.Numeric(precision=10, scale=2), nullable=True, comment='Базовая стоимость'),
        sa.Column('discount', sa.Numeric(precision=10, scale=2), nullable=True, comment='Скидка'),
        sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=True, comment='Итоговая сумма'),
        sa.Column('prepayment_status', sa.String(length=20), nullable=False, server_default='none', comment='Статус предоплаты'),
        sa.Column('prepayment_amount', sa.Numeric(precision=10, scale=2), nullable=True, comment='Сумма предоплаты'),
        sa.Column('prepayment_paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['contractors.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['request_id'], ['requests.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_rentals_id'), 'rentals', ['id'], unique=False)
    op.create_index('ix_rentals_client_id', 'rentals', ['client_id'], unique=False)
    op.create_index('ix_rentals_status', 'rentals', ['status'], unique=False)
    op.create_index('ix_rentals_company_id', 'rentals', ['company_id'], unique=False)

    # === 2. Таблица rental_items (позиции аренды — единицы техники) ===
    op.create_table(
        'rental_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rental_id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False, comment='Техника (vehicles.id)'),
        sa.Column('quantity', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False, comment='Цена за единицу на момент аренды'),
        sa.Column('actual_moto_hours', sa.Numeric(precision=10, scale=2), nullable=True, comment='Фактические моточасы'),
        sa.Column('actual_mileage', sa.Numeric(precision=10, scale=2), nullable=True, comment='Фактический пробег (км)'),
        sa.Column('actual_trips', sa.Integer(), nullable=True, comment='Фактическое количество ходок'),
        sa.Column('actual_volume', sa.Numeric(precision=10, scale=2), nullable=True, comment='Фактический объём (куб.м)'),
        sa.ForeignKeyConstraint(['rental_id'], ['rentals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_rental_items_id'), 'rental_items', ['id'], unique=False)
    op.create_index('ix_rental_items_rental_id', 'rental_items', ['rental_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_rental_items_rental_id', table_name='rental_items')
    op.drop_index(op.f('ix_rental_items_id'), table_name='rental_items')
    op.drop_table('rental_items')

    op.drop_index('ix_rentals_company_id', table_name='rentals')
    op.drop_index('ix_rentals_status', table_name='rentals')
    op.drop_index('ix_rentals_client_id', table_name='rentals')
    op.drop_index(op.f('ix_rentals_id'), table_name='rentals')
    op.drop_table('rentals')