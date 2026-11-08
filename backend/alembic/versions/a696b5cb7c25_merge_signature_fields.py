"""merge_signature_fields

Revision ID: a696b5cb7c25
Revises: 3686e284925d, d2g7b0c4e6f9
Create Date: 2026-10-22 11:24:01.290320

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "a696b5cb7c25"
down_revision: str | None = ("3686e284925d", "d2g7b0c4e6f9")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
