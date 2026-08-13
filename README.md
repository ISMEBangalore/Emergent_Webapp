# LeadPulse — Weekly CRM Report Dashboard

Turns a weekly CRM export (leads + per-program application dumps) into a Program × Lead-Stage
report, CPA metrics, and a styled Excel export. See `memory/PRD.md` for the full feature history
and business rules.

## Architecture

- **backend/** — FastAPI + MongoDB (motor). Excel parsing via pandas/openpyxl. JWT bearer-token
  auth guards every `/api/*` route except `/api/auth/login` and `/api/health`.
- **frontend/** — React + Tailwind + shadcn/radix. Talks to the backend via `REACT_APP_BACKEND_URL`.

## Local setup

### Prerequisites

- Python 3.11+
- Node 18+
- A MongoDB instance (local `mongod`, Docker, or Atlas)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in MONGO_URL, JWT_SECRET, ADMIN_USERNAME, ADMIN_PASSWORD, CORS_ORIGINS
uvicorn server:app --reload --port 8000
```

On first startup, if no users exist yet, the app creates one admin account from
`ADMIN_USERNAME`/`ADMIN_PASSWORD` in `.env`. Log in with that account, then it's safe to remove
those two lines from `.env` (they're a bootstrap step, not read again once a user exists).

Generate a fresh `JWT_SECRET` with:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Frontend

```bash
cd frontend
yarn install   # or npm install
cp .env.example .env   # set REACT_APP_BACKEND_URL to the backend above
yarn start     # or npm start
```

### Tests

```bash
cd backend
pip install -r requirements.txt
REACT_APP_BACKEND_URL=http://localhost:8000 \
TEST_ADMIN_USERNAME=admin TEST_ADMIN_PASSWORD=<your admin password> \
pytest tests/
```

The suite is E2E: it runs against a live backend (set by `REACT_APP_BACKEND_URL` or
`frontend/.env`) and logs in with `TEST_ADMIN_USERNAME`/`TEST_ADMIN_PASSWORD` (falls back to
`ADMIN_USERNAME`/`ADMIN_PASSWORD`) before exercising the API.

## Auth model

Single shared admin-style login, JWT bearer tokens (`Authorization: Bearer <token>`), no cookies —
CORS is configured with `allow_credentials=False`, so `CORS_ORIGINS` just needs the exact frontend
origin(s) that should be allowed to call the API. There's no per-user roles or self-service
registration; this fits a small internal-tool team. If more than one class of user or an audit
trail becomes necessary, that's the next thing to build here — not before.

## Deploying

This app has no dependency on any specific hosting platform — it's a standard FastAPI service plus
a static React build. Deploy the backend anywhere that can run `uvicorn`/`gunicorn` behind HTTPS
with the env vars above set, point `frontend/.env`'s `REACT_APP_BACKEND_URL` at it, and serve the
`frontend` production build (`yarn build`) from any static host or behind the same reverse proxy.
Set `CORS_ORIGINS` to the deployed frontend's real origin.
