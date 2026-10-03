from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


engine = create_engine(
    settings.get_database_url(),
    pool_pre_ping=True,
    future=True,
    # Supabase transaction pooler (pgBouncer on port 6543) does not support
    # prepared statements. Disable them at the psycopg3 driver level.
    connect_args={"prepare_threshold": None},
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    Provide a database session for FastAPI routes and services.

    The session is automatically closed after the request finishes.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
