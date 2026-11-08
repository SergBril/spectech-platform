"""merge_role_and_audit

Revision ID: a8a4d03ace65
Revises: 0f3f96308d88, g5j0e3f7h9c2
Create Date: 2026-10-22 15:01:23.585558

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "a8a4d03ace65"
down_revision: str | None = ("0f3f96308d88", "g5j0e3f7h9c2")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
