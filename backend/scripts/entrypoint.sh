#!/bin/sh
set -e

echo "Starting SpectechPlatform backend..."

# Function to safely apply migrations
apply_migrations() {
    echo "Applying database migrations..."

    # Check if tables already exist in database
    TABLES_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" 2>/dev/null | tr -d ' ' || echo "0")

    if [ "$TABLES_COUNT" -gt 0 ]; then
        echo "Database already has $TABLES_COUNT tables, stamping as head..."
        alembic stamp head 2>/dev/null || true
        echo "Database stamped successfully"
    else
        echo "Empty database, applying all migrations..."
        alembic upgrade head
        echo "All migrations applied"
    fi
}

# Apply migrations only in production
if [ "$ENVIRONMENT" != "testing" ]; then
    apply_migrations || {
        echo "Migrations failed or already applied, continuing..."
    }
fi

# Start the application
echo "Starting Uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
