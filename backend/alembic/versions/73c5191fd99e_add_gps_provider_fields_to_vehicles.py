"""add gps_provider fields to vehicles

Revision ID: 73c5191fd99e
Revises: 52d24caa286b
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa


revision = '73c5191fd99e'
down_revision = '52d24caa286b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('vehicles', sa.Column('gps_provider', sa.String(50), nullable=True, comment='GPS provider: wialon, gdemoi, gps_trace, mapix, manual'))
    op.add_column('vehicles', sa.Column('gps_provider_config', sa.JSON(), nullable=True, comment='Provider-specific config: {api_key, unit_id, device_id, login, password, api_url}'))


def downgrade() -> None:
    op.drop_column('vehicles', 'gps_provider_config')
    op.drop_column('vehicles', 'gps_provider')