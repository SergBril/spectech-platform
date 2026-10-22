"""add payment tracking fields to acts and bank_transactions

Revision ID: f4i9d2e6g8b1
Revises: sprint3_002
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'f4i9d2e6g8b1'
down_revision = 'sprint3_002'
branch_labels = None
depends_on = None


def upgrade():
    # Acts: payment tracking
    op.add_column('acts', sa.Column('paid_amount', sa.Float(), nullable=True, server_default='0'))
    op.add_column('acts', sa.Column('payment_status', sa.String(20), nullable=True, server_default='unpaid'))
    op.add_column('acts', sa.Column('counterparty_inn', sa.String(20), nullable=True))
    op.add_column('acts', sa.Column('counterparty_name', sa.String(200), nullable=True))

    # BankTransactions: matching
    op.add_column('bank_transactions', sa.Column('matched_act_id', sa.Integer(), nullable=True))
    op.add_column('bank_transactions', sa.Column('source', sa.String(20), nullable=True, server_default='manual'))


def downgrade():
    op.drop_column('bank_transactions', 'source')
    op.drop_column('bank_transactions', 'matched_act_id')
    op.drop_column('acts', 'counterparty_name')
    op.drop_column('acts', 'counterparty_inn')
    op.drop_column('acts', 'payment_status')
    op.drop_column('acts', 'paid_amount')
