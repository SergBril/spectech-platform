"""author of a marketplace response

Revision ID: d9e3f4a5b6c7
Revises: c8d2e3f4a5b6
"""

import sqlalchemy as sa

from alembic import op

revision: str = "d9e3f4a5b6c7"  # pragma: allowlist secret
down_revision: str | None = "c8d2e3f4a5b6"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("request_assignments", "created_by_user_id"):
        op.add_column(
            "request_assignments",
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_request_assignments_created_by_user",
            "request_assignments",
            "users",
            ["created_by_user_id"],
            ["id"],
        )


def downgrade() -> None:
    if _has_column("request_assignments", "created_by_user_id"):
        op.drop_constraint(
            "fk_request_assignments_created_by_user",
            "request_assignments",
            type_="foreignkey",
        )
        op.drop_column("request_assignments", "created_by_user_id")
