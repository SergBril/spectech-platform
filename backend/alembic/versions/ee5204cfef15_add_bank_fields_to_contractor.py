"""add_bank_fields_to_contractor

Revision ID: ee5204cfef15
Revises: e04df718848b
Create Date: 2026-10-26 20:15:34.983399

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ee5204cfef15"
down_revision: str | None = "e04df718848b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contractors", sa.Column("bank_account", sa.String(50), nullable=True)
    )
    op.add_column("contractors", sa.Column("bik", sa.String(20), nullable=True))
    op.add_column("contractors", sa.Column("bank_name", sa.String(255), nullable=True))
    op.add_column(
        "contractors", sa.Column("correspondent_account", sa.String(50), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("contractors", "correspondent_account")
    op.drop_column("contractors", "bank_name")
    op.drop_column("contractors", "bik")
    op.drop_column("contractors", "bank_account")
