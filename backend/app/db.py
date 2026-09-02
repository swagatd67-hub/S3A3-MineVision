"""Database production readiness layer for PipeVision with connection pooling and health checks."""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_db_initialized = False


def check_database_connection() -> tuple[bool, str]:
    """Check database connectivity for readiness probes."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return True, "database_connected"
    except (SQLAlchemyError, OSError, ValueError) as exc:
        return False, f"database_error: {exc}"


def init_db() -> None:
    """Initialize database tables and run safe, non-destructive schema migrations."""
    global _db_initialized
    if _db_initialized:
        return

    Base.metadata.create_all(bind=engine)

    # Safe idempotent PostGIS & schema extensions check
    try:
        with engine.begin() as conn:
            # PostGIS initialization attempt (swallowing permission errors if non-superuser)
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            except (OperationalError, DatabaseError) as postgis_err:
                logger.info("PostGIS extension check skipped or unprivileged: %s", postgis_err)

            conn.execute(
                text("ALTER TABLE missions ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;")
            )
            conn.execute(
                text("ALTER TABLE missions ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;")
            )
            try:
                conn.execute(
                    text("ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS gas JSON;")
                )
            except Exception as err:  # noqa: BLE001
                logger.info("Telemetry gas column check skipped: %s", err)
    except (OperationalError, DatabaseError) as err:

        logger.warning("Optional schema check skipped: %s", err)

    _db_initialized = True


def close_db() -> None:
    """Dispose engine connections on shutdown."""
    engine.dispose()
