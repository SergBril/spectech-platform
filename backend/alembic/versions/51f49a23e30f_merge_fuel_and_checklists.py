"""merge_fuel_and_checklists

Revision ID: 51f49a23e30f
Revises: 2b720ae83b59, a9d4e7f1b3c6
Create Date: 2026-10-22 10:34:46.956397

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "51f49a23e30f"
down_revision: str | None = ("2b720ae83b59", "a9d4e7f1b3c6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
