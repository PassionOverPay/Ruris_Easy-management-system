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
`DATABASE_URL` and application secrets in this ignored file. Use a direct
database connection URL for `DATABASE_URL` so both the application and Alembic
migrations use the same endpoint. Configure `CORS_ORIGINS` as a JSON array of
trusted frontend origins,
for example `["http://localhost:5173","https://your-frontend.example"]`.
Use the direct Neon connection for both application traffic and Alembic:

```text
DATABASE_URL=postgresql://user:password@host.region.aws.neon.tech/neondb?sslmode=require
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

The React/Vite client lives in `frontend/`. From that directory, run
`npm install` and `npm run dev`. Vite proxies API requests to
`http://127.0.0.1:8000` by default; set `VITE_BACKEND_URL` in
`frontend/.env.local` to use another backend origin during development. After
login, the client retrieves the authenticated identity from
`GET /api/v1/users/me` to hydrate role-aware route guards. The root npm
manifest remains dedicated to Neon CLI configuration.

## Containerized local deployment

Docker Compose runs a local PostgreSQL database, the FastAPI API, the separate
daily email worker, and the Nginx-served frontend. The default PostgreSQL
credentials in Compose are for local development only; `DATABASE_URL` from
`.env.local` takes precedence when set, and the
local database URLs are used as fallbacks. Set a strong
`JWT_SECRET_KEY` in the root `.env.local` before starting containers. SMTP
settings in the same file are optional until delayed-order email alerts are
needed. Pass `.env.local` to Compose with `--env-file`; Compose does not
automatically load files with that name.

```powershell
docker compose --env-file .env.local up --build -d
docker compose --env-file .env.local run --rm backend python -m alembic -c alembic.ini upgrade head
```

After changing `.env.local`, run `docker compose --env-file .env.local up -d` so
Compose recreates containers with the updated environment.

Open `http://localhost`. The API is also available at `http://localhost:8000`.
Nginx forwards `/api/` and `/token` to the backend and falls back to
`index.html` for React Router paths. The worker is a separate process:
`python -m app.worker`. It runs the scheduled delayed-order check at 08:00
server-local time; the API process does not start the scheduler.

For AWS, do not use the Compose PostgreSQL development password or commit
secrets. Build and publish the backend image to ECR, provide production settings
from Secrets Manager, and use a managed PostgreSQL connection (such as Neon)
instead of exposing the Compose `db` service. Run Alembic migrations as a
deployment step using a direct/unpooled database URL. Run the worker as a
separate scheduled ECS task or service, not as an additional API web worker.

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
invoices use the existing ECB EUR/RON reference-rate lookup, with Frankfurter
as fallback, for the latest published rate on or before the invoice date. The
six-decimal rate and the resulting RON amount are stored with the original
invoice currency and amount. This is an informational conversion basis, not a
determination of the correct VAT or accounting recognition rate; that depends
on the applicable transaction, tax point, receipt date, contract, and
accounting policy. RON invoices use a 1:1 rate without calling an external
service. If no historical rate can be obtained, the API returns `503` and
saves no invoice.

EUR purchase orders use the same lookup for the order date. The original
currency and PO amount remain authoritative, while the retrieved rate is stored
as `budget_exchange_rate` and used to display an estimated RON budget cost.
This estimate is not changed by later API rate changes. The nullable migration
field deliberately remains empty for existing records with unknown historical
rates; those EUR estimates are displayed as unavailable instead of being
recalculated using today's rate. Existing RON orders remain directly
comparable at 1:1.

Invoice matching compares original-currency totals and receipt quantities,
not RON conversions, so different budget and invoice reference rates alone do
not dispute a match. The reported budget variance compares the stored-rate PO
estimate with the sum of same-supplier, same-currency invoice RON conversions
saved at each invoice's own rate; it is a budget-reporting difference, not an
accounting foreign-exchange gain or loss. The current item JSON records PO
prices and ordered/received quantities but has no invoice lines. Matching
therefore cannot reliably compare invoice quantities or line prices
individually; it uses aggregate original-currency invoice and received-goods
values and exact item-name quantity totals.

Database migrations use the root `alembic.ini` and the direct Neon connection
in root `.env.local` (`DATABASE_URL`); run them from the repository root with
`python -m alembic -c alembic.ini upgrade head`. The application uses that same
connection URL for normal traffic.

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
