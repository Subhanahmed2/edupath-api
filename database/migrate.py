"""
Creates every table on startup (new tables such as `journeys` appear automatically, also on Neon) and adds
columns that databases made by older versions are missing. Nothing is ever dropped or overwritten.

    python -m database.create_tables   (optional: the backend runs this by itself when it starts)
"""
from sqlalchemy import inspect, text

from .connection import describe, engine
from .models import Base


def init_db():
    print(f"[db] using {describe()}", flush=True)
    Base.metadata.create_all(engine)
    # databases made before email verification / profile pictures existed (existing accounts start unverified)
    have = {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.begin() as con:
        if "email_verified" not in have:
            con.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT false"))
        if "verified_at" not in have:
            con.execute(text(f"ALTER TABLE users ADD COLUMN verified_at "
                             f"{'TIMESTAMP WITH TIME ZONE' if engine.dialect.name == 'postgresql' else 'DATETIME'}"))
        if "avatar" not in have:
            con.execute(text("ALTER TABLE users ADD COLUMN avatar TEXT"))
        # journeys made before per-field shortlists existed
        if "shortlist" not in {c["name"] for c in inspect(engine).get_columns("journeys")}:
            con.execute(text("ALTER TABLE journeys ADD COLUMN shortlist JSON"))

