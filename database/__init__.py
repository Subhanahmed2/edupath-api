"""
Edu Path database package: connection (Neon / local PostgreSQL / SQLite), tables, start-up migration and the
per-field journey records. The backend imports everything it needs from here:

    from database import User, get_db, init_db, ...
"""
from .connection import DATA_DIR, DATABASE_URL, IS_SQLITE, SessionLocal, aware, describe, engine, get_db, now
from .migrate import init_db
from .models import Assessment, AuthSession, Base, EmailCode, Journey, User, UserState
from . import journeys

__all__ = ["DATA_DIR", "DATABASE_URL", "IS_SQLITE", "SessionLocal", "aware", "describe", "engine", "get_db", "now",
           "init_db", "Assessment", "AuthSession", "Base", "EmailCode", "Journey", "User", "UserState", "journeys"]
