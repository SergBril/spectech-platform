"""align shift reports operator nullability with model

Revision ID: f9000521b079
Revises: 7b5a27e217e3
Create Date: 2026-11-15 14:20:04.920278

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9000521b079"  # pragma: allowlist secret
down_revision: str | None = "7b5a27e217e3"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_COLUMNS = [
    ("shift_reports", "operator_id"),
]


def upgrade() -> None:
    """Drop NOT NULL where the model allows NULL.

    The opposite direction of the previous revision: the database was
    created when these columns were required, then the models were
    relaxed with no migration to match. Relaxing a constraint cannot
    fail on existing data.
    """
    for table, column in _COLUMNS:
        op.alter_column(table, column, nullable=True)


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(table, column, nullable=False)
