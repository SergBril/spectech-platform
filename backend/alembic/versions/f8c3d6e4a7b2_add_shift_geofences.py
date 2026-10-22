"""add shift_geofences table

Revision ID: f8c3d6e4a7b2
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'f8c3d6e4a7b2'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('shift_geofences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shift_task_id', sa.Integer(), nullable=False),
        sa.Column('geofence_id', sa.Integer(), nullable=False),
        sa.Column('entered_at', sa.DateTime(), nullable=True),
        sa.Column('exited_at', sa.DateTime(), nullable=True),
        sa.Column('auto_started', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('auto_completed', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['shift_task_id'], ['shift_tasks.id']),
        sa.ForeignKeyConstraint(['geofence_id'], ['geofences.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_shift_geofences_task_id', 'shift_geofences', ['shift_task_id'])


def downgrade():
    op.drop_index('ix_shift_geofences_task_id', table_name='shift_geofences')
    op.drop_table('shift_geofences')
