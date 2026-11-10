import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Connection pool tuning ────────────────────────────────────────
# pool_pre_ping:  verify connections before use (catchs stale/DROPped conns)
# pool_recycle:   recycle connections after 30 min (avoid PG idle timeout)
# pool_size:      steady-state connections per worker
# max_overflow:   burst connections above pool_size
# pool_timeout:   seconds to wait for a connection before raising
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,  # 30 min — well below PG default idle_in_transaction_session_timeout
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    connect_args=(
        {"sslmode": "disable"} if "postgresql" in settings.database_url else {}
    ),
)


# ── Retry on transient disconnects ───────────────────────────────
@event.listens_for(engine, "handle_error")
def _handle_db_error(context):
    """Log and allow SQLAlchemy to retry on disconnect."""
    if context.is_disconnect:
        logger.warning(
            "Database disconnect detected, connection will be recycled: %s",
            context.original_exception,
        )


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a DB session with guaranteed cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
