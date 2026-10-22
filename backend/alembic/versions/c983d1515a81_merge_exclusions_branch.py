"""merge_exclusions_branch

Revision ID: c983d1515a81
Revises: 8b8d8eb327bc, b4e9d2f0a3c5
Create Date: 2026-10-22 09:12:49.201629

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c983d1515a81'
down_revision: Union[str, None] = ('8b8d8eb327bc', 'b4e9d2f0a3c5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
