# Adapting Farms – FastAPI Backend

Backend scaffold for the Adapting Farms agricultural decision-support platform.

## Architecture

- `app/api`: HTTP endpoints and API versioning.
- `app/core`: configuration, security, dependencies and authorization.
- `app/db`: SQLAlchemy engine, sessions and declarative base.
- `app/models`: SQLAlchemy mappings of the existing MySQL schema.
- `app/schemas`: Pydantic request/response contracts.
- `app/repositories`: database access queries.
- `app/services`: application/business orchestration.
- `app/integrations`: NASA and SoilGrids external clients.
- `app/engine`: agronomic calculations and recommendation algorithms.
- `app/tasks`: background ingestion/computation jobs.
- `database`: existing SQL baseline, diagnostics, seeds and legacy scripts.
- `alembic`: versioned schema migrations.
- `tests`: automated tests.

## Setup (Git Bash on Windows)

```bash
python -m venv venv
source venv/Scripts/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your MySQL credentials. Do not commit `.env`.

## Run the API

```bash
uvicorn app.main:app --reload
```

Open:
- http://127.0.0.1:8000/
- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/docs

## Run tests

```bash
pytest
```

## Next implementation sequence

1. Inspect and copy the real existing `init.sql` into `database/init.sql`.
2. Map existing MySQL tables in `app/models` without redesigning them.
3. Configure Alembic against the existing schema and establish a safe baseline.
4. Implement database diagnostics and integrity fixes as reviewed migrations.
5. Implement authentication and role/access policies.
6. Add farms/fields, soil, satellite indicators, crops, scenarios and recommendations APIs.

The health endpoint checks the API process only; database connectivity is not yet tested.
