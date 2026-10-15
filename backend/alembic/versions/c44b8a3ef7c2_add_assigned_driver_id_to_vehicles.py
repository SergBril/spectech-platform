"""add_assigned_driver_id_to_vehicles

Revision ID: c44b8a3ef7c2
Revises: 61e5ba93890b
Create Date: 2026-10-15 18:18:33.024120

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c44b8a3ef7c2'
down_revision: Union[str, None] = '61e5ba93890b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vehicles', sa.Column('assigned_driver_id', sa.Integer(), nullable=True, comment='Текущий водитель (FK к employees.contractor_id)'))
    op.create_index(op.f('ix_vehicles_assigned_driver_id'), 'vehicles', ['assigned_driver_id'], unique=False)
    op.create_foreign_key('fk_vehicles_assigned_driver_id', 'vehicles', 'employees', ['assigned_driver_id'], ['contractor_id'])


def downgrade() -> None:
    op.drop_constraint('fk_vehicles_assigned_driver_id', 'vehicles', type_='foreignkey')
    op.drop_index(op.f('ix_vehicles_assigned_driver_id'), table_name='vehicles')
    op.drop_column('vehicles', 'assigned_driver_id')