## Plan: Phase 5 — TMF645 Service Qualification Management

**TL;DR —** This phase adds the TMF645 Service Qualification module, the pre-sales feasibility check that sits between Service Design (TMF633) and Service Order (TMF641) in the TMF lifecycle. It introduces `ServiceQualification` (a request to check if a service can be delivered) and `ServiceQualificationItem` (per-service-spec check result). The module follows the same 4-layer pattern as all previous phases (router → service → repository → ORM/schema), integrates read-only with the catalog (`ServiceSpecification`), and closes with a new Alembic migration, frontend page, and full test coverage.

---

**Steps**

1. **Create module skeleton** at `src/qualification/` — mirror the exact layout used by all prior phases: `__init__.py`, `api/router.py`, `models/orm.py`, `models/schemas.py`, `repositories/qualification_repo.py`, `services/qualification_service.py`, `tests/test_qualification_api.py`, `tests/test_qualification_service.py`

2. **Define ORM** in `src/qualification/models/orm.py` — two tables:
   - `ServiceQualificationOrm`: UUID PK, `Base` + `TimestampMixin`; columns: `name` (String, indexed), `description` (Text nullable), `state` (String — `acknowledged | inProgress | accepted | rejected | cancelled`), `expected_qualification_date` (`DateTime(timezone=True)`, nullable), `expiration_date` (`DateTime(timezone=True)`, nullable), `@type` aliased field
   - `ServiceQualificationItemOrm`: UUID PK; FK `qualification_id → service_qualification.id` (cascade delete); `service_spec_id` (FK → `service_specification.id`, nullable), `state` (`approved | rejected | unableToProvide`), `qualifier_message` (Text nullable), `termination_error` (Text nullable)

3. **Define Pydantic schemas** in `src/qualification/models/schemas.py` — following the `BaseEntity` pattern from other modules:
   - `ServiceQualificationItemCreate`, `ServiceQualificationItemResponse`
   - `ServiceQualificationCreate` (includes nested list of items), `ServiceQualificationPatch`, `ServiceQualificationResponse`
   - `ConfigDict(from_attributes=True, populate_by_name=True)` on all response models

4. **Implement repository** in `src/qualification/repositories/qualification_repo.py` — async CRUD with `(list, total)` return for paginated list, same pattern as `src/provisioning/repositories/activation_job_repo.py`

5. **Implement service layer** in `src/qualification/services/qualification_service.py`:
   - `QUALIFICATION_TRANSITIONS` dict enforcing valid state machine transitions
   - `create_qualification()` — validates referenced `service_spec_id` exists (read from catalog repo), creates parent + items, sets initial state to `acknowledged`, publishes `ServiceQualificationCreateEvent`
   - `get_qualification()` / `list_qualifications()` — delegate to repo
   - `patch_qualification()` — validates state transition, updates, publishes `ServiceQualificationStateChangeEvent` on state change
   - `delete_qualification()` — only allowed from terminal or `acknowledged` states

6. **Implement router** in `src/qualification/api/router.py` — 5 standard TMF endpoints:
   - `GET /tmf-api/serviceQualificationManagement/v4/checkServiceQualification` (paginated, `offset`/`limit`, `X-Total-Count`/`X-Result-Count` headers)
   - `POST /tmf-api/serviceQualificationManagement/v4/checkServiceQualification`
   - `GET /tmf-api/serviceQualificationManagement/v4/checkServiceQualification/{id}`
   - `PATCH /tmf-api/serviceQualificationManagement/v4/checkServiceQualification/{id}`
   - `DELETE /tmf-api/serviceQualificationManagement/v4/checkServiceQualification/{id}`
   - `Depends(get_current_user)` on all endpoints

7. **Add event types** in `src/shared/events/schemas.py` — add `ServiceQualificationCreateEvent` and `ServiceQualificationStateChangeEvent` to the existing `TMFEvent` union/discriminated type

8. **Register router** in `src/main.py` — uncomment and activate the `qualification_router` placeholder already present on lines 71–73

9. **Update conftest** in `src/conftest.py` — add `from src.qualification.models import orm as _qualification_orm` import so the in-memory SQLite test engine creates the new tables (follows the same pattern as the provisioning import already there)

10. **Create Alembic migration** as `alembic/versions/0005_qualification_initial.py` — `down_revision = "0004_provisioning_initial"`, creates `service_qualification` and `service_qualification_item` tables, full `downgrade()` implemented

11. **Write tests** in `src/qualification/tests/test_qualification_api.py` and `src/qualification/tests/test_qualification_service.py` — cover: list (empty), create (valid + invalid spec FK), get, patch (valid state transitions, invalid transitions → 422), delete; unit tests mock repo layer

12. **Add frontend page** `frontend/qualification.html` — dark-theme SPA consistent with existing pages; activate the Qualification card in `frontend/index.html`

---

**Verification**
- Run `pytest src/qualification/tests/ -v` — all tests green
- Run `pytest --tb=short` — full suite still green (no regressions)
- Start the app with `docker-compose up` and browse `/ui/qualification.html`
- Hit `POST /tmf-api/serviceQualificationManagement/v4/checkServiceQualification` via `/docs` Swagger UI
- Check `/events` endpoint shows `ServiceQualificationCreateEvent` entries

**Decisions**
- TMF645 chosen over TMF653 (Testing) or TMF642 (Alarms) because it fits logically before `ServiceOrder` in the TMF lifecycle and its FK dependency is only on catalog (already stable)
- Router path uses `checkServiceQualification` (the exact TMF645 resource name), consistent with TMF spec naming conventions used in other routers
- `service_spec_id` FK on `ServiceQualificationItem` is nullable to allow free-form qualification requests not tied to a specific spec (per TMF645 spec optionality)
