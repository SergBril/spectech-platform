"""add bank_statements and bank_transactions

Revision ID: 599021d98758
Revises: 7abdb69cb597
Create Date: 2026-10-07 18:50:27.781339

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '599021d98758'
down_revision: Union[str, None] = '7abdb69cb597'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === Создание таблицы bank_statements ===
    op.create_table(
        'bank_statements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('file_name', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('storage_path', sa.String(1000), nullable=False),
        sa.Column('account_number', sa.String(50), nullable=False, index=True),
        sa.Column('bank_name', sa.String(255), nullable=True),
        sa.Column('date_start', sa.Date(), nullable=False),
        sa.Column('date_end', sa.Date(), nullable=False),
        sa.Column('opening_balance', sa.Numeric(14, 2), default=0),
        sa.Column('closing_balance', sa.Numeric(14, 2), default=0),
        sa.Column('total_incoming', sa.Numeric(14, 2), default=0),
        sa.Column('total_outgoing', sa.Numeric(14, 2), default=0),
        sa.Column('total_transactions', sa.Integer(), default=0),
        sa.Column('matched_transactions', sa.Integer(), default=0),
        sa.Column('unmatched_transactions', sa.Integer(), default=0),
        sa.Column('status', sa.String(20), default='processing'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('uploaded_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # === Создание таблицы bank_transactions ===
    op.create_table(
        'bank_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('statement_id', sa.Integer(), sa.ForeignKey('bank_statements.id'), nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('bank_transaction_id', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('document_type', sa.String(30), nullable=False),
        sa.Column('document_number', sa.String(50), nullable=False),
        sa.Column('document_date', sa.Date(), nullable=False),
        sa.Column('direction', sa.String(20), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('processed_date', sa.Date(), nullable=False),
        sa.Column('counterparty_name', sa.String(500), nullable=False),
        sa.Column('counterparty_inn', sa.String(20), nullable=True),
        sa.Column('counterparty_kpp', sa.String(20), nullable=True),
        sa.Column('counterparty_account', sa.String(50), nullable=True),
        sa.Column('counterparty_bank', sa.String(500), nullable=True),
        sa.Column('counterparty_bik', sa.String(20), nullable=True),
        sa.Column('purpose', sa.Text(), nullable=True),
        sa.Column('match_status', sa.String(20), default='unmatched'),
        sa.Column('matched_invoice_id', sa.Integer(), sa.ForeignKey('invoices.id'), nullable=True),
        sa.Column('matched_amount', sa.Numeric(14, 2), nullable=True),
        sa.Column('match_confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('payment_id', sa.Integer(), sa.ForeignKey('payments.id'), nullable=True),
        sa.Column('is_excluded', sa.Boolean(), default=False),
        sa.Column('exclusion_reason', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # === Новые поля в payments ===
    op.add_column('payments', sa.Column('bank_transaction_id', sa.String(255), nullable=True, unique=True))
    op.add_column('payments', sa.Column('payer_name', sa.String(500), nullable=True))
    op.add_column('payments', sa.Column('payer_inn', sa.String(20), nullable=True))
    op.add_column('payments', sa.Column('payer_account', sa.String(50), nullable=True))
    op.add_column('payments', sa.Column('purpose', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('payments', 'purpose')
    op.drop_column('payments', 'payer_account')
    op.drop_column('payments', 'payer_inn')
    op.drop_column('payments', 'payer_name')
    op.drop_column('payments', 'bank_transaction_id')
    op.drop_table('bank_transactions')
    op.drop_table('bank_statements')