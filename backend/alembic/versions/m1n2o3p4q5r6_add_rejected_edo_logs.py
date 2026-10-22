"""add rejected to document_status enum + edo_send_logs table

Revision ID: m1n2o3p4q5r6
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'm1n2o3p4q5r6'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    # Add 'rejected' value to document_status enum
    op.execute("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'rejected'")
    
    # Create edo_send_logs table
    op.create_table('edo_send_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('act_id', sa.Integer(), nullable=True),
        sa.Column('document_number', sa.String(100), nullable=False),
        sa.Column('operator', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('xml_size', sa.Integer(), nullable=True),
        sa.Column('sig_size', sa.Integer(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('sent_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['act_id'], ['acts.id']),
        sa.ForeignKeyConstraint(['sent_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('edo_send_logs')
    # Note: Cannot remove enum value in PostgreSQL easily
