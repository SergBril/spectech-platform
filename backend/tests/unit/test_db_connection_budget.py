"""Guard the connection budget: workers * (pool + overflow) must fit Postgres."""

from app.core.config import settings

UVICORN_WORKERS_DEFAULT = 4  # entrypoint.sh: WORKERS=${UVICORN_WORKERS:-4}
PG_MAX_CONNECTIONS = 100
RESERVED_FOR_TOOLS = 20  # psql, alembic, GlitchTip, monitoring


class TestConnectionBudget:
    def test_pool_budget_fits_postgres_limit(self):
        total = UVICORN_WORKERS_DEFAULT * (
            settings.db_pool_size + settings.db_max_overflow
        )
        assert total <= PG_MAX_CONNECTIONS - RESERVED_FOR_TOOLS, (
            f"{UVICORN_WORKERS_DEFAULT} workers x "
            f"({settings.db_pool_size}+{settings.db_max_overflow}) = {total} "
            f"exceeds the safe budget"
        )

    def test_pool_sizes_are_positive(self):
        assert settings.db_pool_size > 0
        assert settings.db_max_overflow >= 0
        assert settings.db_pool_timeout > 0
