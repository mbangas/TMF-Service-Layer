# TMF Service Layer — TMF641 Service Order Management

## Objective

Implement the second complete domain module — **TMF641 Service Order Management** — including shared event bus, ORM, business logic, REST API, frontend UI, tests, migration, and catalog hardening (RESTRICT FK + 409 guard).

---

## Steps

### Phase 1 — Shared Event Bus
1. Create `src/shared/events/bus.py`: singleton `EventBus` with `publish(event: TMFEvent)` (appends to `deque(maxlen=500)`) and `get_events(limit: int) -> list[TMFEvent]`

### Phase 2 — `order/` Module (TMF641)
2. Create `src/order/models/orm.py`: SQLAlchemy models `ServiceOrderOrm` and `ServiceOrderItemOrm` inheriting from `Base` + `TimestampMixin`
   - `ServiceOrderOrm` fields: `id` (UUID String(36)), `href`, `external_id`, `priority`, `description`, `category`, `state` (indexed, default `"acknowledged"`), `order_date` (DateTime tz), `completion_date` (nullable), `requested_start_date`, `requested_completion_date`, `expected_completion_date`, `start_date`, `note`; TMF annotation fields (`type`, `base_type`, `schema_location`); relationship `order_item` (`lazy="selectin"`, `cascade="all, delete-orphan"`)
   - `ServiceOrderItemOrm` fields: `id` (UUID String(36)), `order_item_id` (String(64), sequence label), `action` (String(32): `add`/`modify`/`delete`/`noChange`), `state` (String(32)), `quantity` (Integer, default 1), `service_order_id` (FK → `service_order.id` CASCADE), `service_spec_id` (FK → `service_specification.id`, `ondelete="RESTRICT"`, nullable), `service_spec_href`, `service_spec_name`, `service_name`, `service_description`, `note`; `TimestampMixin`

3. Create `src/order/models/schemas.py`: Pydantic schemas following the `XxxBase → XxxCreate → XxxPatch → XxxResponse` pattern
   - `ServiceOrderItemCreate`, `ServiceOrderItemResponse`
   - `ServiceOrderCreate` (name, description, category, priority, `requested_start_date`, `requested_completion_date`, nested `list[ServiceOrderItemCreate]`)
   - `ServiceOrderPatch` (all fields `| None`, including `state` for lifecycle transitions)
   - `ServiceOrderResponse` extends `BaseEntity`; includes nested `list[ServiceOrderItemResponse]`

4. Create `src/order/repositories/service_order_repo.py`: `ServiceOrderRepository` with async methods `get_all(offset, limit, state)`, `get_by_id`, `create`, `patch`, `delete`; same `flush()`+`refresh()` pattern; `get_all` returns `tuple[list[ServiceOrderOrm], int]`

5. Create `src/order/services/order_service.py`: `OrderService` with:
   - State machine `_ALLOWED_TRANSITIONS`: `acknowledged → {inProgress, cancelled}`, `inProgress → {completed, failed, cancelled}`, terminals `completed/failed/cancelled` → no further transitions
   - `create_order()` — forces `state="acknowledged"`, sets `order_date=datetime.now(utc)`; publishes `ServiceOrderCreateEvent` via `EventBus`
   - `patch_order()` — validates lifecycle transition; sets `completion_date=now(utc)` when entering a terminal state; publishes `ServiceOrderStateChangeEvent`
   - `delete_order()` — only `cancelled` orders may be deleted (422 otherwise); wraps `repo.delete()` call; 404 if not found
   - All get-or-404 patterns mirror `CatalogService`

6. Create `src/order/api/router.py`: `APIRouter(prefix="/tmf-api/serviceOrdering/v4/serviceOrder", tags=["TMF641 - Service Order"])`
   - `GET /` (paginated, `state` query filter, `X-Total-Count` + `X-Result-Count` headers) → 200
   - `POST /` → 201
   - `GET /{order_id}` → 200 / 404
   - `PATCH /{order_id}` → 200 / 404 / 422
   - `DELETE /{order_id}` → 204 / 404 / 422
   - Same `_get_service()` dependency factory pattern as catalog router

### Phase 3 — Catalog Hardening
7. Update `src/catalog/services/catalog_service.py`: wrap `repo.delete()` in `try/except IntegrityError` → raise `HTTPException(409, "Specification is referenced by existing service orders and cannot be deleted.")`

### Phase 4 — Alembic Migration
8. Create `alembic/versions/0002_order_initial.py`:
   - `down_revision = "0001_catalog_initial"`
   - Creates `service_order` table with index on `state`
   - Creates `service_order_item` table with FK to `service_order` (CASCADE) and FK to `service_specification` (`RESTRICT`); index on both FK columns
   - `upgrade()` / `downgrade()` following the existing migration pattern

### Phase 5 — Entry Point Updates
9. Update `src/main.py`:
   - Uncomment / add `from src.order.api.router import router as order_router` and `app.include_router(order_router)`
   - Add `GET /events` endpoint (dev-only, returns `EventBus.get_events(limit=100)`) gated by `settings.app_env == "development"`
   - Import `src.order.models.orm` in `alembic/env.py` so autogenerate detects order tables

### Phase 6 — Frontend (Orders)
10. Create `frontend/orders.html`: app-shell (matching `catalog.html` structure)
    - Table columns: Order ID (truncated), Category, Priority, State (badge), Order Date, Items, — actions
    - State badges: `acknowledged`, `inProgress`, `completed`, `failed`, `cancelled` with distinct colours
    - Topbar actions: `state` filter dropdown + "New Order" button
    - Create modal: name, description, category, priority, `requested_completion_date`; inline item form (action, service spec name)
    - Action buttons per row: state-transition button (context-aware: "Start" / "Complete" / "Fail" / "Cancel") + Delete (only if cancelled)
    - Pagination (`offset`/`limit`, `X-Total-Count`)

11. Update `frontend/index.html`: change the TMF641 Orders card from `module-card--disabled` to an active link (`href="orders.html"`); remove the "Coming soon" badge from that card

### Phase 7 — Tests
12. Create `src/order/tests/test_order_api.py`: integration tests with SQLite in-memory + `httpx.AsyncClient` (mirroring `test_catalog_api.py` fixture pattern)
    - `test_create_order_returns_201` — state forced to `acknowledged`
    - `test_create_order_missing_name_returns_422`
    - `test_list_orders_returns_200_with_total_count_header`
    - `test_list_orders_filter_by_state`
    - `test_get_order_by_id`
    - `test_get_nonexistent_order_returns_404`
    - `test_patch_valid_transition_acknowledged_to_inprogress`
    - `test_patch_invalid_transition_returns_422`
    - `test_patch_nonexistent_returns_404`
    - `test_delete_cancelled_order_returns_204`
    - `test_delete_active_order_returns_422`
    - `test_delete_nonexistent_returns_404`
    - `test_completion_date_set_on_terminal_transition`

13. Create `src/order/tests/test_order_service.py`: unit tests with mocked repo
    - `test_create_order_forces_acknowledged_state`
    - `test_create_order_sets_order_date`
    - `test_create_order_publishes_create_event`
    - `test_patch_publishes_state_change_event`
    - `test_patch_sets_completion_date_on_terminal`
    - `test_patch_does_not_set_completion_date_on_non_terminal`
    - `test_delete_cancelled_succeeds`
    - `test_delete_inprogress_raises_422`
    - `test_delete_nonexistent_raises_404`
    - Parametric lifecycle transition matrix (all valid + invalid combinations)

---

## Timeline

| Phase | Estimated Effort |
|---|---|
| Phase 1 — Event bus | 0.5 day |
| Phase 2 — Order module | 2 days |
| Phase 3 — Catalog hardening | 0.25 day |
| Phase 4 — Migration | 0.5 day |
| Phase 5 — Entry point updates | 0.25 day |
| Phase 6 — Frontend | 1.5 days |
| Phase 7 — Tests | 1 day |
| **Total** | **~6 days** |

---

## Resources

- Python 3.11+
- FastAPI, SQLAlchemy (async), asyncpg, Alembic, Pydantic v2
- PostgreSQL 15+
- Docker + docker-compose
- TMF641 Open API specification (reference: `docs/TMF-reference.md`)
- Architecture reference: `docs/app-layout.md`
- Existing catalog module patterns: `src/catalog/` (mirror exactly)

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| FK `ondelete` on `service_spec_id` | `RESTRICT` | Preserves referential integrity; catalog service returns 409 when a referenced spec is deleted |
| Event notifications | In-memory `EventBus` (`deque(maxlen=500)`) | No broker required; shared schema already in `src/shared/events/schemas.py`; accessible via `GET /events` in dev |
| `order_date` source | API-set (`datetime.now(utc)` on POST) | Not client-supplied; ensures server-side audit trail |
| `ServiceOrderItem.id` | UUID String(36) | Consistent with `ServiceSpecCharacteristicOrm`; safe for distributed systems |
| Terminal state `completion_date` | Auto-set by `OrderService.patch_order()` | Service layer responsibility; not delegated to repository or client |
| Delete guard | Only `cancelled` orders | Mirrors catalog pattern (only `draft`/`retired` specs deletable) |

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| RESTRICT FK blocks spec deletion unexpectedly | Catalog service wraps `repo.delete()` in `IntegrityError` handler; returns 409 with clear message |
| Async SQLAlchemy + nested item creation complexity | Follow existing `service_spec_characteristic` pattern: append child ORM objects to relationship list, single `flush()`+`refresh()` |
| In-memory event bus lost on restart | Acceptable in this iteration; document that it is dev-only diagnostic tooling |
| `aiosqlite` + datetime handling in tests | Use string-based comparison or `isoformat()` in assertions; avoid tz-aware comparison issues |
| Frontend CORS when adding new endpoint | CORS already configured globally in `main.py`; no additional changes needed |
