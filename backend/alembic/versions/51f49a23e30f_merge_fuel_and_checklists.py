"""merge_fuel_and_checklists

Revision ID: 51f49a23e30f
Revises: 2b720ae83b59, a9d4e7f1b3c6
Create Date: 2026-10-22 10:34:46.956397

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51f49a23e30f'
down_revision: Union[str, None] = ('2b720ae83b59', 'a9d4e7f1b3c6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
