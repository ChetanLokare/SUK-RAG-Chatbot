# backend/core/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator

from backend.core.config import DATABASE_URL, SQLITE_DB_PATH


# ======================================================
# ENGINE (SAFE SQLITE CONFIG)
# ======================================================

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite
    pool_pre_ping=True,
)


# ======================================================
# SESSION FACTORY
# ======================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ======================================================
# BASE MODEL
# ======================================================

Base = declarative_base()


# ======================================================
# INITIALIZE DATABASE
# ======================================================

def init_db() -> None:
    """
    Create tables safely.
    Ensures DB file exists in correct location.
    """

    # Ensure parent directory exists
    SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Register models
    import backend.registry.models  # noqa

    Base.metadata.create_all(bind=engine)

    print(f"✅ Database initialized at: {SQLITE_DB_PATH.resolve()}")


# ======================================================
# DB DEPENDENCY (FASTAPI)
# ======================================================

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
