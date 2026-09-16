"""Add company tax settings

Revision ID: 9a1b2c3d4e5f
Revises: 0f290bb4cd77
Create Date: 2026-09-16 10:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "9a1b2c3d4e5f"  # pragma: allowlist secret
down_revision = "0f290bb4cd77"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    companies_columns = [c["name"] for c in inspector.get_columns("companies")]

    if "default_tax_system" not in companies_columns:
        op.add_column(
            "companies",
            sa.Column(
                "default_tax_system",
                sa.String(20),
                server_default="osno",
                nullable=False,
            ),
        )

    if "default_vat_rate" not in companies_columns:
        op.add_column(
            "companies",
            sa.Column(
                "default_vat_rate",
                sa.Numeric(5, 2),
                server_default="20.00",
                nullable=False,
            ),
        )

    if "default_is_vat_included" not in companies_columns:
        op.add_column(
            "companies",
            sa.Column(
                "default_is_vat_included",
                sa.Boolean(),
                server_default="true",
                nullable=False,
            ),
        )


def downgrade() -> None:
    op.drop_column("companies", "default_is_vat_included")
    op.drop_column("companies", "default_vat_rate")
    op.drop_column("companies", "default_tax_system")
