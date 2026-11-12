"""unique gps point per vehicle and timestamp

Revision ID: 56df21b4b7f0
Revises: c87714d5dde4
Create Date: 2026-11-12 17:58:49.279396

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "56df21b4b7f0"  # pragma: allowlist secret
down_revision: str | None = "c87714d5dde4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Guarantee one GPS point per (vehicle_id, recorded_at) at DB level.

    An application-level "read then insert" check cannot prevent duplicates
    under concurrency: with uvicorn --workers 4 each worker ran its own
    scheduler and two of them inserted the same minute within 0.026s.
    The index includes the partition column and matches the compression
    settings (segmentby=vehicle_id, orderby=recorded_at DESC), so TimescaleDB
    accepts it on compressed chunks.
    """
    conn = op.get_bind()

    # DELETE requires decompressed chunks
    chunks = conn.execute(
        sa.text(
            "SELECT chunk_schema || '.' || chunk_name "
            "FROM timescaledb_information.chunks "
            "WHERE hypertable_name = 'gps_points' AND is_compressed"
        )
    ).fetchall()
    for (name,) in chunks:
        conn.execute(
            sa.text(f"SELECT decompress_chunk('{name}', if_compressed => true)")
        )

    # keep the best row per (vehicle_id, recorded_at): prefer filled speed
    conn.execute(
        sa.text(
            """
            DELETE FROM gps_points g
            USING (
                SELECT id, recorded_at,
                       row_number() OVER (
                           PARTITION BY vehicle_id, recorded_at
                           ORDER BY (speed IS NULL), id
                       ) AS rn
                FROM gps_points
            ) d
            WHERE g.id = d.id AND g.recorded_at = d.recorded_at AND d.rn > 1
            """
        )
    )

    op.create_index(
        "ix_gps_points_vehicle_ts_uniq",
        "gps_points",
        ["vehicle_id", "recorded_at"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_gps_points_vehicle_ts_uniq", table_name="gps_points")
