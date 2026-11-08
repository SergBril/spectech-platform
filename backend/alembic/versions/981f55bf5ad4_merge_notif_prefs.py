"""merge_notif_prefs

Revision ID: 981f55bf5ad4
Revises: ffaa2ef25f85, j8m3h6i0k2f5
Create Date: 2026-10-22 16:20:23.828349

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "981f55bf5ad4"
down_revision: str | None = ("ffaa2ef25f85", "j8m3h6i0k2f5")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
