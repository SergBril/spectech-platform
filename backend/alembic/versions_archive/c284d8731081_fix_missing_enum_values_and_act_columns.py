"""fix_missing_enum_values_and_act_columns

Revision ID: c284d8731081
Revises: perf_idx_001
Create Date: 2026-11-11 07:09:35.398614

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c284d8731081"  # pragma: allowlist secret
down_revision: str | None = "perf_idx_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # === ENUM FIXES ===
    # shift_task_status: add cancelled
    op.execute("ALTER TYPE shift_task_status ADD VALUE IF NOT EXISTS 'cancelled'")

    # document_status: add missing values
    for val in [
        "sent_to_edo",
        "signed_by_client",
        "rejected_by_client",
        "signed",
        "sent_to_client",
        "accepted",
        "archived",
    ]:
        op.execute(f"ALTER TYPE document_status ADD VALUE IF NOT EXISTS '{val}'")

    # request_status: add missing values
    for val in ["has_responses", "expired", "draft"]:
        op.execute(f"ALTER TYPE request_status ADD VALUE IF NOT EXISTS '{val}'")

    # === ACTS TABLE: add missing columns ===
    op.execute(
        """
        ALTER TABLE acts
        ADD COLUMN IF NOT EXISTS hours_worked DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS hourly_rate DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS vehicle_id INTEGER REFERENCES vehicles(id),
        ADD COLUMN IF NOT EXISTS driver_id INTEGER,
        ADD COLUMN IF NOT EXISTS shift_task_id INTEGER,
        ADD COLUMN IF NOT EXISTS period_start DATE,
        ADD COLUMN IF NOT EXISTS period_end DATE,
        ADD COLUMN IF NOT EXISTS act_type VARCHAR(30) DEFAULT 'standard'
    """
    )


def downgrade() -> None:
    # Note: PostgreSQL does not support removing enum values.
    # Columns can be dropped if needed:
    op.execute(
        """
        ALTER TABLE acts
        DROP COLUMN IF EXISTS act_type,
        DROP COLUMN IF EXISTS period_end,
        DROP COLUMN IF EXISTS period_start,
        DROP COLUMN IF EXISTS shift_task_id,
        DROP COLUMN IF EXISTS driver_id,
        DROP COLUMN IF EXISTS vehicle_id,
        DROP COLUMN IF EXISTS hourly_rate,
        DROP COLUMN IF EXISTS hours_worked
    """
    )
