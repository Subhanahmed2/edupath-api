# Edu Path database

Everything about storing data lives in this folder. The backend only imports it (`backend/db.py` forwards to it).

| File | What it does |
|---|---|
| `connection.py` | Connects to the database in `DATABASE_URL` (Neon cloud, local PostgreSQL, or SQLite for tests). Adds SSL for cloud servers, Neon-friendly connection pool |
| `models.py` | The 6 tables (below) |
| `migrate.py` | Creates missing tables and columns when the backend starts. Never drops or overwrites data |
| `journeys.py` | Saves and reads one **journey per field**: career answers + result, program profile + recommendation |
| `settings.py` | Reads `backend/.env` (the private settings file) |
| `create_tables.py` | `python -m database.create_tables` - set up a fresh database by hand (optional) |
| `check_db.py` | `python -m database.check_db` - which database you are connected to and how many rows each table has |
| `setup_postgres.sql`, `copy_sqlite_to_postgres.py` | Only for a local PostgreSQL server (not needed with Neon) |

## Tables
| Table | One row is |
|---|---|
| `users` | an account (email unique, password hash, verified flag, profile picture) |
| `email_codes` | a 6-digit code (only its hash), with expiry and tries |
| `auth_sessions` | a logged-in device (only a hash of the token) |
| `user_state` | one piece of the student's progress, e.g. questionnaire answers so far, field result, career answers of one field, marks, skill ratings. Shared by every PC the student logs in on |
| `assessments` | one entry of *My History* (field / career / programs / skill gap result) |
| `journeys` | **one field a student explored**: its career answers, top careers, program answers and the program recommendation. A second field is a second row, so nothing mixes |

`assessments`, `auth_sessions`, `user_state` and `journeys` belong to a user (foreign key, deleted with the account).

## Using Neon (one shared database for every PC)
1. Neon dashboard -> your project -> **Connect** -> copy the **pooled** connection string (host contains `-pooler`).
2. In `backend/.env` (copy `backend/.env.example`):  `DATABASE_URL=<that string>`  - the same line on every PC.
3. `pip install -r backend/requirements.txt`
4. `python -m database.check_db` - shows the Neon host and the row counts.
5. Start the backend as usual; tables are created automatically (`[db] using PostgreSQL ep-...-pooler...neon.tech`).

Never commit `backend/.env` - it contains the database password (it is in `.gitignore`).
