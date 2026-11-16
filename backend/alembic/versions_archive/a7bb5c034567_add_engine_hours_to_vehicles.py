"""add engine_hours to vehicles

Revision ID: a7bb5c034567
Revises: f6cc4b023456
Create Date: 2026-09-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a7bb5c034567"  # pragma: allowlist secret
down_revision: str | None = "f6cc4b023456"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass  # Колонка уже добавлена через SQL


def downgrade() -> None:
    op.drop_column("vehicles", "engine_hours")
