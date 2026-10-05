"""add_downtime_tracking

Revision ID: a434f95115a9
Revises: 684efc6be9bd
Create Date: 2026-10-05 ...

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a434f95115a9'
down_revision: Union[str, None] = '684efc6be9bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === 1. Добавляем downtime_hourly_rate в vehicles ===
    op.add_column(
        'vehicles',
        sa.Column(
            'downtime_hourly_rate',
            sa.Numeric(10, 2),
            nullable=True,
            comment='Ставка простоя за час (руб). Если не указана — используется 50% от hourly_rate',
        ),
    )

    # === 2. Создаём таблицу downtime_events ===
    op.create_table(
        'downtime_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shift_task_id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'duration_minutes',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='Длительность простоя в минутах',
        ),
        sa.Column(
            'cause_category',
            sa.String(30),
            nullable=False,
            comment='Причина простоя',
        ),
        sa.Column(
            'fault_party',
            sa.String(20),
            nullable=False,
            comment='Виновная сторона',
        ),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'photos',
            sa.JSON(),
            nullable=True,
            comment='Список фото-доказательств',
        ),
        sa.Column(
            'billable',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
            comment='Оплачивается ли клиентом',
        ),
        sa.Column(
            'hourly_rate',
            sa.Numeric(10, 2),
            nullable=False,
            server_default='0',
            comment='Ставка на момент фиксации простоя (руб/час)',
        ),
        sa.Column(
            'total_amount',
            sa.Numeric(14, 2),
            nullable=False,
            server_default='0',
            comment='Итоговая сумма: (duration_minutes / 60) * hourly_rate',
        ),
        sa.Column(
            'status',
            sa.String(20),
            nullable=False,
            server_default='pending',
        ),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['shift_task_id'], ['shift_tasks.id']),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id']),
        sa.ForeignKeyConstraint(['request_id'], ['requests.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # === 3. Индексы для downtime_events ===
    op.create_index(
        op.f('ix_downtime_events_shift_task_id'),
        'downtime_events',
        ['shift_task_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_downtime_events_vehicle_id'),
        'downtime_events',
        ['vehicle_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_downtime_events_company_id'),
        'downtime_events',
        ['company_id'],
        unique=False,
    )
    op.create_index(
        'ix_downtime_events_status',
        'downtime_events',
        ['status'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_downtime_events_status', table_name='downtime_events')
    op.drop_index(op.f('ix_downtime_events_company_id'), table_name='downtime_events')
    op.drop_index(op.f('ix_downtime_events_vehicle_id'), table_name='downtime_events')
    op.drop_index(op.f('ix_downtime_events_shift_task_id'), table_name='downtime_events')
    op.drop_table('downtime_events')
    op.drop_column('vehicles', 'downtime_hourly_rate')