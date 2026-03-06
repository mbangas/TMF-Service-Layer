# Plan: Phase 4 — TMF640 Service Activation & Configuration (Provisioning)

**TL;DR —** This phase adds the TMF640 Service Activation & Configuration module, the provisioning engine of the Service Layer. It introduces `ServiceActivationJob` (a job-oriented activation/configuration workflow) and `ServiceConfigurationParam` (arbitrary key/value configuration applied to a Service). The module integrates directly with TMF638 inventory: when a job of type `provision` or `activate` succeeds, the target `Service` transitions to `active`; when a job of type `deactivate` or `terminate` succeeds, the Service transitions accordingly. The phase is bundled with targeted tech-debt fixes from Phase 3 and closes with a README update.

---

## Objective

Implement the **TMF640 Service Activation & Configuration** provisioning domain so that:

1. Any `Service` in inventory (state `inactive` or `active`) can have an activation/configuration job raised against it.
2. Jobs execute a strict lifecycle (`accepted → running → succeeded | failed | cancelled`), driving the Service state machine in TMF638.
3. Configuration parameters can be attached to a job and persisted against the Service on success.
4. The module follows the established 4-layer pattern (router → service → repository → ORM/schema) and is consistently event-driven.

---

## Part A — Tech-Debt Fixes from Phase 3 (do first)

**Step 1 — Verify Phase 3 conftest consolidation**
File: `src/conftest.py`
Confirm the shared `test_engine`, `db_session`, and `client` fixtures are present and referenced by all three existing test modules. If `src/inventory/tests/test_inventory_api.py` still carries its own duplicated fixtures, remove and replace with references to `src/conftest.py`.

**Step 2 — Verify event publishing in inventory service**
File: `src/inventory/services/inventory_service.py`
Confirm `ServiceCreateEvent` is published on `create_service()` and `ServiceStateChangeEvent` on `patch_service()` when state changes, matching the pattern in `src/order/services/order_service.py`. Add missing calls if absent.

**Step 3 — Verify static files mount**
File: `src/main.py`
Confirm `app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")` is present. Also verify the `Dockerfile` has a `COPY frontend/ frontend/` step.

**Step 4 — Align inventory ORM date types**
File: `src/inventory/models/orm.py`
Confirm `start_date` and `end_date` columns use `Mapped[datetime | None]` with `DateTime(timezone=True)`, not `Mapped[str | None]`. Fix if needed.

---

## Part B — TMF640 Service Activation & Configuration Module

### Entities

| SID Entity | Description |
|---|---|
| `ServiceActivationJob` | Job that drives activation/configuration of a Service instance |
| `ServiceConfigurationParam` | Key/value parameter applied to a Service through a job |

### Job Type → Service State Effect

| Job Type | Precondition (Service state) | Post-success (Service state) |
|---|---|---|
| `provision` | `inactive` | `active` |
| `activate` | `inactive` | `active` |
| `modify` | `active` | `active` (params updated) |
| `deactivate` | `active` | `inactive` |
| `terminate` | `active` or `inactive` | `terminated` |

### Job State Machine

```
accepted → running → succeeded
                  ↘ failed
         ↘ cancelled   (only from accepted or running)
```

---

**Step 5 — Create module skeleton**
Path: `src/provisioning/`
Mirror the established module layout:
```
src/provisioning/
├── __init__.py
├── api/
│   ├── __init__.py
│   └── router.py
├── models/
│   ├── __init__.py
│   ├── orm.py
│   └── schemas.py
├── repositories/
│   ├── __init__.py
│   └── activation_job_repo.py
├── services/
│   ├── __init__.py
│   └── provisioning_service.py
└── tests/
    ├── __init__.py
    ├── test_provisioning_api.py
    └── test_provisioning_service.py
```

---

**Step 6 — Define ORM**
File: `src/provisioning/models/orm.py`

- `ServiceActivationJobOrm` — UUID PK inheriting `Base` + `TimestampMixin`; columns:
  - `name` (`String`, NOT NULL, indexed)
  - `description` (`Text`, nullable)
  - `job_type` (`String`, NOT NULL) — `provision | activate | modify | deactivate | terminate`
  - `state` (`String`, NOT NULL, indexed, default `"accepted"`)
  - `mode` (`String`, nullable) — `immediate | deferred`
  - `start_mode` (`String`, nullable) — `automatic | manual`
  - `scheduled_start_date` (`DateTime(timezone=True)`, nullable)
  - `scheduled_completion_date` (`DateTime(timezone=True)`, nullable)
  - `actual_start_date` (`DateTime(timezone=True)`, nullable)
  - `actual_completion_date` (`DateTime(timezone=True)`, nullable)
  - `error_message` (`Text`, nullable) — populated on `failed`
  - `@type`, `@baseType`, `@schemaLocation` annotation columns
  - FK `service_id → service.id` (`RESTRICT` on delete) — indexed
  - `lazy="selectin"` relationship to `ServiceConfigurationParamOrm`

- `ServiceConfigurationParamOrm` — UUID PK; columns:
  - `name` (`String`, NOT NULL)
  - `value` (`Text`, nullable)
  - `value_type` (`String`, nullable)
  - FK `job_id → service_activation_job.id` (`CASCADE` on delete) — indexed

---

**Step 7 — Define Pydantic schemas**
File: `src/provisioning/models/schemas.py`

```python
VALID_JOB_TYPES = {"provision", "activate", "modify", "deactivate", "terminate"}
VALID_JOB_STATES = {"accepted", "running", "succeeded", "failed", "cancelled"}

# Valid state transitions
JOB_TRANSITIONS = {
    "accepted": {"running", "cancelled"},
    "running":  {"succeeded", "failed", "cancelled"},
    # terminal states — no further transitions
}
```

- `ServiceConfigurationParamCreate` — `name` required, `value`, `value_type` optional
- `ServiceConfigurationParamResponse` — extends `ServiceConfigurationParamCreate` + `id`
- `ServiceActivationJobCreate` — `name` required, `job_type` required, `service_id` (UUID) required; optional: `description`, `mode`, `start_mode`, `scheduled_start_date`, `params: list[ServiceConfigurationParamCreate]`
- `ServiceActivationJobPatch` — all fields optional; `state` triggers transition validation
- `ServiceActivationJobResponse` — extends `BaseEntity`; includes `params: list[ServiceConfigurationParamResponse]`

---

**Step 8 — Implement repository**
File: `src/provisioning/repositories/activation_job_repo.py`
Async CRUD following `src/inventory/repositories/service_repo.py`:

- `get_all(state_filter, job_type_filter, service_id_filter, offset, limit) → (list, total)`
- `get_by_id(job_id) → ServiceActivationJobOrm | None`
- `create(data: ServiceActivationJobCreate) → ServiceActivationJobOrm`
- `patch(job_id, update_dict) → ServiceActivationJobOrm | None`
- `delete(job_id) → bool`

---

**Step 9 — Implement service layer**
File: `src/provisioning/services/provisioning_service.py`

Rules:

- `create_job()`:
  - Validates `job_type` is in `VALID_JOB_TYPES`
  - Resolves `service_id` FK via inventory repo (404 if not found)
  - Validates the Service's current state is compatible with the requested `job_type` (e.g., cannot `activate` a `terminated` service) — 422 if incompatible
  - Sets initial job state to `"accepted"`
  - Publishes `ServiceActivationJobCreateEvent`

- `patch_job()`:
  - Validates the requested state transition against `JOB_TRANSITIONS` (422 on invalid)
  - **On transition to `succeeded`:** calls `inventory_service.patch_service()` to apply the correct new Service state based on `job_type` (see mapping table in Part B)
  - **On transition to `succeeded` with params:** persists `ServiceConfigurationParam` entries against the Service
  - **On transition to `failed`:** records `error_message`
  - Publishes `ServiceActivationJobStateChangeEvent` on any state change

- `delete_job()`:
  - Only `failed` or `cancelled` jobs may be deleted (422 otherwise)
  - Returns 409 if FK RESTRICT prevents deletion (future dependency)

---

**Step 10 — Implement API router**
File: `src/provisioning/api/router.py`
Prefix: `/tmf-api/serviceActivationConfiguration/v4/serviceActivationJob`

| Method | Path    | Status codes                  |
|--------|---------|-------------------------------|
| GET    | `/`     | 200 + `X-Total-Count` / `X-Result-Count` |
| POST   | `/`     | 201                           |
| GET    | `/{id}` | 200 / 404                     |
| PATCH  | `/{id}` | 200 / 404 / 422               |
| DELETE | `/{id}` | 204 / 404 / 422 / 409         |

Query parameters for `GET /`:
- `state` — filter by job state
- `job_type` — filter by job type
- `service_id` — filter by target service
- `offset`, `limit` — pagination

---

**Step 11 — Add event schemas**
File: `src/shared/events/schemas.py`
Add:
- `ServiceActivationJobCreateEvent` — `event_type = "ServiceActivationJobCreateEvent"`, payload `ServiceActivationJobResponse`
- `ServiceActivationJobStateChangeEvent` — `event_type = "ServiceActivationJobStateChangeEvent"`, payload includes `job_id`, `old_state`, `new_state`, `service_id`

---

**Step 12 — Wire inventory integration**
File: `src/provisioning/services/provisioning_service.py`
Inject `InventoryService` (from `src/inventory/services/inventory_service.py`) as a constructor dependency (not via FastAPI DI directly — inject at the service layer to keep it testable). On job `succeeded`:

```python
SERVICE_STATE_ON_SUCCESS = {
    "provision":  "active",
    "activate":   "active",
    "modify":     "active",       # re-confirms active, params updated
    "deactivate": "inactive",
    "terminate":  "terminated",
}
await inventory_service.patch_service(
    service_id=job.service_id,
    patch=ServicePatch(state=SERVICE_STATE_ON_SUCCESS[job.job_type]),
)
```

---

**Step 13 — DB migration**
File: `alembic/versions/0004_provisioning_initial.py`
`down_revision = "0003_inventory_initial"`

Create tables:
- `service_activation_job` — all columns; FK RESTRICT on `service_id`; indexes on `name`, `state`, `job_type`, `service_id`
- `service_configuration_param` — FK CASCADE on `job_id`; index on `job_id`

`downgrade()` drops `service_configuration_param` then `service_activation_job`.

---

**Step 14 — Register router**
File: `src/main.py`
Import `provisioning_router` from `src/provisioning/api/router.py` and add `app.include_router(provisioning_router)` alongside the existing routers.

---

**Step 15 — Frontend page**
File: `frontend/provisioning.html`

- Table columns: Job ID, Name, Type, State, Target Service, Scheduled Start, Actual Completion, Error, Actions
- Filter dropdowns: State, Job Type
- State-coloured badges (`accepted`, `running`, `succeeded`, `failed`, `cancelled`)
- "New Job" button with create modal (service selector, job type, params key/value list)
- Job detail panel: shows `ServiceConfigurationParam` list
- Activate the currently-disabled "Service Activation" card on `frontend/index.html`
- Add `ProvisioningClient` domain object to `frontend/js/api-client.js`

---

## Part C — Tests

**Step 16 — Unit tests**
File: `src/provisioning/tests/test_provisioning_service.py`
Pattern: mock repo + mock inventory_service, following `src/inventory/tests/test_inventory_service.py`.

Cover:
- `create_job()` — valid job type + compatible service state → 201
- `create_job()` — invalid job type → 422
- `create_job()` — service not found → 404
- `create_job()` — service state incompatible with job type → 422
- `patch_job()` — valid transitions: `accepted→running`, `running→succeeded`, `running→failed`, `accepted→cancelled`, `running→cancelled`
- `patch_job()` — invalid transition (e.g., `succeeded→running`) → 422
- `patch_job()` — on `succeeded`, inventory `patch_service()` called with correct new state (parametric over all 5 job types)
- `patch_job()` — `ServiceActivationJobStateChangeEvent` published
- `delete_job()` — `failed` → 204; `cancelled` → 204; `succeeded` → 422
- Not-found guards on all mutating operations

**Step 17 — Integration tests**
File: `src/provisioning/tests/test_provisioning_api.py`
Pattern: `sqlite+aiosqlite:///:memory:` + `httpx.AsyncClient` from `src/conftest.py`.

Cover:
- `POST /serviceActivationJob` — 201 with params
- `GET /serviceActivationJob` — list with pagination headers
- `GET /serviceActivationJob` — state filter, job_type filter
- `GET /serviceActivationJob/{id}` — 200 / 404
- `PATCH /serviceActivationJob/{id}` — valid transition → 200; invalid transition → 422; 404
- `PATCH /serviceActivationJob/{id}` — `accepted→running→succeeded` for `provision` job type → verify inventory service state set to `active`
- `DELETE /serviceActivationJob/{id}` — guard (succeeded → 422, failed → 204) / 404

---

## Part D — Documentation & README

**Step 18 — Update README.md**
Update the Phase 3 row from `🔄 In Progress` to `✅ Done` and Phase 4 row from `📋 Planned` to `🔄 In Progress`. Add a "Service Activation & Configuration (TMF640)" module section under "Implemented Modules" with:
- Responsibilities
- Key SID Entities table
- API Endpoints table
- Module location

**Step 19 — Update app-layout.md**
Mark `src/provisioning/` and `frontend/provisioning.html` as `✅` in the file tree.

---

## Verification Checklist

- [ ] `pytest src/ -v --asyncio-mode=auto` — all existing tests pass; all new provisioning tests pass
- [ ] Full E2E flow: `POST /serviceSpecification` → `POST /serviceOrder` → PATCH to `completed` → verify `GET /tmf-api/serviceInventory/v4/service` returns `active` Service → `POST /serviceActivationJob` (`deactivate`) → PATCH to `running` → PATCH to `succeeded` → verify Service is now `inactive`
- [ ] `GET /events` (dev mode) contains `ServiceActivationJobCreateEvent` and `ServiceActivationJobStateChangeEvent`
- [ ] `GET /ui/provisioning.html` returns 200
- [ ] `ruff check src/` passes with zero errors
- [ ] `alembic upgrade head` runs cleanly; `alembic downgrade base` reverses cleanly

---

## Timeline (Estimate)

| Step(s) | Activity | Effort |
|---|---|---|
| 1–4 | Phase 3 tech-debt verification and fixes | 1 session |
| 5–7 | Module skeleton, ORM, schemas | 1 session |
| 8–10 | Repository, service layer, API router | 1 session |
| 11–14 | Events, inventory integration, migration, router registration | 1 session |
| 15 | Frontend page | 1 session |
| 16–17 | Unit + integration tests | 1 session |
| 18–19 | README + app-layout updates | 0.5 session |

---

## Resources

- [TMF640 Service Activation & Configuration API Specification](https://www.tmforum.org/resources/standard/tmf640-service-activation-and-configuration-api-rest-specification-r19-0-1/)
- [TM Forum SID — Service domain](docs/TMF-reference.md)
- Phase 3 implementation: `src/inventory/` (pattern reference for ORM, schemas, repo, service, tests)
- Shared event bus: `src/shared/events/bus.py`
- Alembic migration pattern: `alembic/versions/0003_inventory_initial.py`

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Circular dependency: `provisioning_service` ↔ `inventory_service` | Medium | High | Inject `InventoryService` at construction time (not via FastAPI DI at the router level); use an abstract interface if needed |
| Inventory state gets out of sync if DB write partially fails | Medium | High | Wrap the job state update + inventory state update in a single DB transaction using `async with session.begin()` |
| Phase 3 tests still failing when Phase 4 starts | Medium | Medium | Treat Part A tech-debt fixes as blocking — do not merge any Part B code until all Phase 3 tests pass |
| TMF640 spec has more sub-resources than planned (e.g., `ServiceOrder` ref, `ServiceRelationship`) | Low | Low | Implement core job + param entities first; extend in Phase 4b patch if needed |
| `alembic downgrade` ordering breaks with multiple modules | Low | Medium | Always set `down_revision` explicitly and test `downgrade base` before merging |

---

## Decisions

- **Job-driven model (not direct activation call)** — TMF640 is inherently async/job-oriented. A job entity provides auditability and allows deferred scheduling; direct "activate now" calls can be achieved by immediately transitioning `accepted → running → succeeded`.
- **No background task runner in this phase** — Jobs are transitioned by explicit PATCH calls (simulating an orchestrator). A real async worker (Celery/asyncio task) is deferred to Phase 10 (infrastructure hardening).
- **`ServiceConfigurationParam` scoped to job, not Service** — Configuration history is preserved per job. On job success, params are also written to the Service's `characteristics` via the inventory service, keeping the inventory record authoritative.
- **FK RESTRICT on `service_id`** — A Service with pending/running jobs cannot be deleted from inventory, enforcing referential integrity without cascade deletes.
