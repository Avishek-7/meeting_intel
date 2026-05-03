# Alembic Migration Discipline

This project now uses Alembic as the source of truth for schema evolution.

## Baseline

- Baseline revision: `f3eff45bcb2c` (`backend/alembic/versions/f3eff45bcb2c_baseline_schema.py`)
- This revision creates the full current schema (`users`, `meetings`, `usage_records`) for fresh databases.

## Daily Workflow

1. Create a migration after model changes:

```bash
cd backend
alembic revision --autogenerate -m "describe_change"
```

2. Review the generated file and adjust if needed.

3. Apply locally:

```bash
cd backend
alembic upgrade head
```

4. Validate migration state:

```bash
cd backend
alembic current
alembic heads
```

## Existing Database Adoption

If a database already has tables created outside Alembic and should be considered up to date, stamp it once:

```bash
cd backend
alembic stamp head
```

Do not use `stamp` for brand-new databases.

## Team Rules (Discipline)

1. Never change schema in production manually.
2. Every model schema change must include a migration in the same PR.
3. Keep a single migration head (`alembic heads` should return one head).
4. Prefer additive migrations for backward compatibility.
5. Never edit old committed revisions except for critical fixes agreed by the team.

## CI Baseline Checks

CI should run migrations on a clean database to ensure bootstrap works:

```bash
cd backend
alembic upgrade head
alembic current
```

Optional strict check:

```bash
cd backend
test "$(alembic heads | wc -l | tr -d ' ')" = "1"
```

## Notes

- Alembic reads `DATABASE_URL` from app settings via `backend/alembic/env.py`.
- Async URLs are converted to sync driver URLs for migration execution.
