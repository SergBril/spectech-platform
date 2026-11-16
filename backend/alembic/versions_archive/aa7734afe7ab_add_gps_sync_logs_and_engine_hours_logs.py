"""add_gps_sync_logs_table

Revision ID: aa7734afe7ab
Revises: f7a8b9c0d1e2
Create Date: 2026-11-03 11:25:34.838100
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "aa7734afe7ab"  # pragma: allowlist secret
down_revision: str | None = "f7a8b9c0d1e2"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Создаём таблицу gps_sync_logs (engine_hours_logs уже существует в БД)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "gps_sync_logs" not in existing_tables:
        op.create_table(
            "gps_sync_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=True),
            sa.Column("vehicle_id", sa.Integer(), nullable=True),
            sa.Column("provider_name", sa.String(length=50), nullable=False),
            sa.Column("sync_type", sa.String(length=30), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("points_received", sa.Integer(), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["vehicle_id"],
                ["vehicles.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_gps_sync_logs_company_id"),
            "gps_sync_logs",
            ["company_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_gps_sync_logs_vehicle_id"),
            "gps_sync_logs",
            ["vehicle_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_gps_sync_logs_vehicle_id"), table_name="gps_sync_logs")
    op.drop_index(op.f("ix_gps_sync_logs_company_id"), table_name="gps_sync_logs")
    op.drop_table("gps_sync_logs")
