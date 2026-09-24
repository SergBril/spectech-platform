"""add vat_rate and has_invoice_facture to acts

Revision ID: add_vat_rate_002
Revises: 950950b062e8
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "add_vat_rate_002"  # pragma: allowlist secret
down_revision: str | None = "950950b062e8"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    act_columns = [col["name"] for col in inspector.get_columns("acts")]

    if "vat_rate" not in act_columns:
        op.add_column(
            "acts",
            sa.Column(
                "vat_rate",
                sa.Integer(),
                server_default="22",
                nullable=False,
                comment="Ставка НДС (20 или 22)",
            ),
        )

    if "has_invoice_facture" not in act_columns:
        op.add_column(
            "acts",
            sa.Column(
                "has_invoice_facture",
                sa.Boolean(),
                server_default="false",
                nullable=False,
                comment="Генерировать счёт-фактуру (для ОСНО)",
            ),
        )


def downgrade() -> None:
    op.drop_column("acts", "has_invoice_facture")
    op.drop_column("acts", "vat_rate")
