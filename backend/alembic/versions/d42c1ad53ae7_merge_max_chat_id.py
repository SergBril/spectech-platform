"""merge_max_chat_id

Revision ID: d42c1ad53ae7
Revises: c8dbc0a7c4d9
Create Date: 2026-10-22 15:39:11.229970

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd42c1ad53ae7'
down_revision: Union[str, None] = 'c8dbc0a7c4d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
