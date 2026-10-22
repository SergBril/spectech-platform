"""merge_device_tokens

Revision ID: 4e15b192f55c
Revises: b7e35ae7e7d5, e7b2c5d3f9a1
Create Date: 2026-10-22 10:17:00.144429

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e15b192f55c'
down_revision: Union[str, None] = ('b7e35ae7e7d5', 'e7b2c5d3f9a1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
