"""add uploaded_files payout_id and link code expiry

Revision ID: 16bd149120da
Revises: 6d1a13955cc1
Create Date: 2026-11-14 11:02:27.600042

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "16bd149120da"  # pragma: allowlist secret
down_revision: str | None = "6d1a13955cc1"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Две колонки, которых не хватало коде.

    uploaded_files.payout_id: pdf_tasks пишет PDF выплат, но связать файл с
    выплатой было нечем - связь восстанавливалась только по имени пути.
    users.telegram_link_code_expires_at: код привязки чата был вечным,
    единственный секрет без срока действия.
    """
    op.add_column(
        "uploaded_files",
        sa.Column("payout_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_uploaded_files_payout_id",
        "uploaded_files",
        "payouts",
        ["payout_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "users",
        sa.Column(
            "telegram_link_code_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "telegram_link_code_expires_at")
    op.drop_constraint(
        "fk_uploaded_files_payout_id", "uploaded_files", type_="foreignkey"
    )
    op.drop_column("uploaded_files", "payout_id")
