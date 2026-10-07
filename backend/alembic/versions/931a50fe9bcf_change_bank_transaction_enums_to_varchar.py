"""change bank_transaction enums to varchar

Revision ID: 931a50fe9bcf
Revises: 599021d98758
Create Date: 2026-10-07 20:07:27.296174

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '931a50fe9bcf'
down_revision: Union[str, None] = '599021d98758'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # bank_transactions
    op.alter_column('bank_transactions', 'document_type',
                    existing_type=sa.String(30),
                    type_=sa.String(30),
                    existing_nullable=False)
    op.alter_column('bank_transactions', 'direction',
                    existing_type=sa.String(20),
                    type_=sa.String(20),
                    existing_nullable=False)
    op.alter_column('bank_transactions', 'match_status',
                    existing_type=sa.String(20),
                    type_=sa.String(20))
    # bank_statements
    op.alter_column('bank_statements', 'status',
                    existing_type=sa.String(20),
                    type_=sa.String(20))


def downgrade() -> None:
    pass