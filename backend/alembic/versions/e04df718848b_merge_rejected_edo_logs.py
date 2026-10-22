"""merge_rejected_edo_logs

Revision ID: e04df718848b
Revises: 981f55bf5ad4, m1n2o3p4q5r6
Create Date: 2026-10-22 19:00:14.455378

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e04df718848b'
down_revision: Union[str, None] = ('981f55bf5ad4', 'm1n2o3p4q5r6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
