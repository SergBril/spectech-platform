"""add user role and audit_logs table

Revision ID: g5j0e3f7h9c2
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'g5j0e3f7h9c2'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    # Add role column to users
    op.add_column('users', sa.Column('role', sa.String(20), nullable=True, server_default='viewer'))

    # Create audit_logs table
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])


def downgrade():
    op.drop_index('ix_audit_logs_user_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_column('users', 'role')
