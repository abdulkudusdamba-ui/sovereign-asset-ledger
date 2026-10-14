# Sovereign Asset Ledger

SAL is a FastAPI application backed by SQLAlchemy and Alembic. This repository currently provides the server-side API; it does not contain a client-side offline storage or synchronization queue.

## Fresh development environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

Set a local development database and secret in `.env`. SQLite is the default for local development:

```dotenv
DATABASE_URL=sqlite:///./sal.db
SECRET_KEY=<generate-a-local-development-secret>
ENVIRONMENT=development
```

Generate a secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not commit `.env`, real credentials, or private keys. The default SQLite database and local evidence storage are ignored by Git.

Apply the Alembic migrations, then start the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Open Swagger at <http://127.0.0.1:8000/docs> and check <http://127.0.0.1:8000/health>.
Use PostgreSQL by setting `DATABASE_URL` to a PostgreSQL SQLAlchemy URL before applying migrations or starting the application.

## Tests

With the development environment active:

```bash
pytest -q
```

The tests use temporary SQLite databases. Some existing tests generate local certificate PDFs and QR images; these are development artifacts, not migration or provenance records.

## Offline synchronization contract

`POST /offline-sync/batches` accepts authenticated `admin` and `registrar` requests containing 1–100 operations. Each operation uses a client-generated UUID as its idempotency key, references an existing SAL registry record, provides its expected asset version, and contains a bounded set of changes. The server returns an outcome for every operation; retries with the same operation ID and payload do not apply changes twice. Reuse of an operation ID with another payload is preserved as a conflict.

Non-ownership updates can be accepted immediately. Ownership changes, concurrent asset versions, and duplicate VIN or parcel identifiers are retained for authorized human review at `POST /offline-sync/conflicts/{conflict_id}/resolution`. A conflict submission is not discarded when rejected. Resolving ownership is an explicit reviewer decision, not an automated legal-ownership determination.

This is a backend synchronization contract only. There is no device-side offline database or queue in this repository. It currently has no blockchain provenance provider, so accepted sync operations and conflict resolutions are audited locally but are not cryptographically committed or blockchain-anchored.

## Recovering a fresh Codespace or Copilot session

Open the repository root and repeat the fresh-environment commands above. The database can be recreated by applying `alembic upgrade head`; keep any development data you need before deleting a local database. Start the API with `uvicorn app.main:app --reload`, then use `/docs`, `/health`, and `pytest -q` to check the environment.
