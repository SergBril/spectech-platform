"""merge_shift_geofences

Revision ID: 2b720ae83b59
Revises: 4e15b192f55c, f8c3d6e4a7b2
Create Date: 2026-10-22 10:26:25.324845

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "2b720ae83b59"
down_revision: str | None = ("4e15b192f55c", "f8c3d6e4a7b2")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
