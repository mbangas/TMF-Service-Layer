# Plan: Phase 10 — Trouble Ticket & Problem Management (TMF621 + TMF656)

## Objective

Implement a complete new `src/problem/` module covering **TMF621 Trouble Ticket Management** (`TroubleTicket` + `TroubleTicketNote`) and **TMF656 Service Problem Management** (`ServiceProblem`). This activates the `problem_router` placeholder already present in `src/main.py`, adds a `frontend/problems.html` page, and completes the operational loop between Alarms (TMF642) → Trouble Tickets (TMF621) → Problem Records (TMF656).

---

## Steps

### Phase A — Database Migration

**Step 1.** Create `alembic/versions/0013_problem_initial.py` (revises `0012_testing_timestamps_fix`), adding three tables:

- **`trouble_ticket`**
  - `id` String(36) PK, `href` String(512) nullable
  - `name` String(255) NOT NULL INDEX, `description` Text nullable
  - `state` String(32) NOT NULL default=`submitted` — `submitted | inProgress | pending | resolved | closed`
  - `severity` String(32) nullable — `critical | major | minor | warning`
  - `priority` Integer nullable (1–4)
  - `ticket_type` String(64) nullable — `serviceFailure | servicePerformanceDegradation | scheduledMaintenance | others`
  - `resolution` Text nullable
  - `expected_resolution_date` DateTime nullable, `resolution_date` DateTime nullable (auto-set on resolve)
  - `related_service_id` String(36) FK→`service.id` RESTRICT nullable, INDEX
  - `related_alarm_id` String(36) FK→`alarm.id` **SET NULL** nullable, INDEX
  - `created_at`, `updated_at`

- **`trouble_ticket_note`**
  - `id` String(36) PK, `text` Text NOT NULL, `author` String(255) nullable
  - `note_date` DateTime NOT NULL default=`utcnow`
  - `ticket_id` String(36) FK→`trouble_ticket.id` CASCADE

- **`service_problem`**
  - `id` String(36) PK, `href` String(512) nullable
  - `name` String(255) NOT NULL INDEX, `description` Text nullable
  - `state` String(32) NOT NULL default=`submitted` — `submitted | confirmed | active | rejected | resolved | closed`
  - `category` String(64) nullable
  - `impact` String(64) nullable — `criticalSystemImpact | localImpact | serviceImpact | noImpact`
  - `priority` Integer nullable (1–4)
  - `root_cause` Text nullable, `resolution` Text nullable
  - `expected_resolution_date` DateTime nullable, `resolution_date` DateTime nullable
  - `related_service_id` String(36) FK→`service.id` RESTRICT nullable
  - `related_ticket_id` String(36) FK→`trouble_ticket.id` **SET NULL** nullable
  - `created_at`, `updated_at`

---

### Phase B — ORM Models

**Step 2.** Create `src/problem/models/orm.py`:
- `TroubleTicketOrm` (table `trouble_ticket`) — pattern mirrors `AlarmOrm` in `src/assurance/models/orm.py`
- `TroubleTicketNoteOrm` (table `trouble_ticket_note`) — FK to `TroubleTicketOrm` with `notes: Mapped[list[TroubleTicketNoteOrm]]` backref (`lazy="selectin"`, `cascade="all, delete-orphan"`)
- `ServiceProblemOrm` (table `service_problem`) — standalone, no child relationship needed initially

**Step 3.** Create `src/problem/models/__init__.py`, `src/problem/__init__.py`

---

### Phase C — Pydantic Schemas

**Step 4.** Create `src/problem/models/schemas.py`:
- `TroubleTicketNoteCreate(text, author)` · `TroubleTicketNoteResponse` (+ `id`, `note_date`)
- `TroubleTicketCreate(name, description, severity, priority, ticket_type, expected_resolution_date, related_service_id, related_alarm_id, notes: list[TroubleTicketNoteCreate] = [])` · `TroubleTicketPatch` (all optional) · `TroubleTicketResponse`
- `ServiceProblemCreate(...)` · `ServiceProblemPatch` · `ServiceProblemResponse`
- All responses: `model_config = ConfigDict(from_attributes=True)`

---

### Phase D — Repositories *(Steps 5–6 are parallel)*

**Step 5.** New `src/problem/repositories/trouble_ticket_repo.py`:
- `list_all(filters)`, `get(ticket_id)`, `create(data)`, `patch(ticket_id, data)`, `delete(ticket_id)`, `add_note(ticket_id, note_data)`, `delete_note(note_id)`
- Pattern: async `AsyncSession`, follows `src/assurance/repositories/alarm_repo.py`

**Step 6.** New `src/problem/repositories/service_problem_repo.py`:
- `list_all(filters)`, `get(problem_id)`, `create(data)`, `patch(problem_id, data)`, `delete(problem_id)`

---

### Phase E — Service Logic *(depends on D)*

**Step 7.** Create `src/problem/services/problem_service.py` with two service classes:

`TroubleTicketService`:
- Allowed state transitions map: `submitted→inProgress`, `inProgress→pending`, `inProgress→resolved`, `pending→inProgress`, `pending→resolved`, `resolved→closed` — reject all others with HTTP 422
- On transition to `resolved`: auto-set `resolution_date = utcnow()`
- On create: validate `related_service_id` exists (inventory repo lookup); validate `related_alarm_id` exists (assurance alarm repo lookup) if provided

`ServiceProblemService`:
- Allowed transitions: `submitted→confirmed`, `submitted→rejected`, `confirmed→active`, `active→resolved`, `resolved→closed`, `confirmed→rejected`
- On transition to `resolved`: auto-set `resolution_date = utcnow()`
- On create: validate `related_service_id` and `related_ticket_id` (if provided)

---

### Phase F — API Routes *(depends on E)*

**Step 8.** Create `src/problem/api/router.py` with two tag groups:

```
# TMF621 — Trouble Ticket Management
GET    /tmf-api/troubleTicketManagement/v4/troubleTicket
POST   /tmf-api/troubleTicketManagement/v4/troubleTicket
GET    /tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}
PATCH  /tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}
DELETE /tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}

GET    /tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}/note
POST   /tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}/note
DELETE /tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}/note/{note_id}

# TMF656 — Service Problem Management
GET    /tmf-api/serviceProblemManagement/v4/problem
POST   /tmf-api/serviceProblemManagement/v4/problem
GET    /tmf-api/serviceProblemManagement/v4/problem/{problem_id}
PATCH  /tmf-api/serviceProblemManagement/v4/problem/{problem_id}
DELETE /tmf-api/serviceProblemManagement/v4/problem/{problem_id}
```

**Step 9.** `src/main.py` — uncomment the `problem_router` placeholder and register the router

Create `src/problem/api/__init__.py`

---

### Phase G — Frontend *(parallel with Phase F)*

**Step 10.** `frontend/problems.html` — new page following `app-shell` layout (ref: `frontend/assurance.html`):
- Sidebar: same nav as other pages + active "Problems" link
- Topbar: "Problem Management" title + "New Ticket" CTA
- Tab strip: "Trouble Tickets" | "Service Problems"
- **Tickets tab**: filterable table (state badge, severity badge, linked service, linked alarm), expandable detail row showing notes + state transition buttons
- **Problems tab**: filterable table (state badge, impact/category, linked ticket), expandable detail row with resolution and root-cause fields

**Step 11.** `frontend/problems-help.html` — contextual help page (pattern: `frontend/assurance-help.html`)

**Step 12.** `frontend/js/api-client.js` — add three new API method groups:
- `troubleTickets.list(filters)`, `.create(body)`, `.get(id)`, `.patch(id, body)`, `.delete(id)`
- `troubleTickets.notes.list(ticketId)`, `.create(ticketId, body)`, `.delete(ticketId, noteId)`
- `serviceProblems.list(filters)`, `.create(body)`, `.get(id)`, `.patch(id, body)`, `.delete(id)`

**Step 13.** `frontend/index.html` — add Problems module card to the dashboard

**Step 14.** `frontend/assurance.html` — add "Raise Ticket" button on each alarm row that pre-fills the `related_alarm_id` in the new-ticket form on `problems.html`

---

### Phase H — Tests *(Steps 15–16 parallel)*

**Step 15.** New `src/problem/tests/test_trouble_ticket_api.py`:
- CRUD happy path (create, read, patch, delete)
- State transition: valid path accepted (201/200), invalid backwards transition rejected (422)
- Note CRUD: add, list, delete
- Filter by `state`, `severity`
- `related_service_id` not found → 404
- `related_alarm_id` not found → 404

**Step 16.** New `src/problem/tests/test_service_problem_api.py`:
- CRUD happy path
- State transitions valid/invalid
- Filter by `state`, `impact`
- Invalid FK references → 404

Create `src/problem/tests/__init__.py`

---

### Phase I — Integration & Documentation *(depends on F, G, H)*

**Step 17.** `README.md` — update Phase 10 row: `📋 Planned` → `✅ Done`; update the domain table row for Problem Management similarly

**Step 18.** `docs/app-layout.md` — add `problem/` module entry with `TMF621/TMF656` annotation

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
| **Total** | | **~6 days** |

---

## Resources

- **Reference implementation** — `src/assurance/` (same dual-entity module combining TMF642 + TMF628; mirrors the TMF621 + TMF656 structure here)
- **Migration reference** — `alembic/versions/0006_assurance_initial.py`
- **Frontend reference** — `frontend/assurance.html`, `frontend/assurance-help.html`
- **TMF API specs** — TMF621 v4, TMF656 v4 (TM Forum Open API table)
- **SID reference** — `docs/TMF-reference.md` — `TroubleTicket`, `ServiceProblem` SID entities

New files to create:

| File | Description |
|---|---|
| `alembic/versions/0013_problem_initial.py` | DB migration |
| `src/problem/__init__.py` | Module init |
| `src/problem/models/__init__.py` | Models init |
| `src/problem/models/orm.py` | SQLAlchemy ORM |
| `src/problem/models/schemas.py` | Pydantic schemas |
| `src/problem/repositories/trouble_ticket_repo.py` | TT data access |
| `src/problem/repositories/service_problem_repo.py` | SP data access |
| `src/problem/services/problem_service.py` | Business logic + state machines |
| `src/problem/api/__init__.py` | API init |
| `src/problem/api/router.py` | FastAPI routes |
| `src/problem/tests/__init__.py` | Tests init |
| `src/problem/tests/test_trouble_ticket_api.py` | TT tests |
| `src/problem/tests/test_service_problem_api.py` | SP tests |
| `frontend/problems.html` | Problems UI page |
| `frontend/problems-help.html` | Problems help page |

Files to update:

| File | Change |
|---|---|
| `src/main.py` | Uncomment `problem_router` placeholder |
| `frontend/js/api-client.js` | Add `troubleTickets` and `serviceProblems` API groups |
| `frontend/index.html` | Add Problems module card |
| `frontend/assurance.html` | Add "Raise Ticket" shortcut on alarm rows |
| `README.md` | Update Phase 10 status |
| `docs/app-layout.md` | Add `problem/` module entry |

---

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| FK violation: alarm deleted while ticket exists | Low | **SET NULL** on `related_alarm_id` delete — preserves ticket history |
| FK violation: ticket deleted while problem exists | Low | **SET NULL** on `related_ticket_id` delete |
| State machine edge cases (many valid paths) | Medium | Explicit allowed-transitions dictionary; all others → HTTP 422 |
| Frontend complexity (two entity types, one page) | Medium | Two-tab layout pattern (follows `assurance.html`) |
| Cross-module Python circular imports (problem ↔ assurance) | Low | Soft-link via IDs only; repos accessed independently — no cross-service imports |
| Service validation adds latency (FK lookups on create) | Low | Single async `get()` per FK; negligible overhead |

---

## Verification Checklist

1. `alembic upgrade head` — migration applies cleanly with no FK errors
2. `pytest src/problem/tests/ -v` — all tests green
3. Start app (`uvicorn src.main:app`) — `/docs` shows TMF621 and TMF656 tag groups with all endpoints
4. POST `TroubleTicket` linked to existing alarm → 201, notes visible in GET response
5. PATCH state `submitted→inProgress` → 200; PATCH state `resolved→submitted` → 422
6. POST `ServiceProblem` linked to the new ticket → 201
7. Navigate to `http://localhost:8000/ui/problems.html` — both tabs render, CRUD works in browser
8. POST TroubleTicket with non-existent `related_service_id` → 404
9. DELETE alarm → `trouble_ticket.related_alarm_id` set to NULL (not cascade-deleted)
