# Plan: Phase 3 — TMF638 Service Inventory + Tech-Debt

**TL;DR —** This phase adds the TMF638 Service Inventory module (the natural downstream consumer of TMF641 orders), bundled with targeted fixes to the most impactful bugs and structural issues found in Phases 1–2. The inventory module follows the established 4-layer pattern (router → service → repository → ORM/schema) and integrates with the existing order lifecycle: when a `ServiceOrder` transitions to `completed`, the order service auto-creates a `Service` record in inventory. The phase closes with a full README roadmap update and a new plan document in `docs/plans/`.

---

## Part A — Tech-Debt Fixes (do first, they unblock clean tests later)

**Step 1 — Fix `completion_date` persistence**
File: `src/order/services/order_service.py`
Pass `completion_date` explicitly into `repo.patch()` by including it in the update dict alongside the `ServiceOrderPatch` fields, so it is actually written to the DB column instead of being set on a detached ORM instance.

**Step 2 — Fix ORM type annotations**
File: `src/order/models/orm.py`
Change all date columns (`order_date`, `completion_date`, `requested_start_date`, etc.) from `Mapped[str | None]` to `Mapped[datetime | None]` to match the `DateTime(timezone=True)` column types.

**Step 3 — Create shared `conftest.py`**
Path: `src/conftest.py`
Extract the duplicated `test_engine`, `db_session`, and `client` fixtures from `src/catalog/tests/test_catalog_api.py` and `src/order/tests/test_order_api.py` into a single shared conftest, parameterised by the app dependency and router under test.

**Step 4 — Add catalog events**
File: `src/catalog/services/catalog_service.py`
Publish `ServiceSpecificationCreateEvent` on `create_spec()` and `ServiceSpecificationStateChangeEvent` on `update_spec()` / `patch_spec()` when `lifecycle_status` changes, following the same pattern as `src/order/services/order_service.py`. Add the two new event type schemas to `src/shared/events/schemas.py`.

**Step 5 — Fix dead `StaticFiles` import**
File: `src/main.py`
Mount the `frontend/` directory (`app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")`) and add it to the Dockerfile `COPY` step so the frontend is reachable at `/ui`.

**Step 6 — Fix `ruff` dev dependency**
File: `requirements-dev.txt`
Add `ruff>=0.4` so the already-configured linter rules in `pyproject.toml` are available in dev environments.

---

## Part B — TMF638 Service Inventory Module

**Step 7 — Create module skeleton**
Path: `src/inventory/`
Mirror the existing module layout:
- `__init__.py`
- `api/__init__.py`, `api/router.py`
- `models/__init__.py`, `models/orm.py`, `models/schemas.py`
- `repositories/__init__.py`, `repositories/service_repo.py`
- `services/__init__.py`, `services/inventory_service.py`
- `tests/__init__.py`, `tests/test_inventory_api.py`, `tests/test_inventory_service.py`

**Step 8 — Define ORM**
File: `src/inventory/models/orm.py`

- `ServiceOrm` — UUID PK inheriting `Base` + `TimestampMixin`; columns: `name` (indexed, NOT NULL), `description`, `service_type`, `state` (indexed, default `"inactive"`), `start_date DateTime(tz=True)`, `end_date DateTime(tz=True)`, TMF annotation columns (`@type`, `@baseType`, `@schemaLocation`), FK `service_spec_id → service_specification.id` (RESTRICT), FK `service_order_id → service_order.id` (SET NULL on order delete), `lazy="selectin"` relationship to `ServiceCharacteristicOrm`
- `ServiceCharacteristicOrm` — `name`, `value`, `value_type`, FK → `service.id` (CASCADE)

**Step 9 — Define Pydantic schemas**
File: `src/inventory/models/schemas.py`

- `ServiceCharacteristicCreate`, `ServiceCharacteristicResponse`
- `ServiceCreate` — name required, state defaults `inactive`
- `ServicePatch` — all optional
- `ServiceResponse` — extends `BaseEntity`
- `VALID_SERVICE_STATES = {"feasibilityChecked", "designed", "reserved", "inactive", "active", "terminated"}`

**Step 10 — Implement repository**
File: `src/inventory/repositories/service_repo.py`
Async CRUD following `src/catalog/repositories/service_spec_repo.py`:
- `get_all(state_filter, offset, limit) → (list, total)`
- `get_by_id`
- `create`
- `patch`
- `delete`

**Step 11 — Implement service layer**
File: `src/inventory/services/inventory_service.py`

State machine:
```
feasibilityChecked → designed → reserved → inactive → active → terminated
```
Valid transitions (strict):
- `inactive` → `active`
- `active` → `terminated`
- Pre-active states (`feasibilityChecked`, `designed`, `reserved`) → `inactive`
- `feasibilityChecked` → `designed` → `reserved` (sequential)

Rules:
- `create_service()` — validates initial state, resolves `service_spec_id` FK via catalog repo (404 if spec not found), publishes `ServiceCreateEvent`
- `patch_service()` — validates state transition, publishes `ServiceStateChangeEvent` on state change
- `delete_service()` — only `terminated` or `inactive` may be deleted (422 otherwise); FK RESTRICT from future modules caught as 409

**Step 12 — Implement API router**
File: `src/inventory/api/router.py`
Prefix: `/tmf-api/serviceInventory/v4/service`

| Method | Path    | Status codes               |
|--------|---------|----------------------------|
| GET    | `/`     | 200 + `X-Total-Count` / `X-Result-Count` |
| POST   | `/`     | 201                        |
| GET    | `/{id}` | 200 / 404                  |
| PATCH  | `/{id}` | 200 / 404 / 422            |
| DELETE | `/{id}` | 204 / 404 / 422 / 409      |

**Step 13 — Auto-create inventory on order completion**
File: `src/order/services/order_service.py`
Inject `InventoryService` as a dependency. When `new_state == "completed"`, for each `ServiceOrderItem` with `action in ("add", "modify")`, call `inventory_service.create_service()` with:
- `name = item.service_name`
- `service_spec_id = item.service_spec_id`
- `service_order_id = order.id`
- `state = "active"`

**Step 14 — DB migration**
File: `alembic/versions/0003_inventory_initial.py`
`down_revision = "0002_order_initial"`

Create tables:
- `service` — all columns, FK RESTRICT on `service_spec_id`, FK SET NULL on `service_order_id`; indexes on `name`, `state`, `service_spec_id`, `service_order_id`
- `service_characteristic` — FK CASCADE on `service_id`

`downgrade()` drops in reverse order.

**Step 15 — Register router**
File: `src/main.py`
Import `inventory_router` and add `app.include_router(inventory_router)` alongside the existing catalog and order routers.

**Step 16 — Frontend page**
File: `frontend/inventory.html`
- Table columns: Service ID, Name, Type, State, Spec, Order, Start Date, Actions
- State filter dropdown
- State-coloured badges (`inactive`, `active`, `terminated`, etc.)
- "New Service" button with create modal
- Activate the currently-disabled "Service Inventory" card in `frontend/index.html`
- Add `InventoryClient` domain object to `frontend/js/api-client.js`

---

## Part C — Tests

**Step 17 — Unit tests**
File: `src/inventory/tests/test_inventory_service.py`
Pattern: mock repo from `src/order/tests/test_order_service.py`

Cover:
- Forced `inactive` default state
- `ServiceCreateEvent` published on create
- Valid/invalid transition matrix (parametric)
- `ServiceStateChangeEvent` published on patch with state change
- Delete guard (active → 422, terminated → 204)
- 404 on not-found

**Step 18 — Integration tests**
File: `src/inventory/tests/test_inventory_api.py`
Pattern: `sqlite+aiosqlite:///:memory:` + `httpx.AsyncClient` from `src/catalog/tests/test_catalog_api.py`

Cover:
- POST 201 with characteristics
- List + pagination headers
- State filter
- GET by ID / 404
- PATCH valid transition / invalid transition 422 / 404
- DELETE guard (active → 422, terminated → 204) / 404

---

## Part D — Documentation & README

**Step 19 — Create plan file**
File: `docs/plans/plan-serviceInventory.md`
Follow structure of `docs/plans/plan-catalogImplementation.md`. Include: TMF638 spec overview, entities and their relationships, state machine diagram, integration points with TMF633 and TMF641, and implementation checklist.

**Step 20 — Update README.md**
Add / update the "Implementation Phases" section with a full-roadmap status table:

| Phase    | Scope                                                                  | Status          |
|----------|------------------------------------------------------------------------|-----------------|
| Phase 1  | Project setup, infrastructure, shared layer, auth stub, event bus      | ✅ Done         |
| Phase 2a | TMF633 Service Catalog (ServiceSpecification CRUD + lifecycle)         | ✅ Done         |
| Phase 2b | TMF641 Service Order Management (Order lifecycle + FK to Catalog)      | ✅ Done         |
| Phase 3  | TMF638 Service Inventory + tech-debt fixes                             | 🔄 In Progress  |
| Phase 4  | TMF640 Service Activation & Configuration (Provisioning)               | 📋 Planned      |
| Phase 5  | TMF645 Service Qualification                                           | 📋 Planned      |
| Phase 6  | TMF642/628/657 Assurance (Alarms, Performance, SLA)                    | 📋 Planned      |
| Phase 7  | TMF653 Service Test Management                                         | 📋 Planned      |
| Phase 8  | TMF621/656 Trouble Ticket & Problem Management                         | 📋 Planned      |
| Phase 9  | TMF648/651 Quote & Agreement Management                                | 📋 Planned      |
| Phase 10 | Auth hardening (JWT + RBAC), CI/CD, production hardening               | 📋 Planned      |

---

## Verification Checklist

- [ ] `pytest src/ -v --asyncio-mode=auto` — all existing tests pass; all new inventory tests pass
- [ ] `POST /tmf-api/serviceOrdering/v4/serviceOrder` → PATCH to `inProgress` → `completed` → verify `GET /tmf-api/serviceInventory/v4/service` returns the auto-created `Service` record
- [ ] `GET /events` (dev mode) returns `ServiceOrderCreateEvent`, `ServiceOrderStateChangeEvent`, `ServiceCreateEvent`, `ServiceStateChangeEvent`, `ServiceSpecificationCreateEvent`
- [ ] `GET /ui/inventory.html` returns 200 after static files are mounted
- [ ] `ruff check src/` passes with zero errors
- [ ] `alembic upgrade head` runs cleanly on a fresh DB; `alembic downgrade base` reverses cleanly

---

## Decisions

- **Tech-debt bundled into Phase 3** (not a separate sprint) to keep the codebase clean before adding more surface area.
- **Inventory auto-creation uses direct service injection** (not event-driven) to keep the `completed` state change and inventory write in the same DB transaction, ensuring consistency.
- **`ServiceOrder` FK in inventory uses `SET NULL`** (not RESTRICT) so orders that are later deleted do not orphan inventory records.
- **README uses a full roadmap table** covering all 10 planned phases per the project's TMF reference documentation.
