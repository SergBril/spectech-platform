"""merge_cost_rates

Revision ID: 3686e284925d
Revises: 69477bfc4c74, c1f6a9b3d5e8
Create Date: 2026-10-22 11:11:57.575326

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3686e284925d'
down_revision: Union[str, None] = ('69477bfc4c74', 'c1f6a9b3d5e8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
