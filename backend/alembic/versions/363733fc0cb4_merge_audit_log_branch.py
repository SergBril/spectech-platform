"""merge_audit_log_branch

Revision ID: 363733fc0cb4
Revises: c5f0e3a1b6d7, c983d1515a81
Create Date: 2026-10-22 09:31:56.036416

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '363733fc0cb4'
down_revision: Union[str, None] = ('c5f0e3a1b6d7', 'c983d1515a81')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
