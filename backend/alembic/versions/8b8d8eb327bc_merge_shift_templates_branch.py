"""merge_shift_templates_branch

Revision ID: 8b8d8eb327bc
Revises: a3f8c1d9e2b4, c8d9e0f1a2b3
Create Date: 2026-10-22 08:40:40.943564

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b8d8eb327bc'
down_revision: Union[str, None] = ('a3f8c1d9e2b4', 'c8d9e0f1a2b3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
