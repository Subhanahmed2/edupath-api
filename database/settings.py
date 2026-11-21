"""
Loads the private settings file before the database connects. The database link lives in backend/.env
(DATABASE_URL=...), the same file the backend reads, so every PC needs only that one file.
Values already set in the environment win (the tests use their own temporary database this way).
No extra package needed. Template: backend/.env.example. Never commit backend/.env - it holds passwords.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILES = [ROOT / "backend" / ".env", ROOT / ".env"]


def load_env():
    for path in ENV_FILES:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
