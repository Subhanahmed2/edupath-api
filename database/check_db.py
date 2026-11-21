"""
Read-only database check: which database DATABASE_URL (backend/.env) points to, whether it answers, and how many
rows each Edu Path table has. Nothing is written. The password is never printed.

    python -m database.check_db          (from the project folder)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import database as DB  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402

print(f"Database: {DB.describe()}")
t0 = time.time()
try:
    with DB.engine.connect() as con:
        version = con.execute(text("select version()")).scalar() if not DB.IS_SQLITE else "SQLite"
        print(f"Connected in {time.time() - t0:.1f} s - {version.split(',')[0]}")
        tables = inspect(DB.engine).get_table_names()
        for name in [t.name for t in DB.Base.metadata.sorted_tables]:
            if name in tables:
                n = con.execute(text(f'select count(*) from "{name}"')).scalar()
                print(f"  {name:15s} {n} rows")
            else:
                print(f"  {name:15s} MISSING (start the backend once, or run: python -m database.create_tables)")
        if "users" in tables:
            print(f"Verified accounts: {con.execute(text('select count(*) from users where email_verified')).scalar()}")
except Exception as e:  # noqa: BLE001 - show the reason in plain words
    print(f"Could not connect: {type(e).__name__}: {str(e).splitlines()[0]}")
    sys.exit(1)
