"""Database connection and session management for FlowPilot."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.engine import Engine


class Database:
    """Database connection manager for FlowPilot.

    Handles SQLite database creation, connection, and session management.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialize the database connection.

        Args:
            db_path: Path to the SQLite database file.
                     If None, uses ~/.flowpilot/flowpilot.db
        """
        if db_path is None:
            db_path = Path.home() / ".flowpilot" / "flowpilot.db"
        elif isinstance(db_path, str):
            db_path = Path(db_path)

        # Handle special case for in-memory database
        if str(db_path) == ":memory:":
            db_url = "sqlite:///:memory:"
        else:
            # Ensure parent directory exists
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{db_path}"

        self._db_path = db_path
        self._engine: Engine = create_engine(db_url, echo=False)
        self._session_factory = sessionmaker(bind=self._engine)

    @property
    def db_path(self) -> Path:
        """Get the database file path."""
        return self._db_path

    def create_tables(self) -> None:
        """Create all database tables if they don't exist."""
        Base.metadata.create_all(self._engine)

    def drop_tables(self) -> None:
        """Drop all database tables. Use with caution!"""
        Base.metadata.drop_all(self._engine)

    def get_session(self) -> Session:
        """Get a new database session.

        The caller is responsible for closing the session.

        Returns:
            A new SQLAlchemy Session instance.
        """
        return self._session_factory()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope for database operations.

        Usage:
            with db.session_scope() as session:
                repo = ExecutionRepository(session)
                repo.create(execution)

        Yields:
            A SQLAlchemy Session that will be committed on success
            or rolled back on exception.
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Global database instance (initialized lazily)
_default_db: Database | None = None


def get_database(db_path: Path | str | None = None) -> Database:
    """Get the default database instance or create one.

    Args:
        db_path: Optional path to use for the database.
                 If provided, creates a new Database instance.
                 If None and no default exists, creates default at ~/.flowpilot/flowpilot.db

    Returns:
        The database instance.
    """
    global _default_db

    if db_path is not None:
        # Return a new instance for specific path
        return Database(db_path)

    if _default_db is None:
        _default_db = Database()
        _default_db.create_tables()

    return _default_db


def init_database(db_path: Path | str | None = None) -> Database:
    """Initialize the database with tables created.

    This is typically called during application startup or
    by the `flowpilot init` command.

    Args:
        db_path: Optional path for the database file.

    Returns:
        The initialized Database instance.
    """
    db = Database(db_path)
    db.create_tables()
    return db
