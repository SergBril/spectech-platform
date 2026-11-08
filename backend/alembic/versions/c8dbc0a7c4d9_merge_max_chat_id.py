"""merge_max_chat_id

Revision ID: c8dbc0a7c4d9
Revises: a8a4d03ace65, h6k1f4g8i0d3
Create Date: 2026-10-22 15:29:08.396933

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c8dbc0a7c4d9"
down_revision: str | None = ("a8a4d03ace65", "h6k1f4g8i0d3")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
