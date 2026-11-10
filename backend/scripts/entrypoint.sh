#!/bin/sh
set -e

echo "Starting SpectechPlatform backend..."

apply_migrations() {
    echo "Applying database migrations..."

    if alembic upgrade head 2>&1; then
        echo "Migrations applied successfully"
    else
        echo "alembic upgrade head failed, attempting recovery..."

        HAS_ALEMBIC_VERSION=$(psql "$DATABASE_URL" -t -c \
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'alembic_version';" \
            2>/dev/null | tr -d ' ' || echo "0")

        if [ "$HAS_ALEMBIC_VERSION" = "0" ]; then
            echo "No alembic_version table found, stamping as head..."
            alembic stamp head
            echo "Database stamped as head"
        else
            echo "Migration failed with existing alembic_version. Manual intervention required."
            echo "Current revision:"
            alembic current 2>&1 || true
            echo "Pending revisions:"
            alembic history -r current:head 2>&1 || true
            exit 1
        fi
    fi
}

if [ "$ENVIRONMENT" != "testing" ]; then
    apply_migrations
fi

WORKERS=${UVICORN_WORKERS:-4}
GRACEFUL_TIMEOUT=${UVICORN_GRACEFUL_TIMEOUT:-30}

echo "Starting Uvicorn with $WORKERS workers, graceful timeout ${GRACEFUL_TIMEOUT}s..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "$WORKERS" \
    --timeout-graceful-shutdown "$GRACEFUL_TIMEOUT" \
    --log-level info
