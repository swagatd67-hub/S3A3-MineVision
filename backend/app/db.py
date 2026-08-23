import logging
import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/pipevision"
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
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


def init_db() -> None:
    global _db_initialized
    if _db_initialized:
        return
    Base.metadata.create_all(bind=engine)
    # Ensure newly added columns exist on pre-existing Postgres database tables
    try:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE missions ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;")
            )
            conn.execute(
                text("ALTER TABLE missions ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;")
            )
    except (OperationalError, DatabaseError) as err:
        logger.warning("Optional schema check skipped: %s", err)
    _db_initialized = True
