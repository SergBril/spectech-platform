"""add rental_id to invoices and make request_id nullable

Revision ID: a4d1a15f105e
Revises: db76ca9f4b93
Create Date: 2026-10-07 ...

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a4d1a15f105e"
down_revision: str | None = "db76ca9f4b93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Добавляем rental_id в invoices
    op.add_column("invoices", sa.Column("rental_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "invoices_rental_id_fkey",
        "invoices",
        "rentals",
        ["rental_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 2. Делаем request_id nullable
    op.alter_column("invoices", "request_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column(
        "invoices", "request_id", existing_type=sa.Integer(), nullable=False
    )
    op.drop_constraint("invoices_rental_id_fkey", "invoices", type_="foreignkey")
    op.drop_column("invoices", "rental_id")
