"""
Loads backend/.env (if present) into the environment before the other modules read their settings.
Values already set in the environment win, so the tests and one-off `$env:X = ...` overrides still work.
No extra package needed. Template: backend/.env.example  (backend/.env is git-ignored - it holds passwords).
"""
import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent / ".env"


def load_env(path=ENV_FILE):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
