"""Add performance indexes for frequently queried columns

Revision ID: perf_idx_001
Revises: aa7734afe7ab
Create Date: 2026-11-10
"""

from sqlalchemy import inspect

from alembic import op

revision = "perf_idx_001"
down_revision = "aa7734afe7ab"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    insp = inspect(bind)
    return table_name in insp.get_table_names()


def _safe_create_index(bind, index_name: str, table_name: str, columns: list):
    if not _table_exists(bind, table_name):
        return
    insp = inspect(bind)
    existing = [idx["name"] for idx in insp.get_indexes(table_name)]
    if index_name not in existing:
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()

    # auth.users
    _safe_create_index(bind, "ix_users_company_id", "users", ["company_id"])
    _safe_create_index(bind, "ix_users_status", "users", ["status"])
    _safe_create_index(bind, "ix_users_created_at", "users", ["created_at"])

    # auth.user_sessions
    _safe_create_index(bind, "ix_user_sessions_user_id", "user_sessions", ["user_id"])

    # finance.invoices
    _safe_create_index(bind, "ix_invoices_company_id", "invoices", ["company_id"])
    _safe_create_index(bind, "ix_invoices_status", "invoices", ["status"])
    _safe_create_index(bind, "ix_invoices_client_id", "invoices", ["client_id"])
    _safe_create_index(bind, "ix_invoices_created_at", "invoices", ["created_at"])

    # finance.acts
    _safe_create_index(bind, "ix_acts_company_id", "acts", ["company_id"])
    _safe_create_index(bind, "ix_acts_status", "acts", ["status"])
    _safe_create_index(bind, "ix_acts_created_at", "acts", ["created_at"])

    # finance.payouts
    _safe_create_index(bind, "ix_payouts_company_id", "payouts", ["company_id"])
    _safe_create_index(bind, "ix_payouts_status", "payouts", ["status"])
    _safe_create_index(bind, "ix_payouts_owner_id", "payouts", ["owner_id"])

    # dispatch.requests
    _safe_create_index(bind, "ix_requests_status", "requests", ["status"])
    _safe_create_index(bind, "ix_requests_company_id", "requests", ["company_id"])
    _safe_create_index(bind, "ix_requests_created_at", "requests", ["created_at"])

    # maintenance.maintenance_orders
    _safe_create_index(
        bind, "ix_maintenance_orders_vehicle_id", "maintenance_orders", ["vehicle_id"]
    )
    _safe_create_index(
        bind, "ix_maintenance_orders_company_id", "maintenance_orders", ["company_id"]
    )
    _safe_create_index(
        bind, "ix_maintenance_orders_status", "maintenance_orders", ["status"]
    )

    # marketplace_offers (not marketplace_listings)
    _safe_create_index(
        bind,
        "ix_marketplace_offers_owner_company_id",
        "marketplace_offers",
        ["owner_company_id"],
    )
    _safe_create_index(
        bind, "ix_marketplace_offers_status", "marketplace_offers", ["status"]
    )

    # telematics.gps_points (recorded_at, not timestamp)
    _safe_create_index(
        bind, "ix_gps_points_vehicle_id_ts", "gps_points", ["vehicle_id", "recorded_at"]
    )

    # chat.messages
    _safe_create_index(bind, "ix_chat_messages_chat_id", "chat_messages", ["chat_id"])
    _safe_create_index(
        bind, "ix_chat_messages_created_at", "chat_messages", ["created_at"]
    )

    # notifications
    _safe_create_index(bind, "ix_notifications_user_id", "notifications", ["user_id"])
    _safe_create_index(bind, "ix_notifications_read", "notifications", ["is_read"])

    # bank_statements
    _safe_create_index(
        bind, "ix_bank_statements_company_id", "bank_statements", ["company_id"]
    )
    _safe_create_index(bind, "ix_bank_statements_status", "bank_statements", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    tables_indexes = [
        (
            "bank_statements",
            ["ix_bank_statements_company_id", "ix_bank_statements_status"],
        ),
        ("notifications", ["ix_notifications_user_id", "ix_notifications_read"]),
        ("chat_messages", ["ix_chat_messages_chat_id", "ix_chat_messages_created_at"]),
        ("gps_points", ["ix_gps_points_vehicle_id_ts"]),
        (
            "marketplace_offers",
            ["ix_marketplace_offers_owner_company_id", "ix_marketplace_offers_status"],
        ),
        (
            "maintenance_orders",
            [
                "ix_maintenance_orders_vehicle_id",
                "ix_maintenance_orders_company_id",
                "ix_maintenance_orders_status",
            ],
        ),
        (
            "requests",
            ["ix_requests_status", "ix_requests_company_id", "ix_requests_created_at"],
        ),
        (
            "payouts",
            ["ix_payouts_company_id", "ix_payouts_status", "ix_payouts_owner_id"],
        ),
        ("acts", ["ix_acts_company_id", "ix_acts_status", "ix_acts_created_at"]),
        (
            "invoices",
            [
                "ix_invoices_company_id",
                "ix_invoices_status",
                "ix_invoices_client_id",
                "ix_invoices_created_at",
            ],
        ),
        ("user_sessions", ["ix_user_sessions_user_id"]),
        ("users", ["ix_users_company_id", "ix_users_status", "ix_users_created_at"]),
    ]
    for table, indexes in tables_indexes:
        if _table_exists(bind, table):
            for idx in indexes:
                op.drop_index(idx, table_name=table)
