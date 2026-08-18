from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

is_sqlite = settings.database_url.startswith("sqlite")

# check_same_thread=False is required for SQLite because BackgroundTasks
# runs the pipeline on a different thread than the request that queued it.
# The timeout makes a blocked writer wait rather than fail instantly.
connect_args = {"check_same_thread": False, "timeout": 30.0} if is_sqlite else {}

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)

if is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        """WAL lets readers run while one writer works.

        Without it, concurrent scrape jobs deadlock: each holds a write
        transaction across slow network calls and the others block forever.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables. Fine for MVP; swap for Alembic migrations before deploy."""
    from app import models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)


def is_postgres() -> bool:
    return engine.dialect.name == "postgresql"
