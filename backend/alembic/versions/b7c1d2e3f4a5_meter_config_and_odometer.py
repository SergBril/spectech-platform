"""meter config per category and odometer fields on vehicles

Revision ID: b7c1d2e3f4a5
Revises: a43d5ef44075
Create Date: 2026-11-18

Счётчики различаются по типу техники: гусеничный экскаватор не имеет одометра,
автокран имеет и пробег шасси, и моточасы надстройки - это два регламента разных
производителей. Одно число интервала на весь парк неверно.

Пресеты заполнены ТОЛЬКО там, где есть источник (руководство производителя или
официальный регламент). Остальные оставлены NULL: выдуманное число хуже пустого,
потому что выглядит как регламент.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7c1d2e3f4a5"  # pragma: allowlist secret
down_revision: str | None = "a43d5ef44075"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# code -> (tracks_odometer, tracks_engine_hours, basis, interval_h, interval_km)
HOURS_ONLY = [
    "excavator-tracked",
    "mini-excavator",
    "wheel-loader",
    "skid-steer-loader",
    "bulldozer",
    "road-roller",
    "asphalt-paver",
    "generator",
    "compressor",
]
HOURS_PRIMARY_WITH_ODO = [
    "excavator-wheeled",
    "backhoe-loader",
    "telehandler",
    "grader",
    "scraper",
]
BOTH_AXES = [
    "aerial-platform",
    "truck-crane",
    "manipulator",
    "auger",
    "drilling-rig",
    "pile-driver",
    "concrete-pump-truck",
    "concrete-mixer",
    "garbage-truck",
    "snow-removal",
]
ODO_PRIMARY = ["dump-truck", "lowbed-trailer", "tonar_trailers", "cover_vehicles"]

# Пресеты с источником:
#   excavator-tracked 500 м/ч - Operation and Maintenance Manual Cat 320D
#   bulldozer 250 м/ч - Cat planned maintenance PM1
#   backhoe-loader 500 м/ч - регламент JCB 3CX/4CX (250 в тяжёлых условиях)
#   dump-truck 10000 км - КАМАЗ ТО-1 Евро-3, неполноприводный, I категория
PRESETS = {
    "excavator-tracked": (500, None),
    "bulldozer": (250, None),
    "backhoe-loader": (500, None),
    "dump-truck": (None, 10000),
}


def upgrade() -> None:
    op.add_column(
        "vehicles", sa.Column("odometer_km", sa.Numeric(10, 1), nullable=True)
    )
    op.add_column(
        "vehicles", sa.Column("maintenance_interval_km", sa.Integer(), nullable=True)
    )
    op.add_column(
        "vehicles", sa.Column("last_maintenance_km", sa.Numeric(10, 1), nullable=True)
    )
    op.add_column(
        "vehicles", sa.Column("next_maintenance_km", sa.Numeric(10, 1), nullable=True)
    )

    op.add_column(
        "categories",
        sa.Column(
            "tracks_odometer", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "categories",
        sa.Column(
            "tracks_engine_hours",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "categories",
        sa.Column(
            "maintenance_basis",
            sa.String(20),
            nullable=False,
            server_default="engine_hours",
        ),
    )
    op.add_column(
        "categories", sa.Column("default_interval_hours", sa.Integer(), nullable=True)
    )
    op.add_column(
        "categories", sa.Column("default_interval_km", sa.Integer(), nullable=True)
    )

    conn = op.get_bind()

    def apply(codes, odo, hours, basis):
        if not codes:
            return
        conn.execute(
            sa.text(
                "UPDATE categories SET tracks_odometer=:o, tracks_engine_hours=:h, "
                "maintenance_basis=:b WHERE code = ANY(:codes)"
            ),
            {"o": odo, "h": hours, "b": basis, "codes": list(codes)},
        )

    apply(HOURS_ONLY, False, True, "engine_hours")
    apply(HOURS_PRIMARY_WITH_ODO, True, True, "engine_hours")
    apply(BOTH_AXES, True, True, "both")
    apply(ODO_PRIMARY, True, True, "odometer")

    for code, (ih, ikm) in PRESETS.items():
        conn.execute(
            sa.text(
                "UPDATE categories SET default_interval_hours=:ih, default_interval_km=:ikm "
                "WHERE code=:c"
            ),
            {"ih": ih, "ikm": ikm, "c": code},
        )


def downgrade() -> None:
    for col in (
        "default_interval_km",
        "default_interval_hours",
        "maintenance_basis",
        "tracks_engine_hours",
        "tracks_odometer",
    ):
        op.drop_column("categories", col)
    for col in (
        "next_maintenance_km",
        "last_maintenance_km",
        "maintenance_interval_km",
        "odometer_km",
    ):
        op.drop_column("vehicles", col)
