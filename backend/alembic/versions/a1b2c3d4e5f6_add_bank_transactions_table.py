"""add_bank_transactions_table

Revision ID: a1b2c3d4e5f6
Revises: 30bc3e9e4f8b
Create Date: 2026-10-13
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '30bc3e9e4f8b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'bank_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('bank_name', sa.String(100), nullable=True),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('currency', sa.String(3), server_default='RUB'),
        sa.Column('counterparty_name', sa.String(500), nullable=True),
        sa.Column('counterparty_inn', sa.String(20), nullable=True),
        sa.Column('counterparty_account', sa.String(50), nullable=True),
        sa.Column('purpose', sa.Text(), nullable=True),
        sa.Column('document_number', sa.String(100), nullable=True),
        sa.Column('operation_type', sa.Enum('income', 'expense', name='transactiontype'), nullable=False),
        sa.Column('match_status', sa.Enum('unmatched', 'matched_auto', 'matched_manual', 'ignored', name='matchstatus'), server_default='unmatched', nullable=False),
        sa.Column('matched_invoice_id', sa.Integer(), nullable=True),
        sa.Column('matched_payout_id', sa.Integer(), nullable=True),
        sa.Column('match_confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('uploaded_by', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['matched_invoice_id'], ['invoices.id']),
        sa.ForeignKeyConstraint(['matched_payout_id'], ['payouts.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bank_transactions_company_id', 'bank_transactions', ['company_id'])
    op.create_index('ix_bank_transactions_transaction_date', 'bank_transactions', ['transaction_date'])
    op.create_index('ix_bank_transactions_counterparty_inn', 'bank_transactions', ['counterparty_inn'])


def downgrade() -> None:
    op.drop_index('ix_bank_transactions_counterparty_inn', table_name='bank_transactions')
    op.drop_index('ix_bank_transactions_transaction_date', table_name='bank_transactions')
    op.drop_index('ix_bank_transactions_company_id', table_name='bank_transactions')
    op.drop_table('bank_transactions')