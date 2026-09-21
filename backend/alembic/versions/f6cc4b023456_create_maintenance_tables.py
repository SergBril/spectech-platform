"""create maintenance tables

Revision ID: f6cc4b023456
Revises: e5bb3a012345
Create Date: 2026-09-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f6cc4b023456"  # pragma: allowlist secret
down_revision: str | None = "e5bb3a012345"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    op.drop_table("maintenance_works")
    op.drop_table("maintenance_parts")
    op.drop_table("maintenance_orders")
    op.drop_column("vehicles", "total_maintenance_cost")
    op.drop_column("vehicles", "maintenance_interval")
    op.drop_column("vehicles", "next_maintenance_hours")
    op.drop_column("vehicles", "last_maintenance_hours")
