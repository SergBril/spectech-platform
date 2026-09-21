"""create chat tables

Revision ID: e5bb3a012345
Revises: d4aa2c19fc9c
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e5bb3a012345"  # pragma: allowlist secret
down_revision: Union[str, None] = "d4aa2c19fc9c"  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Таблицы уже созданы вручную через SQL
    pass


def downgrade() -> None:
    op.drop_table("chat_participants")
    op.drop_table("chat_messages")
    op.drop_table("request_chats")