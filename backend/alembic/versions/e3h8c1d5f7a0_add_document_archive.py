"""add document_archive table

Revision ID: e3h8c1d5f7a0
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'e3h8c1d5f7a0'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('document_archive',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('doc_type', sa.String(30), nullable=False),
        sa.Column('doc_number', sa.String(100), nullable=True),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('related_act_id', sa.Integer(), nullable=True),
        sa.Column('related_shift_id', sa.Integer(), nullable=True),
        sa.Column('uploaded_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['related_act_id'], ['acts.id']),
        sa.ForeignKeyConstraint(['related_shift_id'], ['shift_tasks.id']),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_document_archive_company', 'document_archive', ['company_id'])


def downgrade():
    op.drop_index('ix_document_archive_company', table_name='document_archive')
    op.drop_table('document_archive')
