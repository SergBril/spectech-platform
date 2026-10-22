"""merge_auto_assign_rules

Revision ID: b7e35ae7e7d5
Revises: 363733fc0cb4, d6a1f4b2c8e9
Create Date: 2026-10-22 09:37:38.749069

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e35ae7e7d5'
down_revision: Union[str, None] = ('363733fc0cb4', 'd6a1f4b2c8e9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
