"""Sprint 3 Task 1: Convert gps_points to TimescaleDB hypertable

Revision ID: sprint3_002
Revises: sprint3_001
Create Date: 2026-09-28
"""

from alembic import op

revision = "sprint3_002"
down_revision = "sprint3_001"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Extension уже создан через shared_preload_libraries
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # 2. TimescaleDB требует чтобы колонка партиционирования была в PK
    # Преобразуем PK(id) в PK(id, recorded_at)

    # Находим имя текущего primary key constraint
    op.execute(
        """
        DO $$
        DECLARE
            pk_name TEXT;
        BEGIN
            SELECT con.conname INTO pk_name
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE rel.relname = 'gps_points'
              AND nsp.nspname = 'public'
              AND con.contype = 'p';

            IF pk_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE gps_points DROP CONSTRAINT %I', pk_name);
            END IF;
        END $$;
    """
    )

    # Создаём новый составной PK
    op.execute(
        """
        ALTER TABLE gps_points
        ADD PRIMARY KEY (id, recorded_at);
    """
    )

    # 3. Преобразуем в hypertable
    op.execute(
        """
        SELECT create_hypertable(
            'gps_points',
            'recorded_at',
            chunk_time_interval => INTERVAL '1 day',
            migrate_data => true,
            if_not_exists => true
        );
    """
    )

    # 4. Настраиваем сжатие
    try:
        op.execute(
            """
            ALTER TABLE gps_points SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'vehicle_id',
                timescaledb.compress_orderby = 'recorded_at DESC'
            );
        """
        )
    except Exception:
        pass

    # 5. Политика сжатия
    op.execute(
        """
        SELECT add_compression_policy(
            'gps_points',
            INTERVAL '7 days',
            if_not_exists => true
        );
    """
    )

    # 6. Политика удаления старых данных
    op.execute(
        """
        SELECT add_retention_policy(
            'gps_points',
            INTERVAL '2 years',
            if_not_exists => true
        );
    """
    )

    # 7. Continuous aggregate для часовой агрегации
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_hourly_summary
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', recorded_at) AS hour,
            vehicle_id,
            COUNT(*) AS data_points_count,
            AVG(speed) AS avg_speed_kmh,
            MAX(speed) AS max_speed_kmh,
            AVG(fuel_level) AS avg_fuel_level,
            MIN(fuel_level) AS min_fuel_level,
            MAX(fuel_level) AS max_fuel_level,
            SUM(CASE WHEN engine_on = true THEN 1 ELSE 0 END) AS engine_on_count,
            AVG(engine_hours) AS avg_engine_hours
        FROM gps_points
        GROUP BY hour, vehicle_id
        WITH NO DATA;
    """
    )

    # 8. Политика обновления continuous aggregate
    op.execute(
        """
        SELECT add_continuous_aggregate_policy(
            'telemetry_hourly_summary',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => true
        );
    """
    )


def downgrade():
    op.execute(
        "SELECT remove_continuous_aggregate_policy('telemetry_hourly_summary', if_exists => true);"
    )
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly_summary CASCADE;")
    op.execute("SELECT remove_retention_policy('gps_points', if_exists => true);")
    op.execute("SELECT remove_compression_policy('gps_points', if_exists => true);")

    try:
        op.execute("ALTER TABLE gps_points SET (timescaledb.compress = false);")
    except Exception:
        pass

    # Возвращаем обычный PK
    op.execute("ALTER TABLE gps_points DROP CONSTRAINT gps_points_pkey;")
    op.execute("ALTER TABLE gps_points ADD PRIMARY KEY (id);")
