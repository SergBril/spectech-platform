"""merge_notification_templates

Revision ID: ffaa2ef25f85
Revises: d42c1ad53ae7, i7l2g5h9j1e4
Create Date: 2026-10-22 16:00:04.306921

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ffaa2ef25f85'
down_revision: Union[str, None] = ('d42c1ad53ae7', 'i7l2g5h9j1e4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
