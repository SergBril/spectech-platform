"""add shift_fuel_entries and pre_shift_checklists tables

Revision ID: a9d4e7f1b3c6
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'a9d4e7f1b3c6'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('shift_fuel_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shift_task_id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('fuel_type', sa.String(20), nullable=True, server_default='diesel'),
        sa.Column('quantity_liters', sa.Float(), nullable=False),
        sa.Column('odometer_reading', sa.Float(), nullable=True),
        sa.Column('engine_hours', sa.Float(), nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('recorded_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['shift_task_id'], ['shift_tasks.id']),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id']),
        sa.ForeignKeyConstraint(['recorded_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_shift_fuel_entries_task_id', 'shift_fuel_entries', ['shift_task_id'])

    op.create_table('pre_shift_checklists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shift_task_id', sa.Integer(), nullable=False),
        sa.Column('submitted_by', sa.Integer(), nullable=True),
        sa.Column('checklist_json', sa.Text(), nullable=True),
        sa.Column('notes', sa.String(1000), nullable=True),
        sa.Column('photo_paths', sa.Text(), nullable=True),
        sa.Column('has_issues', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['shift_task_id'], ['shift_tasks.id']),
        sa.ForeignKeyConstraint(['submitted_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pre_shift_checklists_task_id', 'pre_shift_checklists', ['shift_task_id'])


def downgrade():
    op.drop_index('ix_pre_shift_checklists_task_id', table_name='pre_shift_checklists')
    op.drop_table('pre_shift_checklists')
    op.drop_index('ix_shift_fuel_entries_task_id', table_name='shift_fuel_entries')
    op.drop_table('shift_fuel_entries')
