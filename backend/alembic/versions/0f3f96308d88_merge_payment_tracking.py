"""merge_payment_tracking

Revision ID: 0f3f96308d88
Revises: 06454ecb605f, f4i9d2e6g8b1
Create Date: 2026-10-22 14:33:46.638379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f3f96308d88'
down_revision: Union[str, None] = ('06454ecb605f', 'f4i9d2e6g8b1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
