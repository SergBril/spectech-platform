"""add_employee_salary_fields_and_salary_records

Revision ID: 52d24caa286b
Revises: a1b2c3d4e5f6
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '52d24caa286b'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === Добавляем поля зарплаты в employees ===
    op.add_column('employees', sa.Column('salary_type', sa.String(20), nullable=True, comment='Тип расчёта: fixed_shift, hourly, per_km, shift_percent, combo'))
    op.add_column('employees', sa.Column('salary_rate', sa.Numeric(12, 2), nullable=True, comment='Основная ставка (за смену/час/км)'))
    op.add_column('employees', sa.Column('salary_rate_secondary', sa.Numeric(12, 2), nullable=True, comment='Дополнительная ставка (для combo)'))
    op.add_column('employees', sa.Column('salary_commission_percent', sa.Numeric(5, 2), nullable=True, comment='% от стоимости смены (для shift_percent/combo)'))

    # === Создаём таблицу salary_records ===
    op.create_table(
        'salary_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('employee_contractor_id', sa.Integer(), sa.ForeignKey('employees.contractor_id'), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('shifts_count', sa.Integer(), server_default='0'),
        sa.Column('total_hours', sa.Numeric(10, 2), server_default='0'),
        sa.Column('total_km', sa.Numeric(12, 2), server_default='0'),
        sa.Column('salary_type', sa.String(20), nullable=False),
        sa.Column('gross_amount', sa.Numeric(14, 2), server_default='0'),
        sa.Column('deductions', sa.Numeric(14, 2), server_default='0'),
        sa.Column('net_amount', sa.Numeric(14, 2), server_default='0'),
        sa.Column('calculation_details', JSONB(), nullable=True),
        sa.Column('status', sa.String(20), server_default='draft'),
        sa.Column('payout_id', sa.Integer(), sa.ForeignKey('payouts.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
    )
    op.create_index('ix_salary_records_company_id', 'salary_records', ['company_id'])
    op.create_index('ix_salary_records_employee_contractor_id', 'salary_records', ['employee_contractor_id'])


def downgrade() -> None:
    op.drop_index('ix_salary_records_employee_contractor_id', table_name='salary_records')
    op.drop_index('ix_salary_records_company_id', table_name='salary_records')
    op.drop_table('salary_records')
    op.drop_column('employees', 'salary_commission_percent')
    op.drop_column('employees', 'salary_rate_secondary')
    op.drop_column('employees', 'salary_rate')
    op.drop_column('employees', 'salary_type')