"""Database setup. SQLite by default, any SQLAlchemy URL via RIP_DATABASE_URL."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_URL = os.environ.get("RIP_DATABASE_URL", "sqlite:///rip.db")


class Base(DeclarativeBase):
    pass


_connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
# Pool settings apply to server-backed engines only. SQLite uses SingletonThread/
# NullPool depending on the URL and rejects pool_size, so passing these
# unconditionally would break the default local setup.
_pool_kwargs = (
    {}
    if DB_URL.startswith("sqlite")
    else {"pool_size": 5, "max_overflow": 10, "pool_pre_ping": True, "pool_recycle": 1800}
)
engine = create_engine(DB_URL, connect_args=_connect_args, **_pool_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

if DB_URL.startswith("sqlite"):
    from sqlalchemy import event

    _READ_ONLY = "mode=ro" in DB_URL

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        """WAL lets a serving process read while an ingest process writes;
        busy_timeout waits out a writer instead of raising 'database is locked'.

        Never enable WAL on a read-only database: WAL needs to create -wal and
        -shm sidecars, which fails on a read-only filesystem (the deployed
        snapshot) and takes the whole connection down with it.
        """
        cursor = dbapi_connection.cursor()
        try:
            if not _READ_ONLY:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        except Exception:
            pass
        finally:
            cursor.close()


def init_db() -> None:
    from . import models  # noqa: F401  ensure models are registered

    Base.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    """Minimal additive migrations for pre-existing databases."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    additive = {
        "identity_link": [("review_state", "VARCHAR(32) DEFAULT 'unreviewed'")],
        "person": [("merged_into", "VARCHAR(36)"), ("country", "VARCHAR(2)")],
    }
    _backfill_name_tokens(inspector)
    for table, columns in additive.items():
        if table not in inspector.get_table_names():
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name, ddl in columns:
            if name not in existing:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _backfill_name_tokens(inspector) -> None:
    """Populate the blocking index for persons ingested before it existed."""
    from sqlalchemy import func, select

    if "person_name_token" not in inspector.get_table_names():
        return
    from .models import Person, PersonNameToken
    from .resolution import sync_name_tokens

    with SessionLocal() as session:
        persons = session.execute(select(func.count(Person.id))).scalar_one()
        tokens = session.execute(select(func.count(PersonNameToken.id))).scalar_one()
        if persons == 0 or tokens > 0:
            return
        for person in session.execute(select(Person)).scalars():
            sync_name_tokens(session, person)
        session.commit()
