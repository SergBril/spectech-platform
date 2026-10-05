"""add_disputes_table

Revision ID: bb817b656eaf
Revises: add_overbooking_protection
Create Date: 2026-10-02 08:24:46.176615

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb817b656eaf'
down_revision: Union[str, None] = 'add_overbooking_protection'  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'disputes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shift_report_id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='open'),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sla_deadline', sa.DateTime(timezone=True), nullable=False),
        sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('escalation_deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('initiator_id', sa.Integer(), nullable=False),
        sa.Column('initiator_role', sa.String(20), nullable=False),
        sa.Column('assigned_to', sa.Integer(), nullable=True),
        sa.Column('assigned_role', sa.String(20), nullable=True),
        sa.Column('dispute_type', sa.String(20), nullable=False),
        sa.Column('operator_version', sa.JSON(), nullable=True),
        sa.Column('client_version', sa.JSON(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('resolution', sa.JSON(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolution_time_minutes', sa.Integer(), nullable=True),
        sa.Column('sla_breached', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['shift_report_id'], ['shift_reports.id'], ),
        sa.ForeignKeyConstraint(['request_id'], ['requests.id'], ),
        sa.ForeignKeyConstraint(['initiator_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], ),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_disputes_status', 'disputes', ['status'], unique=False)
    op.create_index('idx_disputes_sla_deadline', 'disputes', ['sla_deadline'], unique=False)
    op.create_index('idx_disputes_company_id', 'disputes', ['company_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_disputes_company_id', table_name='disputes')
    op.drop_index('idx_disputes_sla_deadline', table_name='disputes')
    op.drop_index('idx_disputes_status', table_name='disputes')
    op.drop_table('disputes')