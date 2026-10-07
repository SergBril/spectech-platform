"""add paid_at to payouts

Revision ID: db76ca9f4b93
Revises: ceb6ec91bd38
Create Date: 2026-10-07 ...

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'db76ca9f4b93'
down_revision: Union[str, None] = 'ceb6ec91bd38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('payouts', sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('payouts', 'paid_at')