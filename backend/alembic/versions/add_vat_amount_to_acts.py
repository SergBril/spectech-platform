"""add vat_amount to acts

Revision ID: add_vat_amount_001
Revises: add_vat_rate_002
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "add_vat_amount_001"  # pragma: allowlist secret
down_revision: str | None = "add_vat_rate_002"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    act_columns = [col["name"] for col in inspector.get_columns("acts")]

    if "vat_amount" not in act_columns:
        op.add_column(
            "acts",
            sa.Column(
                "vat_amount",
                sa.Numeric(precision=14, scale=2),
                server_default="0",
                nullable=False,
                comment="Сумма НДС",
            ),
        )


def downgrade() -> None:
    op.drop_column("acts", "vat_amount")
