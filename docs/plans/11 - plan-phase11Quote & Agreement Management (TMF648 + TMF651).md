# Plan: Phase 11 — Quote & Agreement Management (TMF648 + TMF651)

## Objective

Implement the **Commercial Support** domain by creating a new `src/commercial/` module covering **TMF648 Quote Management** (`Quote` + `QuoteItem`) and **TMF651 Agreement Management** (`Agreement` + `ServiceLevelAgreement`). This module activates the `commercial_router` placeholder already in `src/main.py`, adds `frontend/commercial.html` + `frontend/commercial-help.html`, and closes the pre-sales → contract lifecycle loop: ServiceSpecification → ServiceQualification → **Quote** → **Agreement** → ServiceOrder.

---

## Steps

### Phase A — Database Migration

**Step 1.** Create `alembic/versions/0014_commercial_initial.py` (revises `0013_problem_initial`), adding four tables:

- **`quote`**
  - `id` String(36) PK, `href` String(512) nullable
  - `name` String(255) NOT NULL INDEX, `description` Text nullable, `category` String(64) nullable
  - `state` String(32) NOT NULL default=`inProgress` — `inProgress | pending | cancelled | approved | accepted | rejected`
  - `quote_date` DateTime NOT NULL default=utcnow
  - `requested_completion_date` DateTime nullable
  - `expected_fulfillment_start_date` DateTime nullable
  - `completion_date` DateTime nullable (auto-set on `accepted` / `rejected`)
  - `related_service_spec_id` String(36) FK→`service_specification.id` RESTRICT nullable, INDEX
  - `created_at`, `updated_at`
  - Relationship: `items: Mapped[list[QuoteItemOrm]]` (lazy="selectin", cascade="all, delete-orphan")

- **`quote_item`**
  - `id` String(36) PK
  - `action` String(32) NOT NULL default=`add` — `add | modify | delete | noChange`
  - `state` String(32) NOT NULL default=`inProgress`
  - `quantity` Integer nullable default=1
  - `item_price` Numeric(15,2) nullable, `price_type` String(32) nullable — `recurring | nonRecurring | usage`
  - `description` Text nullable
  - `quote_id` String(36) FK→`quote.id` CASCADE, INDEX
  - `related_service_spec_id` String(36) FK→`service_specification.id` RESTRICT nullable
  - `created_at`, `updated_at`

- **`agreement`**
  - `id` String(36) PK, `href` String(512) nullable
  - `name` String(255) NOT NULL INDEX, `description` Text nullable
  - `agreement_type` String(64) nullable — `commercial | technical | SLA`
  - `state` String(32) NOT NULL default=`inProgress` — `inProgress | active | expired | terminated | cancelled`
  - `document_number` String(64) nullable, `version` String(32) nullable default=`1.0`
  - `start_date` DateTime nullable, `end_date` DateTime nullable, `status_change_date` DateTime nullable
  - `related_service_spec_id` String(36) FK→`service_specification.id` RESTRICT nullable, INDEX
  - `related_quote_id` String(36) FK→`quote.id` SET NULL nullable, INDEX
  - `related_service_id` String(36) FK→`service.id` RESTRICT nullable, INDEX
  - `created_at`, `updated_at`
  - Relationship: `slas: Mapped[list[ServiceLevelAgreementOrm]]` (lazy="selectin", cascade="all, delete-orphan")

- **`service_level_agreement`**
  - `id` String(36) PK
  - `name` String(255) NOT NULL
  - `description` Text nullable
  - `metric` String(64) NOT NULL — `availability | latency | throughput | mttr | packetLoss | jitter`
  - `metric_threshold` Numeric(15,4) NOT NULL
  - `metric_unit` String(32) nullable — `percent | ms | Mbps | hours`
  - `conformance_period` String(32) nullable — `daily | weekly | monthly`
  - `agreement_id` String(36) FK→`agreement.id` CASCADE, INDEX
  - `created_at`, `updated_at`

---

### Phase B — ORM Models *(depends on A)*

**Step 2.** Create `src/commercial/models/orm.py`:
- `QuoteOrm` (table `quote`) + `QuoteItemOrm` (table `quote_item`) — pattern mirrors `TroubleTicketOrm` + `TroubleTicketNoteOrm` in `src/problem/models/orm.py`
- `AgreementOrm` (table `agreement`) + `ServiceLevelAgreementOrm` (table `service_level_agreement`)

**Step 3.** Create `src/commercial/models/__init__.py`, `src/commercial/__init__.py`

---

### Phase C — Pydantic Schemas *(parallel with B)*

**Step 4.** Create `src/commercial/models/schemas.py`:
- `QuoteItemCreate(action, quantity, item_price, price_type, description, related_service_spec_id)` · `QuoteItemResponse` (+ `id`, `state`, `created_at`)
- `QuoteCreate(name, description, category, requested_completion_date, expected_fulfillment_start_date, related_service_spec_id, items: list[QuoteItemCreate] = [])` · `QuotePatch` (all optional) · `QuoteResponse`
- `ServiceLevelAgreementCreate(name, description, metric, metric_threshold, metric_unit, conformance_period)` · `ServiceLevelAgreementResponse` (+ `id`)
- `AgreementCreate(name, description, agreement_type, document_number, version, start_date, end_date, related_service_spec_id, related_quote_id, related_service_id, slas: list[ServiceLevelAgreementCreate] = [])` · `AgreementPatch` (all optional) · `AgreementResponse`
- All responses: `model_config = ConfigDict(from_attributes=True)`

---

### Phase D — Repositories *(Steps 5–6 parallel, depend on B)*

**Step 5.** New `src/commercial/repositories/quote_repo.py`:
- `list_all(filters)`, `get(quote_id)`, `create(data)`, `patch(quote_id, data)`, `delete(quote_id)`
- `add_item(quote_id, item_data)`, `delete_item(item_id)`
- Pattern: async `AsyncSession`, follows `src/problem/repositories/trouble_ticket_repo.py`

**Step 6.** New `src/commercial/repositories/agreement_repo.py`:
- `list_all(filters)`, `get(agreement_id)`, `create(data)`, `patch(agreement_id, data)`, `delete(agreement_id)`
- `add_sla(agreement_id, sla_data)`, `delete_sla(sla_id)`

Create `src/commercial/repositories/__init__.py`

---

### Phase E — Service Logic *(depends on D)*

**Step 7.** Create `src/commercial/services/commercial_service.py` with two service classes:

`QuoteService`:
- State machine: `inProgress→pending`, `inProgress→cancelled`, `pending→approved`, `pending→rejected`, `pending→inProgress`, `approved→accepted`, `approved→cancelled` — reject all others with HTTP 422
- On transition to `accepted` or `rejected`: auto-set `completion_date = utcnow()`
- On create: validate `related_service_spec_id` exists (catalog repo lookup)

`AgreementService`:
- State machine: `inProgress→active`, `inProgress→cancelled`, `active→expired`, `active→terminated` — terminal states: `expired`, `terminated`, `cancelled`
- On state change: auto-set `status_change_date = utcnow()`
- On create: validate `related_service_spec_id` (catalog), `related_quote_id` (quote repo), `related_service_id` (inventory repo) — all conditional on non-null

Create `src/commercial/services/__init__.py`

---

### Phase F — API Routes *(depends on E)*

**Step 8.** Create `src/commercial/api/router.py` with two tag groups:

TMF648 — Quote Management:
```
GET    /tmf-api/quoteManagement/v4/quote
POST   /tmf-api/quoteManagement/v4/quote
GET    /tmf-api/quoteManagement/v4/quote/{quote_id}
PATCH  /tmf-api/quoteManagement/v4/quote/{quote_id}
DELETE /tmf-api/quoteManagement/v4/quote/{quote_id}

GET    /tmf-api/quoteManagement/v4/quote/{quote_id}/quoteItem
POST   /tmf-api/quoteManagement/v4/quote/{quote_id}/quoteItem
DELETE /tmf-api/quoteManagement/v4/quote/{quote_id}/quoteItem/{item_id}
```

TMF651 — Agreement Management:
```
GET    /tmf-api/agreementManagement/v4/agreement
POST   /tmf-api/agreementManagement/v4/agreement
GET    /tmf-api/agreementManagement/v4/agreement/{agreement_id}
PATCH  /tmf-api/agreementManagement/v4/agreement/{agreement_id}
DELETE /tmf-api/agreementManagement/v4/agreement/{agreement_id}

GET    /tmf-api/agreementManagement/v4/agreement/{agreement_id}/agreementItem
POST   /tmf-api/agreementManagement/v4/agreement/{agreement_id}/agreementItem
DELETE /tmf-api/agreementManagement/v4/agreement/{agreement_id}/agreementItem/{sla_id}
```

**Step 9.** `src/main.py` — uncomment the `commercial_router` placeholder and register the router

Create `src/commercial/api/__init__.py`

---

### Phase G — Frontend *(parallel with F)*

**Step 10.** `frontend/commercial.html` — new page following `app-shell` layout (ref: `frontend/problems.html`):
- Tab strip: "Quotes" | "Agreements"
- **Quotes tab**: filterable table (state badge, category, linked spec, date), expandable detail row showing quote items + state transition buttons
- **Agreements tab**: filterable table (state badge, type, linked quote, start/end dates), expandable detail row showing SLA metrics + state transition buttons

**Step 11.** `frontend/commercial-help.html` — contextual help page (pattern: `frontend/problems-help.html`)

**Step 12.** `frontend/js/api-client.js` — add two new API method groups:
- `quotes.list(filters)`, `.create(body)`, `.get(id)`, `.patch(id, body)`, `.delete(id)`
- `quotes.items.list(quoteId)`, `.create(quoteId, body)`, `.delete(quoteId, itemId)`
- `agreements.list(filters)`, `.create(body)`, `.get(id)`, `.patch(id, body)`, `.delete(id)`
- `agreements.slas.list(agreementId)`, `.create(agreementId, body)`, `.delete(agreementId, slaId)`

**Step 13.** `frontend/index.html` — add "Commercial" module card (Quotes + Agreements) to the dashboard

**Step 14.** `frontend/qualification.html` — add "Create Quote" button that pre-fills `related_service_spec_id` in the new-quote form on `commercial.html`

---

### Phase H — Tests *(Steps 15–16 parallel)*

**Step 15.** New `src/commercial/tests/test_quote_api.py`:
- CRUD happy path (create, read, patch, delete)
- State transition: valid path accepted (200), invalid backward transition rejected (422)
- QuoteItem CRUD: add item, list items, delete item
- Filter by `state`, `category`
- `related_service_spec_id` not found → 404

**Step 16.** New `src/commercial/tests/test_agreement_api.py`:
- CRUD happy path
- State transitions valid/invalid
- SLA CRUD: add SLA, list SLAs, delete SLA
- Filter by `state`, `agreement_type`
- Invalid FK references → 404

Create `src/commercial/tests/__init__.py`

---

### Phase I — Integration & Documentation *(depends on F, G, H)*

**Step 17.** `README.md` — update Phase 11 row: `📋 Planned` → `✅ Done`; update domain table row for Commercial Support

**Step 18.** `docs/app-layout.md` — add `commercial/` module entry with `TMF648/TMF651` annotation

---

## Timeline

| Phase | Steps | Estimated Effort |
|---|---|---|
| A — Migration | 1 | 0.5 day |
| B–C — ORM + Schemas | 2–4 | 0.5 day |
| D — Repositories | 5–6 | 0.5 day |
| E — Service Logic | 7 | 1 day |
| F — API Routes | 8–9 | 0.5 day |
| G — Frontend | 10–14 | 1.5 days |
| H — Tests | 15–16 | 1 day |
| I — Docs & Integration | 17–18 | 0.5 day |
| **Total** | 18 steps | **~6 days** |

---

## Resources

- **Reference implementation** — `src/problem/` (same dual-entity module pattern combining TMF621 + TMF656; mirrors TMF648 + TMF651 here)
- **Migration reference** — `alembic/versions/0013_problem_initial.py`
- **ORM parent-child pattern** — `TroubleTicketOrm` + `TroubleTicketNoteOrm` in `src/problem/models/orm.py` (selectin + cascade="all, delete-orphan")
- **Service logic pattern** — `TroubleTicketService` + `ServiceProblemService` in `src/problem/services/problem_service.py`
- **Frontend reference** — `frontend/problems.html`, `frontend/problems-help.html`
- **Router placeholder** — `src/main.py` lines 108–109: `# from src.commercial.api.router import router as commercial_router`
- **TMF API specs** — TMF648 v4, TMF651 v4 (TM Forum Open API table)
- **SID reference** — `docs/TMF-reference.md` → Quote, QuoteItem, Agreement, ServiceLevelAgreement entities

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| `service_level_agreement` table name conflicts with existing SLA concept in assurance module | Keep table name as `service_level_agreement` — no collision since assurance uses `service_level` for TMF657; verify before migration |
| FK from `agreement` to `quote` makes deletion order-sensitive | Use SET NULL (not RESTRICT) for `related_quote_id` in agreement — safe to delete quote without cascading to agreement |
| Quote-to-OrderFlow: users may expect an "Accept Quote → Create ServiceOrder" automation | Explicitly out of scope for Phase 11 — document as a cross-domain integration point for a future phase |
| Agreement SLA metrics overlap semantically with TMF657 SLO objects | SLA items here are contractual (per agreement); TMF657 SLOs are operational monitoring targets — document the distinction and keep separate tables |
| Alembic revision chain must stay linear | Verify `0013_problem_initial.py` `revision` identifier before writing `0014_commercial_initial.py` down_revision |

---

## Decisions

- Module path: `src/commercial/` (matches existing placeholder comment in `src/main.py`)
- Agreements link to: `ServiceSpecification` (TMF633), `Quote` (TMF648), and `Service` (TMF638) as FK
- Frontend: full `commercial.html` + `commercial-help.html` with tabbed Quotes/Agreements UI
- Scope EXCLUDES: Quote-to-ServiceOrder automation, TMF622 ProductOrder integration, customer/party management (TMF629/TMF632)
