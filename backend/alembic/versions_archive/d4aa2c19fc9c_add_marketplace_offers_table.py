"""add marketplace offers table

Revision ID: d4aa2c19fc9c
Revises: 7230a9b5e733
Create Date: 2026-09-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4aa2c19fc9c"  # pragma: allowlist secret
down_revision: str | None = "7230a9b5e733"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Таблица уже создана вручную через SQL
    # Эта миграция только для отметки в alembic_version
    pass


def downgrade() -> None:
    op.drop_table("marketplace_offers")
