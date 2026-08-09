# Database

PostgreSQL runs as the `db` service in the root `docker-compose.yml` (image
`postgres:16-alpine`, named volume `pgdata`).

**Schema ownership**: the live schema is defined by SQLAlchemy models in
`backend/app/models/` and versioned by Alembic migrations in `backend/alembic/versions/`.
That is the single source of truth — this folder does not duplicate migration files.

This folder is reserved for:
- ERD / entity-relationship notes
- Ad hoc ops scripts (backups, one-off data fixes)
- Reference exports

See [`../docs/data-model.md`](../docs/data-model.md) for a summary of the current tables and
relationships.
