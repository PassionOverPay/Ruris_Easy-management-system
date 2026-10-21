# Supply Chain Management

Internal purchasing, warehouse, and accounting workflow application. The
frontend is a React/Vite single-page app; the API is FastAPI with SQLModel and
Alembic; Nginx serves the frontend and proxies API requests to the backend.

## Features

- JWT sign-in and role-aware access for Purchasing, Warehouse, and Accounting.
- Purchase orders, partial goods receipts, supplier invoices, and order/invoice/
  receipt matching.
- History page and audit log for recorded actions, including who performed
  supported actions and when.
- PDF downloads for purchase orders, goods receipts, and invoices.
- EUR to RON reference rates for invoices and purchase-order budget estimates.
- Email alerts for overdue orders, receipt discrepancies, and disputed invoices
  to the affected departments when SMTP is configured.

## Requirements

- Python 3.11 or later for running the backend outside Docker.
- Node.js 20 or later for the frontend.
- Docker Compose for the containerized deployment.
- PostgreSQL for a persistent shared deployment. SQLite is used by some tests.

## Local development

### Configure the backend

Create a root `.env.local` file. Backend settings load this file, with process
environment variables taking precedence. Keep credentials and secrets out of
Git. Use a direct Neon database URL for `DATABASE_URL`; the same URL is used by
the application and Alembic migrations.

```text
DATABASE_URL=postgresql://user:password@host.region.aws.neon.tech/neondb?sslmode=require
JWT_SECRET_KEY=replace-with-at-least-32-random-bytes
FIRST_ADMIN_EMAIL=admin@example.com
FIRST_ADMIN_PASSWORD=replace-with-a-strong-password
CORS_ORIGINS=["http://localhost:5173"]
SMTP_HOST=
SMTP_PORT=
SMTP_USER=
SMTP_PASSWORD=
```

The API falls back to SQLite when `DATABASE_URL` is unset, but Alembic requires
`DATABASE_URL` and rejects a Neon pooled hostname. `CORS_ORIGINS` is a JSON
array of trusted browser origins. SMTP settings are optional until email alerts
are needed. Port 465 uses implicit TLS; other SMTP ports use STARTTLS.

Create and activate a virtual environment, install dependencies, and apply the
database migrations from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python -m alembic -c alembic.ini upgrade head
```

Create the first administrator (the script does nothing if one already
exists), then start the API:

```powershell
python scripts/create_first_admin.py
uvicorn app.main:app --reload --app-dir backend
```

The API docs are at `http://127.0.0.1:8000/docs`. Health endpoints are
`/api/v1/health` and `/api/v1/health/database`.

### Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

The Vite dev server runs at `http://localhost:5173` and proxies `/api` and
`/token` to `http://127.0.0.1:8000`. Set `VITE_BACKEND_URL` in
`frontend/.env.local` to change that development proxy target. The client uses
relative API paths by default; `VITE_API_BASE_URL` is only needed when the API
is served from a different base URL. The root npm manifest is for Neon CLI
configuration, not the frontend.

There is no public sign-up. After migrations, bootstrap the first administrator
as described above. An authenticated administrator can create department users
through `POST /api/v1/admin/users`, with an email, password, full name, and one
or more department roles.

## Docker Compose

Compose starts PostgreSQL, the FastAPI backend, a separate email worker, and
the Nginx frontend. The default PostgreSQL credentials are for local
development only. Compose does not automatically read `.env.local`, so pass it
explicitly:

```powershell
docker compose --env-file .env.local up --build -d
docker compose --env-file .env.local run --rm backend python -m alembic -c alembic.ini upgrade head
```

Run `python scripts/create_first_admin.py` from the repository root on the host
after migrations, with the local virtual environment active. The backend image
does not include the `scripts/` directory.

Open `http://localhost`. Nginx serves the frontend, proxies `/api/` and
`/token` to the backend, and falls back to `index.html` for React Router paths.
The API is also exposed on `http://localhost:8000` for local development.

The worker runs the delayed-order check daily at 08:00 in server-local time;
the API process does not run the scheduler. Configure `SMTP_HOST`,
`SMTP_PORT`, `SMTP_USER`, and `SMTP_PASSWORD` in `.env.local` to enable email.
After changing environment values, recreate the affected services with
`docker compose --env-file .env.local up -d` (use `--build` when changing
frontend build arguments or application images).

Compose currently sets `CORS_ORIGINS` to localhost values instead of reading
that key from `.env.local`. This is sufficient for the same-origin Nginx and
CloudFront setup below. A separately hosted frontend needs an appropriate
backend CORS configuration.

## EC2 origin behind CloudFront

The current hosting arrangement can use the EC2 Nginx frontend as the
CloudFront custom origin. The container listens on HTTP port 80. Keep
`VITE_API_BASE_URL` empty so the browser requests `/api/...` and `/token` on the
CloudFront hostname; Nginx then proxies those paths to the backend. No CORS
allow-list entry is needed for this same-origin arrangement.

In CloudFront, route the default behavior and the `/api/*` and `/token`
requests to the EC2 origin. Allow the methods the API uses, forward the
`Authorization` header and required query strings, and disable caching for API
and token responses. Use short or no caching for `index.html` and longer
caching for versioned static assets. The Nginx SPA fallback handles direct
visits to frontend routes. Keep the origin protocol set to HTTP unless TLS is
configured on EC2; Nginx in the provided Compose setup listens on port 80.
CloudFront configuration is managed outside this repository.

## Alternative AWS deployment

For an ECS deployment, publish the backend image to ECR, provide production
settings through Secrets Manager, and use a managed PostgreSQL database rather
than exposing the Compose `db` service. Run Alembic migrations as a deployment
step using the direct `DATABASE_URL`. Run the email worker as a separate
scheduled task or service, not as an additional API web worker.

## Data and workflow notes

EUR invoice amounts are converted using the ECB EUR/RON reference rate for the
invoice date, with Frankfurter as a fallback. The rate and resulting RON amount
are saved with the invoice; if no historical rate is available, invoice
creation returns `503`. RON invoices use a 1:1 rate. EUR purchase orders store
their rate-based RON budget estimate; existing records without a saved rate
show the estimate as unavailable rather than using today's rate.

Invoice matching compares original-currency totals and receipt quantities.
Current order items do not include invoice lines, so matching cannot compare
invoice quantities or prices item by item. Budget variance is a reporting
comparison and is not an accounting foreign-exchange gain or loss.

Audit logging currently covers successful logins, user management, invoice
creation, purchase-order creation, and purchase-order matching. Additional
actions need their own audit calls as they are implemented.

## Tests

Run the SQLite-backed backend tests from the `backend` directory:

```powershell
python -m unittest discover -s tests -v
```

## Project layout

- `backend/app/api/routes/` — API route modules for authentication, users,
  purchasing, warehouse, accounting, history, and health checks.
- `backend/app/models/` and `backend/app/schemas/` — database models and API
  schemas.
- `backend/app/services/` — matching, currency, email, PDF, audit, and
  notification services.
- `alembic/` — database migrations, configured through the root `alembic.ini`.
- `frontend/src/` — React application, pages, components, and API client.
