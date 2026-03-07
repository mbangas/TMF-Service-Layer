## Plan: Phase 6 — TMF642 / TMF628 / TMF657 Service Assurance

**TL;DR —** This phase adds the Service Assurance module, covering three complementary TMF APIs that together close the monitoring and SLA enforcement loop for active services. TMF642 handles reactive fault management (alarms), TMF628 handles proactive performance measurement, and TMF657 closes the loop by evaluating collected metrics against defined Service Level Objectives. The module follows the same 4-layer pattern used by all prior phases (router → service → repository → ORM/schema), integrates with the Service Inventory (read-only FK to `service.id`) and optionally the Catalog (`service_level_specification.id`), and closes with a new Alembic migration, a frontend page, and full test coverage.

---

**Steps**

1. **Create module skeleton** at `src/assurance/` — mirror the exact layout used by all prior phases: `__init__.py`, `api/__init__.py`, `api/router.py`, `models/__init__.py`, `models/orm.py`, `models/schemas.py`, `repositories/__init__.py`, `repositories/alarm_repo.py`, `repositories/measurement_repo.py`, `repositories/slo_repo.py`, `services/__init__.py`, `services/assurance_service.py`, `tests/__init__.py`, `tests/test_assurance_api.py`, `tests/test_assurance_service.py`

2. **Define ORM** in `src/assurance/models/orm.py` — three tables:
   - `AlarmOrm` (`alarm`): UUID PK, `Base` + `TimestampMixin`; columns: `name` (String, indexed), `description` (Text nullable), `state` (String — `raised | acknowledged | cleared`, default `raised`), `alarm_type` (String nullable), `severity` (String nullable — `critical | major | minor | warning | indeterminate`), `probable_cause` (String nullable), `specific_problem` (Text nullable), `service_id` (FK → `service.id` RESTRICT), `raised_at` (DateTime nullable), `acknowledged_at` (DateTime nullable), `cleared_at` (DateTime nullable)
   - `PerformanceMeasurementOrm` (`performance_measurement`): UUID PK; columns: `name` (String, indexed), `description` (Text nullable), `state` (String — `scheduled | completed | failed`, default `scheduled`), `metric_name` (String, indexed), `metric_value` (Float nullable), `unit_of_measure` (String nullable), `granularity` (String nullable), `service_id` (FK → `service.id` RESTRICT), `scheduled_at` (DateTime nullable), `completed_at` (DateTime nullable)
   - `ServiceLevelObjectiveOrm` (`service_level_objective`): UUID PK; columns: `name` (String, indexed), `description` (Text nullable), `state` (String — `active | violated | suspended`, default `active`), `metric_name` (String, indexed), `threshold_value` (Float nullable), `direction` (String — `above | below`, nullable), `tolerance` (Float nullable), `service_id` (FK → `service.id` RESTRICT), `sls_id` (FK → `service_level_specification.id` RESTRICT, nullable)

3. **Define Pydantic schemas** in `src/assurance/models/schemas.py` — following the `BaseEntity` pattern from other modules:
   - State machine constants: `ALARM_TRANSITIONS`, `MEASUREMENT_TRANSITIONS`, `SLO_TRANSITIONS`, `DELETABLE_ALARM_STATES = {"cleared"}`, `DELETABLE_MEASUREMENT_STATES = {"completed", "failed"}`, `DELETABLE_SLO_STATES = {"suspended"}`
   - `AlarmCreate`, `AlarmPatch`, `AlarmResponse`
   - `PerformanceMeasurementCreate`, `PerformanceMeasurementPatch`, `PerformanceMeasurementResponse`
   - `ServiceLevelObjectiveCreate`, `ServiceLevelObjectivePatch`, `ServiceLevelObjectiveResponse`
   - `ConfigDict(from_attributes=True, populate_by_name=True)` on all response models

4. **Implement repositories** — three files, each with `get_all`, `get_by_id`, `create`, `patch`, `delete` following the `(list, total)` pattern:
   - `src/assurance/repositories/alarm_repo.py` — `AlarmRepository`
   - `src/assurance/repositories/measurement_repo.py` — `MeasurementRepository`
   - `src/assurance/repositories/slo_repo.py` — `SLORepository` plus `get_active_by_service_and_metric(service_id, metric_name)` for violation detection

5. **Implement service layer** in `src/assurance/services/assurance_service.py` — all three service classes co-located to avoid circular imports (MeasurementService references SLOService for `check_violations`):
   - `AlarmService`: `create_alarm` (validates `service.state == "active"`), `patch_alarm` (sets `acknowledged_at` / `cleared_at` on transitions), `delete_alarm`, `get_alarm`, `list_alarms`
   - `ServiceLevelObjectiveService`: `create_slo` (validates service exists + optionally SLS exists), `patch_slo`, `delete_slo`, `get_slo`, `list_slos`, `check_violations(service_id, metric_name, value)` (evaluates `above`/`below` thresholds, flips active SLOs to `violated`, publishes event)
   - `PerformanceMeasurementService`: `create_measurement`, `patch_measurement` (after transition to `completed`, calls `slo_service.check_violations(...)`), `delete_measurement`, `get_measurement`, `list_measurements`

6. **Implement router** in `src/assurance/api/router.py` — three sub-routers aggregated into one:
   - `alarm_router`: prefix `/tmf-api/alarmManagement/v4/alarm`, tag `TMF642 - Alarm Management`
   - `measurement_router`: prefix `/tmf-api/performanceManagement/v4/performanceMeasurement`, tag `TMF628 - Performance Management`
   - `slo_router`: prefix `/tmf-api/serviceLevelManagement/v4/serviceLevel`, tag `TMF657 - Service Level Management`
   - All 5 standard endpoints per sub-router; DELETE returns `HTTP_204_NO_CONTENT` with `Response` class

7. **Add `get_sls_by_id` to catalog repo** in `src/catalog/repositories/service_spec_repo.py` — the SLO service needs a direct lookup of `ServiceLevelSpecificationOrm` by ID to validate the FK on SLO creation

8. **Register router** in `src/main.py` — add `from src.assurance.api.router import router as assurance_router` and `app.include_router(assurance_router)` after the qualification router

9. **Update conftest** in `src/conftest.py` — add `from src.assurance.models import orm as _assurance_orm` import so the in-memory SQLite test engine creates the new tables

10. **Create Alembic migration** as `alembic/versions/0006_assurance_initial.py` — `down_revision = "0005_qualification_initial"`, creates `alarm`, `performance_measurement`, `service_level_objective` tables; `downgrade()` drops in reverse order

11. **Write tests** in `src/assurance/tests/test_assurance_api.py` (integration) and `src/assurance/tests/test_assurance_service.py` (unit):
    - Integration: CRUD for all 3 entities, state transitions (valid + invalid → 422), 404 guards, active-service guard on alarm creation, auto-violation detection (above/below threshold, no-breach, failed measurement does not trigger check)
    - Unit: mocked repos, state machine valid/invalid paths, `check_violations` threshold evaluation, event publishing assertions

12. **Add frontend page** `frontend/assurance.html` — dark-theme SPA consistent with existing pages; tabbed interface (Alarms / Measurements / SLOs) with CRUD modals, state transition buttons, badge styling per state and severity

---

**Verification**
- Run `pytest src/assurance/tests/ -v` — all tests green
- Run `pytest --tb=short` — full suite still green (no regressions)
- Start the app and browse `/ui/assurance.html`
- Hit POST endpoints via `/docs` Swagger UI
- Check `/events` endpoint shows alarm, measurement, and SLO violation events

**Decisions**
- All three service classes are co-located in `assurance_service.py` to prevent a circular import between `PerformanceMeasurementService` (which needs `SLOService`) and `SLOService` (which has no dependency on measurements)
- `check_violations` is the only mechanism that transitions a SLO to `violated`; the PATCH endpoint does not allow that transition directly (enforced by `SLO_TRANSITIONS`)
- `AlarmOrm.service_id` FK uses `RESTRICT` (not CASCADE) to prevent accidental orphan-cleanup; alarms must be explicitly deleted before a service can be removed
- `sls_id` FK on SLO is nullable to allow SLOs not tied to a specific catalog SLS definition
- SLO `direction` field allows `above` (alert when value exceeds threshold) and `below` (alert when value drops below threshold), covering both over-utilisation and under-delivery scenarios
