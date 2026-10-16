"""add_driver_assignment_logs

Revision ID: b900f6ea7225
Revises: d001_driver_profiles
Create Date: 2026-10-16 08:21:36.876212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b900f6ea7225'
down_revision: Union[str, None] = 'd001_driver_profiles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('driver_assignment_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('driver_contractor_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('unassigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assigned_by_user_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['assigned_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['driver_contractor_id'], ['contractors.id'], ),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_driver_assignment_logs_vehicle_id', 'driver_assignment_logs', ['vehicle_id'], unique=False)
    op.create_index('ix_driver_assignment_logs_driver_contractor_id', 'driver_assignment_logs', ['driver_contractor_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_driver_assignment_logs_driver_contractor_id', table_name='driver_assignment_logs')
    op.drop_index('ix_driver_assignment_logs_vehicle_id', table_name='driver_assignment_logs')
    op.drop_table('driver_assignment_logs')
