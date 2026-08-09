# Data Model

Defined in `backend/app/models/`, versioned by Alembic (`backend/alembic/versions/`). Plain
integer primary keys and portable `sqlalchemy.JSON`/standard types are used deliberately (not
UUIDs or Postgres-only types like `JSONB`) so the schema also builds against an in-memory
SQLite engine for pytest, independent of the Docker/Postgres stack.

**Note on test coverage**: pytest builds tables via `Base.metadata.create_all()` against SQLite
directly — it does not run Alembic migrations. This means Alembic migrations are not exercised
by the automated test suite; they're verified manually via `alembic upgrade head` against the
real Postgres service.

## Tables

| Model | File | Notes |
|---|---|---|
| `Role` | `role.py` | 7 fixed roles, seeded by `app/db/seed.py` |
| `User` | `user.py` | FK → `Role` |
| `Field`, `Facility`, `Well` | `field.py` | `Field → Facility → Well` hierarchy |
| `ProductionRecord`, `PressureRecord`, `TemperatureRecord` | `production.py` | FK → `Well` |
| `Equipment`, `EquipmentReading`, `MaintenanceRecord`, `DowntimeEvent` | `equipment.py` | `Equipment` FK → `Facility`/`Well` (nullable) |
| `ProductionLoss`, `OperatingCost`, `CommodityPrice` | `economics.py` | nullable FKs to `Well`/`Equipment`/`Field`/`Facility` |
| `Alert`, `AIPrediction`, `AIRecommendation` | `ai.py` | nullable FKs to `Well`/`Equipment`; `AIRecommendation.disclaimer_text` is **non-nullable** and defaults to the AI-output guardrail language |
| `Report`, `AuditLog` | `reporting.py` | FK → `User` |

## Relationships
```
Field 1──* Facility 1──* Well 1──* {ProductionRecord, PressureRecord, TemperatureRecord}
Facility/Well 1──* Equipment 1──* {EquipmentReading, MaintenanceRecord}
Well/Equipment ──o {Alert, AIPrediction, AIRecommendation, ProductionLoss, DowntimeEvent}
User 1──* {MaintenanceRecord (technician), Report (generated_by), AuditLog}
```

## AI-output guardrail encoded in schema
`AIRecommendation.disclaimer_text` defaults to:
> "AI-generated estimate requiring engineering review; not a guaranteed conclusion."

This bakes the product's required framing into the data itself, not just UI copy — every AI
recommendation carries the disclaimer whether or not the frontend renders it explicitly.

## Migrations
```
docker compose exec backend alembic revision --autogenerate -m "<message>"
docker compose exec backend alembic upgrade head
```
