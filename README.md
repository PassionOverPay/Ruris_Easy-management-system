# Supply Chain Management API

## Run locally

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn app.main:app --reload --app-dir backend
```

The API docs are available at `http://127.0.0.1:8000/docs`; the health check is
`http://127.0.0.1:8000/api/v1/health`.

The database defaults to a local SQLite file. The app reads `DATABASE_URL` from
the process environment, a root `.env` file, or a root `.env.local` file (the
last file takes precedence if both files define it). Neon CLI provides the
pooled production connection in `.env.local`:

```text
DATABASE_URL=postgresql://user:password@host-pooler.region.aws.neon.tech/neondb?sslmode=require
```

The SQLModel engine uses Psycopg 3 and converts standard `postgresql://` Neon
URLs to the SQLAlchemy `postgresql+psycopg://` dialect. The database probe at
`/api/v1/health/database` verifies a live connection.

## Layout

`backend/app` follows the modular layout used by the official FastAPI full-stack
template: `api` for versioned routes, `core` for configuration, `db` for session
management, and `crud`, `models`, and `schemas` for data access and domain
definitions. The purchasing, warehouse, accounting, and auth routers are
intentionally empty scaffolds; only the health check is implemented.

Authentication and department-level authorization, persisted audit logging,
delayed-order notifications, and the daily EUR/RON rate job remain to be
implemented before this API is used with operational data.
