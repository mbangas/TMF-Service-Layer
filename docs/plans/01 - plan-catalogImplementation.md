# TMF Service Layer — Foundation + TMF633 Catalog MVP

## Objective

Implement the base application layer (shared infrastructure, async DB, auth stub) and the first complete domain module — **TMF633 Service Catalog Management** — including REST API, ORM, business logic, frontend UI, tests, and Docker setup.

---

## Steps

### Phase 1 — Project Structure & Configuration
1. Create `pyproject.toml` with dependencies: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `pydantic`, `pydantic-settings`, `alembic`, `python-jose`, `passlib`, `pytest`, `pytest-asyncio`, `httpx`
2. Create `src/config.py`: `Settings` class (Pydantic `BaseSettings`) loading `DATABASE_URL`, `SECRET_KEY`, `APP_ENV` from environment / `.env`
3. Create `.env.example` with all variables documented (no real values)
4. Create `docker-compose.yml` with `api` and `postgres` services; `Dockerfile` multi-stage

### Phase 2 — `shared/` Module (Foundation)
5. Create `src/shared/db/session.py`: async SQLAlchemy engine (`create_async_engine`), `AsyncSession`, `get_db` FastAPI dependency
6. Create `src/shared/db/base.py`: declarative ORM `Base` and `TimestampMixin` (`created_at`, `updated_at`)
7. Create `src/shared/models/base_entity.py`: Pydantic base schema `BaseEntity` with common SID fields (`id`, `href`, `name`, `description`, `@type`, `@baseType`, `@schemaLocation`)
8. Create `src/shared/auth/dependencies.py`: stub `get_current_user` returning a fixed user — replaceable with real JWT without touching routers
9. Create `src/shared/events/schemas.py`: generic Pydantic schemas for TMF event notifications (`eventType`, `eventTime`, `event`)

### Phase 3 — `catalog/` Module (TMF633)
10. Create `src/catalog/models/orm.py`: SQLAlchemy models `ServiceSpecificationOrm`, `ServiceSpecCharacteristicOrm`, `ServiceLevelSpecificationOrm` inheriting from `Base`
11. Create `src/catalog/models/schemas.py`: Pydantic schemas — `ServiceSpecificationCreate`, `ServiceSpecificationUpdate`, `ServiceSpecificationResponse` with TMF633 field validation
12. Create `src/catalog/repositories/service_spec_repo.py`: `ServiceSpecificationRepository` with async methods `get_all`, `get_by_id`, `create`, `update`, `patch`, `delete`
13. Create `src/catalog/services/catalog_service.py`: `CatalogService` with state machine (`active` → `obsolete` → `retired`), validations, ORM↔schema mapping
14. Create `src/catalog/api/router.py`: `APIRouter` at `/tmf-api/serviceCatalogManagement/v4/serviceSpecification` with full CRUD endpoints (`GET /`, `POST /`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`); TMF-style pagination (`offset`, `limit`, `X-Total-Count`)

### Phase 4 — Alembic Migrations
15. Initialise Alembic; configure `alembic/env.py` for async + import `Base`; generate first migration `catalog_initial`

### Phase 5 — Entry Point
16. Create `src/main.py`: `FastAPI` instance with TMF metadata; mount catalog router; lifespan handler for DB pool; CORS middleware

### Phase 6 — Frontend (Catalog)
17. Create `frontend/css/style.css`: dark theme design system with CSS variables, typography, component classes (`card`, `table`, `badge`, `button`, `form`)
18. Create `frontend/js/api-client.js`: reusable `fetch` wrapper with base URL, error handling, JSON headers
19. Create `frontend/catalog.html`: app-shell (`aside.sidebar` + `main.content`); `ServiceSpecification` table with pagination; create/edit modal; delete confirmation
20. Create `frontend/index.html`: landing page with nav to all modules (placeholder links for future modules)

### Phase 7 — Tests
21. Create `src/catalog/tests/test_catalog_api.py`: integration tests with `pytest-asyncio` + `httpx.AsyncClient`; cover full CRUD, field validation, TMF status codes (201, 404, 422)
22. Create `src/catalog/tests/test_catalog_service.py`: unit tests for `CatalogService` with mocked repository; cover state transitions and business validations

---

## Timeline

| Phase | Estimated Effort |
|---|---|
| Phase 1 — Config & Docker | 0.5 day |
| Phase 2 — Shared module | 1 day |
| Phase 3 — Catalog module | 2 days |
| Phase 4 — Migrations | 0.5 day |
| Phase 5 — Entry point | 0.5 day |
| Phase 6 — Frontend | 1.5 days |
| Phase 7 — Tests | 1 day |
| **Total** | **~7 days** |

---

## Resources

- Python 3.11+
- FastAPI, SQLAlchemy (async), asyncpg, Alembic, Pydantic v2
- PostgreSQL 15+
- Docker + docker-compose
- TMF633 Open API specification (reference: `docs/TMF-reference.md`)
- Architecture reference: `docs/app-layout.md`, `docs/Purpose.md`

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| TMF633 spec compliance gaps | Cross-reference the TMF Open API swagger spec during schema design; add spec URL to `docs/TMF-reference.md` |
| Async SQLAlchemy complexity | Use `AsyncSession` consistently; avoid mixing sync/async ORM calls |
| Frontend CORS issues in local dev | Configure CORS middleware in `main.py` to allow `localhost` origins |
| Auth stub left in production | Add env flag `AUTH_ENABLED`; CI check warns if stub is active in non-dev environments |
| DB migration drift | Run `alembic upgrade head` in Docker entrypoint; test migrations in CI pipeline |
