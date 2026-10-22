"""add shift_audit_log table

Revision ID: c5f0e3a1b6d7
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'c5f0e3a1b6d7'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('shift_audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shift_task_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('field_changed', sa.String(100), nullable=True),
        sa.Column('old_value', sa.String(500), nullable=True),
        sa.Column('new_value', sa.String(500), nullable=True),
        sa.Column('changed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['shift_task_id'], ['shift_tasks.id']),
        sa.ForeignKeyConstraint(['changed_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_shift_audit_log_task_id', 'shift_audit_log', ['shift_task_id'])


def downgrade():
    op.drop_index('ix_shift_audit_log_task_id', table_name='shift_audit_log')
    op.drop_table('shift_audit_log')
