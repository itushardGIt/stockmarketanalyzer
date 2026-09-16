"""SQLite engine and session helpers."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.storage.models import Base


def create_database(database_path: Path) -> sessionmaker[Session]:
    """Create the SQLite schema and return a session factory."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def session_scope(database_path: Path) -> Iterator[Session]:
    """Yield a transaction-scoped SQLite session."""
    session_factory = create_database(database_path)
    with session_factory() as session:
        yield session