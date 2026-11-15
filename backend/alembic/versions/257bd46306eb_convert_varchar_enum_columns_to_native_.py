"""convert varchar enum columns to native enum types

Revision ID: 257bd46306eb
Revises: f9000521b079
Create Date: 2026-11-15 15:57:02.843935

"""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "257bd46306eb"  # pragma: allowlist secret
down_revision: str | None = "f9000521b079"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (table, column, pg type name, member names, nullable)
_ENUMS = [
    (
        "disputes",
        "assigned_role",
        "assigned_role",
        ["dispatcher", "manager", "ceo"],
        True,
    ),
    (
        "disputes",
        "dispute_type",
        "dispute_type",
        ["hours", "mileage", "fuel", "idle", "damage", "other"],
        False,
    ),
    (
        "disputes",
        "initiator_role",
        "initiator_role",
        ["operator", "client", "client_rep"],
        False,
    ),
    (
        "disputes",
        "status",
        "dispute_status",
        [
            "open",
            "dispatcher_review",
            "escalated_to_manager",
            "escalated_to_ceo",
            "resolved",
            "closed",
        ],
        False,
    ),
    (
        "downtime_events",
        "cause_category",
        "downtime_cause",
        [
            "waiting_client",
            "waiting_site",
            "technical",
            "weather",
            "operator_rest",
            "operator_fault",
            "fuel",
            "delivery",
            "force_majeure",
            "other",
        ],
        False,
    ),
    (
        "downtime_events",
        "fault_party",
        "fault_party",
        ["client", "owner", "operator", "platform", "none"],
        False,
    ),
    (
        "downtime_events",
        "status",
        "downtime_status",
        ["pending", "approved", "rejected"],
        False,
    ),
    (
        "rentals",
        "prepayment_status",
        "prepayment_status",
        ["none", "required", "paid", "refunded"],
        False,
    ),
    (
        "rentals",
        "rate_type",
        "rate_type",
        ["hourly", "shift", "trip", "volume", "mileage", "combined"],
        False,
    ),
    (
        "rentals",
        "status",
        "rental_status",
        ["draft", "active", "overdue", "completed", "cancelled"],
        False,
    ),
]


def upgrade() -> None:
    """Match the project convention: native enum types, not VARCHAR.

    27 columns are declared as Enum in the models; 16 already used native
    types while these stayed VARCHAR from early migrations. The drift check
    skipped enum columns instead of flagging them, so this was invisible.
    Every affected table was verified empty before writing this.

    The default must be dropped first: PostgreSQL cannot cast a varchar
    default to an enum automatically, and re-applying it with an explicit
    cast keeps the semantics (a new dispute still opens as 'open').
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    for table, column, type_name, values, nullable in _ENUMS:
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        raw_default = cols.get(column, {}).get("default")
        literal = None
        if raw_default:
            match = re.match(r"^'([^']*)'::", str(raw_default))
            if match:
                literal = match.group(1)
            op.alter_column(table, column, server_default=None)

        enum_type = postgresql.ENUM(*values, name=type_name)
        enum_type.create(bind, checkfirst=True)
        op.alter_column(
            table,
            column,
            type_=enum_type,
            existing_nullable=nullable,
            postgresql_using=f"{column}::" + type_name,
        )
        if literal is not None:
            op.alter_column(
                table,
                column,
                server_default=text("'" + literal + "'::" + type_name),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for table, column, type_name, values, nullable in _ENUMS:
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        raw_default = cols.get(column, {}).get("default")
        literal = None
        if raw_default:
            match = re.match(r"^'([^']*)'::", str(raw_default))
            if match:
                literal = match.group(1)
            op.alter_column(table, column, server_default=None)

        op.alter_column(
            table,
            column,
            type_=sa.VARCHAR(),
            existing_nullable=nullable,
            postgresql_using=f"{column}::varchar",
        )
        if literal is not None:
            op.alter_column(
                table,
                column,
                server_default=text("'" + literal + "'::character varying"),
            )
        postgresql.ENUM(name=type_name).drop(bind, checkfirst=True)
