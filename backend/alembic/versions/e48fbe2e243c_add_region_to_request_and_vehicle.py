"""add_region_to_request_and_vehicle

Revision ID: e48fbe2e243c
Revises: ee5204cfef15
Create Date: 2026-10-26 21:50:21.544105

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e48fbe2e243c'
down_revision: Union[str, None] = 'ee5204cfef15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('requests', sa.Column('region', sa.String(100), nullable=True))
    op.create_index('ix_requests_region', 'requests', ['region'])
    op.add_column('vehicles', sa.Column('region', sa.String(100), nullable=True))
    op.create_index('ix_vehicles_region', 'vehicles', ['region'])


def downgrade() -> None:
    op.drop_index('ix_vehicles_region', table_name='vehicles')
    op.drop_column('vehicles', 'region')
    op.drop_index('ix_requests_region', table_name='requests')
    op.drop_column('requests', 'region')