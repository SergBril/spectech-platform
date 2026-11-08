"""merge_document_archive

Revision ID: 06454ecb605f
Revises: a696b5cb7c25, e3h8c1d5f7a0
Create Date: 2026-10-22 11:33:50.745214

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "06454ecb605f"
down_revision: str | None = ("a696b5cb7c25", "e3h8c1d5f7a0")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
