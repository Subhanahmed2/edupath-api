"""
The database connection (SQLAlchemy 2 + psycopg2).

DATABASE_URL in backend/.env decides where the data lives:
  - Neon cloud PostgreSQL (shared by every PC):  the "pooled" connection string from the Neon dashboard
  - a local PostgreSQL server:                   postgresql+psycopg2://user:password@localhost:5432/edupath
  - not set:                                     a SQLite file, backend/data/edupath.db (tests and quick demos)
"""
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import settings

DATA_DIR = settings.ROOT / "backend" / "data"
DATA_DIR.mkdir(exist_ok=True)


def _normalise(url: str) -> str:
    """Accept cloud links as copied (e.g. from Neon): postgres:// -> postgresql+psycopg2://, and require SSL
    for any non-local server unless the link already says how (Neon refuses unencrypted connections)."""
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    if url.startswith("postgresql") and "sslmode=" not in url:
        host = url.split("@")[-1].split("/")[0].split(":")[0]
        if host not in ("localhost", "127.0.0.1", "::1"):
            url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


DATABASE_URL = _normalise(os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'edupath.db').as_posix()}").strip())
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {"connect_timeout": 10},
    pool_pre_ping=True,  # test a connection before using it (cloud servers close idle ones)
    # Neon suspends an idle database after ~5 minutes and drops its connections: renew them before that
    **({} if IS_SQLITE else {"pool_recycle": 280, "pool_size": 5, "max_overflow": 5}),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def describe():
    """Where the app is connected, without the password (for logs and check_db.py)."""
    u = engine.url
    return "SQLite file" if IS_SQLITE else f"PostgreSQL {u.host}/{u.database} as {u.username}"


def now():
    return datetime.now(timezone.utc)


def aware(dt):
    """SQLite gives back naive datetimes; treat them as UTC."""
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def get_db():
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
