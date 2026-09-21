"""marketplace fields company vehicle

Revision ID: 7230a9b5e733
Revises: 9a1b2c3d4e5f
Create Date: 2026-09-XX
"""

from collections.abc import Sequence  # ← ДОБАВЬТЕ ЭТУ СТРОКУ

from alembic import op

revision: str = "7230a9b5e733"  # pragma: allowlist secret
down_revision: str | None = "9a1b2c3d4e5f"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Поля уже добавлены прямым SQL, миграция только для отметки в alembic_version
    pass


def downgrade() -> None:
    with op.batch_alter_table("vehicles", schema=None) as batch_op:
        batch_op.drop_column("base_location_lon")
        batch_op.drop_column("base_location_lat")
        batch_op.drop_column("description")
        batch_op.drop_column("photos")
        batch_op.drop_column("shift_rate")
        batch_op.drop_column("hourly_rate")
        batch_op.drop_column("is_available_for_rent")

    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.drop_column("is_verified")
        batch_op.drop_column("website")
        batch_op.drop_column("phone")
        batch_op.drop_column("city")
        batch_op.drop_column("logo_url")
        batch_op.drop_column("description")
        batch_op.drop_column("company_type")
