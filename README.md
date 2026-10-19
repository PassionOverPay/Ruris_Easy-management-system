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

The app reads local configuration from the root `.env.local`, independent of
the launch directory; process environment variables take precedence. Keep
`DATABASE_URL`, `DATABASE_URL_UNPOOLED`, and application secrets in this ignored
file. Neon CLI provides the pooled connection used by the app and direct
connection used by Alembic:

```text
DATABASE_URL=postgresql://user:password@host-pooler.region.aws.neon.tech/neondb?sslmode=require
DATABASE_URL_UNPOOLED=postgresql://user:password@host.region.aws.neon.tech/neondb?sslmode=require
```

The SQLModel engine uses Psycopg 3 and converts standard `postgresql://` Neon
URLs to the SQLAlchemy `postgresql+psycopg://` dialect. The database probe at
`/api/v1/health/database` verifies a live connection.

Authentication uses JWT bearer tokens. Set `JWT_SECRET_KEY` in `.env.local` to
at least 32 random bytes before using `/token`. Sign in with an OAuth2 form
containing `username` (the user's email) and `password`; access tokens expire
after 30 minutes by default.

There is no public sign-up. After applying database migrations, bootstrap the
first administrator by setting `FIRST_ADMIN_EMAIL` and `FIRST_ADMIN_PASSWORD`
in the process environment or root `.env.local`, then run
`python scripts/create_first_admin.py` from the repository root. The script
does nothing if an admin already exists. An authenticated admin can provision
department users with `POST /api/v1/admin/users`; the request accepts
`email`, `password`, `full_name`, and a `purchasing`, `warehouse`, or
`accounting` role. The response never includes the password.

## Layout

`backend/app` follows the modular layout used by the official FastAPI full-stack
template: `api` for versioned routes, `core` for configuration, `db` for session
management, and `crud`, `models`, and `schemas` for data access and domain
definitions. The warehouse router remains an empty scaffold.

The SQLModel tables are in `backend/app/models/models.py`. The purchasing
endpoint `GET /api/v1/purchasing/{purchase_order_id}/match` aggregates all
linked receipts and reports matched, missing, over-received, and unexpected
item quantities. Run its SQLite-backed tests from `backend` with
`python -m unittest discover -s tests -v`.

Accounting creates invoices through `POST /api/v1/accounting/invoices`. EUR
invoices use the BNR rate when its published date matches the invoice date,
then try Frankfurter for that exact historical date. If neither source provides
a valid rate for the date, the endpoint returns `503` and does not save the
invoice. RON invoices use an exchange rate of `1`.

Database migrations use the root `alembic.ini` and the direct Neon connection
in root `.env.local` (`DATABASE_URL_UNPOOLED`); run them from the repository
root with `python -m alembic -c alembic.ini upgrade head`. The application
continues to use its pooled `DATABASE_URL` for normal traffic.

The invoice create, purchase-order create, and purchase-order match endpoints
are restricted to Accounting or Purchasing as appropriate. Successful login,
invoice creation, purchase-order creation, and purchase-order matching actions
are written to `AuditLog`. Additional department routes still need their own
role guards and audit calls as they are implemented.

The app checks for overdue purchase orders each day at 08:00 in the server's
local timezone and emails all Purchasing users. Orders with `received` or
`cancelled` status, and orders expected today, are excluded. Overdue `blocked`
orders are included. Configure
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, and `SMTP_PASSWORD` in the process
environment or root `.env.local`. Port 465 uses implicit TLS; other ports use
STARTTLS.
