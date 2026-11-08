"""merge_audit_log_branch

Revision ID: 363733fc0cb4
Revises: c5f0e3a1b6d7, c983d1515a81
Create Date: 2026-10-22 09:31:56.036416

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "363733fc0cb4"
down_revision: str | None = ("c5f0e3a1b6d7", "c983d1515a81")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
