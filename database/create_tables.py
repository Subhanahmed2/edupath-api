"""
Create (or update) every Edu Path table in the database DATABASE_URL points to - e.g. a fresh Neon database.
Safe to run any time: existing tables and rows are kept.

    python -m database.create_tables
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect  # noqa: E402

from database import engine, init_db  # noqa: E402

init_db()
print("[db] all tables are ready:", ", ".join(sorted(inspect(engine).get_table_names())))
