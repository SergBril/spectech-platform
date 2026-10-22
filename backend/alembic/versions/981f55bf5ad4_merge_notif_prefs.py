"""merge_notif_prefs

Revision ID: 981f55bf5ad4
Revises: ffaa2ef25f85, j8m3h6i0k2f5
Create Date: 2026-10-22 16:20:23.828349

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '981f55bf5ad4'
down_revision: Union[str, None] = ('ffaa2ef25f85', 'j8m3h6i0k2f5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
