"""merge_rejected_edo_logs

Revision ID: e04df718848b
Revises: 981f55bf5ad4, m1n2o3p4q5r6
Create Date: 2026-10-22 19:00:14.455378

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "e04df718848b"
down_revision: str | None = ("981f55bf5ad4", "m1n2o3p4q5r6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
