"""fix marketplace commission rate precision

Revision ID: c87714d5dde4
Revises: z9y8x7w6v5u4
Create Date: 2026-11-12 16:08:10.520236

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c87714d5dde4"
down_revision: str | None = "z9y8x7w6v5u4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """numeric(5,4) fraction -> numeric(5,2) percent.

    The column held 0.1000 (a fraction) with server_default 0.1, while the
    ORM model, rentals/payouts columns and calculate_payout() all treat the
    rate as a PERCENT. numeric(5,4) caps at 9.9999, so the vehicle form
    sending 10.00 raised numeric field overflow and the UI showed 0.1%.
    """
    op.alter_column(
        "vehicles",
        "marketplace_commission_rate",
        existing_type=sa.Numeric(5, 4),
        type_=sa.Numeric(5, 2),
        existing_nullable=True,
        server_default="10.00",
        postgresql_using=(
            "CASE WHEN marketplace_commission_rate < 1 "
            "THEN marketplace_commission_rate * 100 "
            "ELSE marketplace_commission_rate END"
        ),
    )


def downgrade() -> None:
    op.alter_column(
        "vehicles",
        "marketplace_commission_rate",
        existing_type=sa.Numeric(5, 2),
        type_=sa.Numeric(5, 4),
        existing_nullable=True,
        server_default="0.1",
        postgresql_using="marketplace_commission_rate / 100",
    )
