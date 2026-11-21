"""
The database code now lives in the top-level database/ folder (connection, tables, migration, journeys).
This small file keeps the backend's existing `import db` / `from db import ...` lines working.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root, so `database` can be imported

from database import *  # noqa: E402,F401,F403
from database import __all__  # noqa: E402,F401
