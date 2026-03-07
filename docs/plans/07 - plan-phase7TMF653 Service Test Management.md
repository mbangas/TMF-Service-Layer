## Plan: Phase 7 — TMF653 Service Test Management

**TL;DR —** Implement the `testing` module (TMF653) covering two resources: `ServiceTestSpecification` (test templates, analogous to `ServiceSpecification` in the catalog) and `ServiceTest` (test run instances linked to active services, with nested `TestMeasure` results). The module follows the same 4-layer pattern as all prior phases (router → service → repository → ORM/schema), integrates read-only with the Service Inventory (FK to `service.id`) and optionally the Catalog (FK to `service_specification.id`), closes with a new Alembic migration, a frontend page at `frontend/testing.html`, and full test coverage. The frontend sidebar already links to `testing.html` and `main.py` already has the placeholder comment ready to uncomment.

---

### Objective

Implement the TMF653 Service Test Management module to enable creation, scheduling, execution, and result recording of service tests against active inventory services, aligned with TM Forum ODA Frameworx standards.

---

### Steps

**Phase A — Foundation (no external dependencies)**

1. **Create module skeleton** at `src/testing/` — mirror the exact layout of all prior phases:
   `__init__.py`, `api/__init__.py`, `api/router.py`, `models/__init__.py`, `models/orm.py`, `models/schemas.py`, `repositories/__init__.py`, `repositories/test_spec_repo.py`, `repositories/test_repo.py`, `services/__init__.py`, `services/testing_service.py`, `tests/__init__.py`, `tests/test_testing_api.py`, `tests/test_testing_service.py`

2. **Define ORM** in `src/testing/models/orm.py` — three tables:
   - `ServiceTestSpecificationOrm` (`service_test_specification`): UUID PK + `TimestampMixin`; fields: `name` (String 255, indexed), `description` (Text nullable), `state` (String 32, default `active`, indexed — `active | retired | obsolete`), `test_type` (String 64 nullable — e.g., `connectivity | performance | functional`), `version` (String 16 nullable), `valid_for_start` (DateTime nullable), `valid_for_end` (DateTime nullable), `service_spec_id` (FK → `service_specification.id` RESTRICT, nullable String 36, indexed)
   - `ServiceTestOrm` (`service_test`): UUID PK + `TimestampMixin`; fields: `name` (String 255, indexed), `description` (Text nullable), `state` (String 32, default `planned`, indexed — `planned | inProgress | completed | failed | cancelled`), `mode` (String 16 nullable — `automated | manual`), `start_date_time` (DateTime nullable), `end_date_time` (DateTime nullable), `service_id` (FK → `service.id` RESTRICT, String 36, indexed), `test_spec_id` (FK → `service_test_specification.id` RESTRICT, nullable String 36, indexed)
   - `TestMeasureOrm` (`test_measure`): UUID PK; fields: `service_test_id` (FK → `service_test.id` **CASCADE**, String 36, indexed), `metric_name` (String 255, indexed), `metric_value` (Float nullable), `unit_of_measure` (String 64 nullable), `result` (String 64 nullable — `pass | fail | inconclusive`), `captured_at` (DateTime nullable)

3. **Define Pydantic schemas** in `src/testing/models/schemas.py` — following `BaseEntity` + `ConfigDict(from_attributes=True, populate_by_name=True)` pattern:
   - Constants: `TEST_SPEC_TRANSITIONS = {"active": {"retired"}, "retired": {"obsolete"}, "obsolete": set()}`, `TEST_TRANSITIONS = {"planned": {"inProgress", "cancelled"}, "inProgress": {"completed", "failed", "cancelled"}, "completed": set(), "failed": set(), "cancelled": set()}`, `DELETABLE_SPEC_STATES = {"obsolete"}`, `DELETABLE_TEST_STATES = {"completed", "failed", "cancelled"}`
   - `ServiceTestSpecificationCreate`, `ServiceTestSpecificationPatch`, `ServiceTestSpecificationResponse`
   - `TestMeasureCreate`, `TestMeasureResponse`
   - `ServiceTestCreate`, `ServiceTestPatch`, `ServiceTestResponse` (includes `measures: list[TestMeasureResponse] = []` for embedded output)

**Phase B — Data and Business Layer** *(depends on A)*

4. **Implement repositories** in two files:
   - `src/testing/repositories/test_spec_repo.py` — `TestSpecificationRepository` with `get_all(offset, limit, state)`, `get_by_id`, `create`, `patch`, `delete` following the `(list, total)` pattern
   - `src/testing/repositories/test_repo.py` — `ServiceTestRepository` with `get_all(offset, limit, state, service_id, test_spec_id)`, `get_by_id`, `create`, `patch`, `delete`; plus `add_measure(service_test_id, data: TestMeasureCreate) → TestMeasureOrm` and `get_measures(service_test_id) → list[TestMeasureOrm]`

5. **Implement service layer** in `src/testing/services/testing_service.py` — two service classes co-located:
   - `TestSpecificationService`: `create_spec` (no external FK validation beyond optional catalog spec), `patch_spec` (state machine enforcement using `TEST_SPEC_TRANSITIONS`), `delete_spec` (guard: only `obsolete`), `get_spec`, `list_specs`
   - `ServiceTestService`: `create_test` (validates service exists and is `active`; validates spec exists if `test_spec_id` provided), `patch_test` (state machine enforcement; sets `start_date_time` on `→ inProgress`, `end_date_time` on `→ completed|failed|cancelled`; publishes `ServiceTestCompleteEvent` on `completed`, `ServiceTestFailedEvent` on `failed`), `delete_test` (guard: only terminal states), `get_test`, `list_tests`, `add_measure(test_id, data)` (validates test is `inProgress`), `list_measures(test_id)`

**Phase C — API Layer** *(depends on A, B)*

6. **Implement router** in `src/testing/api/router.py` — two sub-routers aggregated into one exported `router`:
   - `spec_router`: prefix `/tmf-api/serviceTest/v4/serviceTestSpecification`, tag `TMF653 - Service Test Specification` — 5 standard endpoints (GET list, POST, GET /{id}, PATCH /{id}, DELETE /{id})
   - `test_router`: prefix `/tmf-api/serviceTest/v4/serviceTest`, tag `TMF653 - Service Test Management` — 5 standard endpoints + `POST /{id}/testMeasure` (201) + `GET /{id}/testMeasure` (200)
   - Dependency factories `_get_spec_service(db)` and `_get_test_service(db)` following the `_get_alarm_service` pattern; use `ServiceRepository` and `ServiceSpecificationRepository` from existing modules

**Phase D — Integration** *(depends on A, B, C)*

7. **Register router** in `src/main.py` — replace the existing placeholder comment with `from src.testing.api.router import router as testing_router` and `app.include_router(testing_router)` (after the assurance router)

8. **Update conftest** in `src/conftest.py` — add `from src.testing.models import orm as _testing_orm  # noqa: F401 — registers ORM tables` after the assurance import line

9. **Create Alembic migration** as `alembic/versions/0007_testing_initial.py` — `down_revision = "0006_assurance_initial"`; `upgrade()` creates `service_test_specification`, `service_test`, `test_measure` in dependency order; `downgrade()` drops in reverse order

**Phase E — Tests & Frontend** *(depends on A–D)*

10. **Write tests** in `src/testing/tests/`:
    - `test_testing_api.py` (integration): CRUD for both resources, state transitions valid + invalid (422), 404 guards, active-service guard on test creation, test spec lifecycle (active→retired→obsolete), add_measure only when `inProgress`, state auto-timestamps
    - `test_testing_service.py` (unit): mocked repos, state machine paths for both entities, event assertions on completion/failure, measure guard enforcement

11. **Add frontend page** `frontend/testing.html` — dark-theme SPA consistent with `assurance.html`; tabbed interface (Test Specifications / Service Tests); CRUD modals for both tabs; state transition buttons; nested Measures panel per test row; badge styling per state

---

### Timeline

| Step | Effort |
|---|---|
| Steps 1–3 (skeleton + ORM + schemas) | Day 1 |
| Steps 4–5 (repositories + service) | Day 1–2 |
| Step 6 (router) | Day 2 |
| Steps 7–9 (integration + migration) | Day 2 |
| Step 10 (tests) | Day 3 |
| Step 11 (frontend) | Day 3 |

---

### Resources

- [TM Forum TMF653 Service Test API specification](https://www.tmforum.org/open-apis/) — canonical TMF653 v4 spec for entity shapes and state machines
- [docs/TMF-reference.md](docs/TMF-reference.md) — local SID entity mapping reference
- [src/assurance/](src/assurance/) — primary implementation template for module structure, repo pattern, service class layout, router pattern
- [src/catalog/models/orm.py](src/catalog/models/orm.py) — `ServiceSpecificationOrm` for FK reference in `ServiceTestSpecificationOrm.service_spec_id`
- [src/inventory/repositories/service_repo.py](src/inventory/repositories/service_repo.py) — `ServiceRepository.get_by_id` reused for active-service guard
- [src/catalog/repositories/service_spec_repo.py](src/catalog/repositories/service_spec_repo.py) — `ServiceSpecificationRepository.get_by_id` reused for optional spec FK validation
- [src/shared/events/bus.py](src/shared/events/bus.py) + [src/shared/events/schemas.py](src/shared/events/schemas.py) — `EventBus.publish` + `TMFEvent` / `EventPayload` for test completion events
- [src/shared/models/base_entity.py](src/shared/models/base_entity.py) — `BaseEntity` base class for all response schemas

---

### Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| `TestMeasure` CASCADE delete breaks existing test data queries | Low | Use `CASCADE` only on the `service_test_id` FK in `test_measure`; all other FKs use `RESTRICT`. Document explicitly in ORM comments. |
| `ServiceTest.state` machine has 5 states (more than prior modules) — invalid transitions easy to miss in tests | Medium | Define `TEST_TRANSITIONS` dict exhaustively in schemas.py and test every edge (planned→completed must be blocked). |
| Embedded `measures` list in `ServiceTestResponse` causes N+1 query if not handled carefully | Medium | Load measures via explicit `get_measures(test_id)` call in the service layer's `get_test` method and assemble the response manually, same pattern used for `ServiceSpecCharacteristic` in the catalog module. |
| `service_spec_id` nullable FK points to `service_specification` table — that table name must be confirmed against the catalog ORM | Low | Verify via `ServiceSpecificationOrm.__tablename__` in [src/catalog/models/orm.py](src/catalog/models/orm.py) before writing the migration (expected: `service_specification`). |
| Frontend `testing.html` complexity with two tabs + nested measures panel | Low | Reuse exact JS patterns from `assurance.html` (tab switching, modal CRUD, badge rendering); add a sub-panel per test row for measures. |

---

### Decisions

- `TestMeasure` is a child table with CASCADE delete (not a top-level entity with its own DELETE endpoint); measures are only accessible through `serviceTest/{id}/testMeasure`
- `ServiceTest` can only move to `inProgress` or `cancelled` from `planned`; direct `planned → completed` is blocked (enforces that tests must actually run)
- `ServiceTestSpecification` is optional on a `ServiceTest` (nullable FK) to allow ad-hoc tests without a formal specification template
- Module directory is `src/testing/` (not `src/service_test/`) to keep it short and consistent with the existing compact naming (`src/assurance/`, `src/catalog/`, etc.)
- `TestMeasure` records may only be added when the test is in `inProgress` state; the service layer enforces this guard with HTTP 422
