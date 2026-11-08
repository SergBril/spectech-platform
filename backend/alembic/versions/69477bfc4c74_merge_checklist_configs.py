"""merge_checklist_configs

Revision ID: 69477bfc4c74
Revises: 51f49a23e30f, b0e5f8a2c4d7
Create Date: 2026-10-22 10:42:46.054362

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "69477bfc4c74"
down_revision: str | None = ("51f49a23e30f", "b0e5f8a2c4d7")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
