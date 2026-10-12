"""add_shift_data_reconciliations_table

Revision ID: 3d5ce7627a74
Revises: 16373ca3d8d5
Create Date: 2026-10-12 09:27:46.228846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3d5ce7627a74'
down_revision: Union[str, None] = '16373ca3d8d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1. Добавляем owner_rate в vehicles
    op.add_column('vehicles', sa.Column('owner_rate', sa.Numeric(10, 2), nullable=True))
    
    # 2. Создаём таблицу shift_data_reconciliations
    op.create_table(
        'shift_data_reconciliations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shift_task_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('operator_moto_hours', sa.Numeric(10, 2), nullable=True),
        sa.Column('operator_odometer', sa.Numeric(10, 2), nullable=True),
        sa.Column('operator_fuel_used', sa.Numeric(10, 2), nullable=True),
        sa.Column('telematics_moto_hours', sa.Numeric(10, 2), nullable=True),
        sa.Column('telematics_odometer', sa.Numeric(10, 2), nullable=True),
        sa.Column('telematics_fuel_used', sa.Numeric(10, 2), nullable=True),
        sa.Column('telematics_data_points_count', sa.Integer(), nullable=True),
        sa.Column('planned_moto_hours', sa.Numeric(10, 2), nullable=True),
        sa.Column('planned_odometer', sa.Numeric(10, 2), nullable=True),
        sa.Column('moto_hours_diff_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('odometer_diff_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('fuel_diff_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('reconciliation_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('final_moto_hours', sa.Numeric(10, 2), nullable=True),
        sa.Column('final_odometer', sa.Numeric(10, 2), nullable=True),
        sa.Column('final_fuel_used', sa.Numeric(10, 2), nullable=True),
        sa.Column('decision_source', sa.String(50), nullable=True),
        sa.Column('decision_comment', sa.Text(), nullable=True),
        sa.Column('decided_by', sa.Integer(), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['shift_task_id'], ['shift_tasks.id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reconciliations_shift_task', 'shift_data_reconciliations', ['shift_task_id'])
    op.create_index('ix_reconciliations_company', 'shift_data_reconciliations', ['company_id'])
    op.create_index('ix_reconciliations_status', 'shift_data_reconciliations', ['reconciliation_status'])


def downgrade():
    op.drop_index('ix_reconciliations_status')
    op.drop_index('ix_reconciliations_company')
    op.drop_index('ix_reconciliations_shift_task')
    op.drop_table('shift_data_reconciliations')
    op.drop_column('vehicles', 'owner_rate')