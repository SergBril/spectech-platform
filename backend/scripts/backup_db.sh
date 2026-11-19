#!/bin/sh
# SpectechPlatform — PostgreSQL Backup Script
# Usage: ./scripts/backup_db.sh [retention_days]
# Designed to run via cron or docker exec

set -euo pipefail

RETENTION_DAYS=${1:-30}
BACKUP_DIR="/backups"
# Каталог textfile-метрики для node-exporter (--collector.textfile.directory).
# Общий том с node-exporter; метрика видна Prometheus как job="node-exporter".
METRICS_DIR="${BACKUP_METRICS_DIR:-/metrics}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="spectech_${TIMESTAMP}.sql.gz"

# Use env vars from docker-compose / .env.prod
: "${POSTGRES_USER:?POSTGRES_USER not set}"
: "${POSTGRES_DB:?POSTGRES_DB not set}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD not set}"
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"

mkdir -p "$BACKUP_DIR" "$METRICS_DIR"

echo "[$(date)] Starting backup of ${POSTGRES_DB}..."

if pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB"     --format=custom --compress=9 --file="${BACKUP_DIR}/${FILENAME}" 2>&1; then
    SIZE=$(du -h "${BACKUP_DIR}/${FILENAME}" | cut -f1)
    echo "[$(date)] Backup complete: ${FILENAME} (${SIZE})"
    # Метрика последнего УСПЕШНОГО бэкапа — ТОЛЬКО здесь, после подтверждённого
    # успеха pg_dump (exit 0) и непустого файла. В ветке else (дамп упал) НЕ
    # пишем: timestamp остаётся старым, и BackupTooOld не маскирует отказ.
    # Атомарная запись (tmp+mv), чтобы node-exporter не читал неполный файл.
    if [ -s "${BACKUP_DIR}/${FILENAME}" ]; then
        printf '# HELP backup_last_success_timestamp_seconds Unix time of the last successful pg_dump.\n# TYPE backup_last_success_timestamp_seconds gauge\nbackup_last_success_timestamp_seconds %s\n' \
            "$(date +%s)" > "${METRICS_DIR}/backup_last_success.prom.tmp"
        mv "${METRICS_DIR}/backup_last_success.prom.tmp" "${METRICS_DIR}/backup_last_success.prom"
    fi
else
    echo "[$(date)] ERROR: Backup failed!" >&2
    exit 1
fi

# Cleanup old backups
DELETED=$(find "$BACKUP_DIR" -name "spectech_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "[$(date)] Cleaned up ${DELETED} backup(s) older than ${RETENTION_DAYS} days"
fi

echo "[$(date)] Backup job finished successfully"
