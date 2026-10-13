# sovereign-asset-ledger
SAL

## Development and Codespaces

```bash
pip install -r requirements-dev.txt
alembic upgrade head   # only against a new/disposable database
pytest
```

Importing `app.main` no longer creates tables; use Alembic for schema setup.
Tests use temporary SQLite, evidence, and generated QR/certificate paths and
an in-memory Celery broker (`REDIS_URL=memory://`), so no Redis or existing
database is required.
