"""add_shift_report_photos_and_signatures

Revision ID: 684efc6be9bd
Revises: bb817b656eaf
Create Date: 2026-10-05 ...

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "684efc6be9bd"
down_revision: str | None = "bb817b656eaf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Только добавление колонок в shift_reports — без мусорных alter_column для disputes
    op.add_column(
        "shift_reports", sa.Column("operator_photos", sa.JSON(), nullable=True)
    )
    op.add_column(
        "shift_reports", sa.Column("operator_signature", sa.Text(), nullable=True)
    )
    op.add_column(
        "shift_reports",
        sa.Column("operator_signed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "shift_reports", sa.Column("client_signature", sa.Text(), nullable=True)
    )
    op.add_column(
        "shift_reports",
        sa.Column("client_signed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shift_reports", "client_signed_at")
    op.drop_column("shift_reports", "client_signature")
    op.drop_column("shift_reports", "operator_signed_at")
    op.drop_column("shift_reports", "operator_signature")
    op.drop_column("shift_reports", "operator_photos")
