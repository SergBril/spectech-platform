"""Add overbooking protection constraint

Revision ID: add_overbooking_protection
Revises: 03f5053871de
Create Date: 2026-10-02

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_overbooking_protection"
down_revision = "03f5053871de"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Добавляем EXCLUDE constraint для защиты от овербукинга.

    Этот constraint физически не позволит создать пересекающиеся назначения
    для одной и той же техники в одно и то же время.

    Работает только в PostgreSQL (не в SQLite).
    Для SQLite защита остаётся на уровне приложения.
    """
    # Проверяем, что это PostgreSQL (для SQLite пропускаем)
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Создаём расширение btree_gist если его нет
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")

    # Добавляем EXCLUDE constraint
    # vehicle_id WITH = — одинаковая техника
    # tstzrange(planned_start, planned_end) WITH && — пересекающиеся периоды
    # WHERE (status NOT IN ('cancelled')) — исключаем отменённые назначения
    op.execute(
        """
        ALTER TABLE request_assignments
        ADD CONSTRAINT prevent_overbooking
        EXCLUDE USING gist (
            vehicle_id WITH =,
            tstzrange(planned_start, planned_end) WITH &&
        ) WHERE (status NOT IN ('cancelled', 'completed'))
    """
    )

    # Создаём индекс для ускорения проверок
    op.create_index(
        "idx_request_assignments_vehicle_period",
        "request_assignments",
        ["vehicle_id", "planned_start", "planned_end"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    """Удаляем constraint и индекс."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index(
        "idx_request_assignments_vehicle_period", table_name="request_assignments"
    )
    op.drop_constraint("prevent_overbooking", "request_assignments", type_="exclude")
