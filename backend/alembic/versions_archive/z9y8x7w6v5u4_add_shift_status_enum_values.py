"""Add planned/confirmed/in_progress statuses to shift_task_status enum."""

from alembic import op

revision = "z9y8x7w6v5u4"  # pragma: allowlist secret
down_revision = "c284d8731081"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum values to PostgreSQL enum type
    op.execute("ALTER TYPE shift_task_status ADD VALUE IF NOT EXISTS 'planned'")
    op.execute("ALTER TYPE shift_task_status ADD VALUE IF NOT EXISTS 'confirmed'")
    op.execute("ALTER TYPE shift_task_status ADD VALUE IF NOT EXISTS 'in_progress'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values
    pass
