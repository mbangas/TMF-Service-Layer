# Application Layout

The application layout follows a modular, domain-oriented structure with a clean separation between frontend shell, backend API, shared libraries, and persisted data.

---

## UI Shell Pattern

Each page/module follows the `app-shell` layout:

```
┌─────────────────────────────────────────────────────┐
│  div.app-shell                                      │
│  ┌──────────┬──────────────────────────────────────┐│
│  │ aside    │ main.content                         ││
│  │ .sidebar │  ┌────────────────────────────────┐  ││
│  │          │  │ div.topbar                     │  ││
│  │  [logo]  │  │  [page title]   [actions]      │  ││
│  │          │  └────────────────────────────────┘  ││
│  │  [nav]   │                                      ││
│  │          │  [page content]                      ││
│  │          │                                      ││
│  │  ──────  │                                      ││
│  │ [footer] │                                      ││
│  └──────────┴──────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

- **`aside.sidebar`** — fixed left sidebar with app logo, primary navigation links (MDI icons + label), and a footer section for secondary links (settings, API reference)
- **`main.content`** — scrollable main area containing:
  - `div.topbar` — page title on the left, contextual action buttons on the right
  - Page-specific content (tables, cards, forms, dashboards)

---

## Project File Structure

```
TMF-Service-Layer/
│
├── src/                          # Backend — one sub-package per domain module
│   ├── catalog/                  # TMF633 — Service Catalog Management ✅
│   │   ├── models/               # SID entity data models (Pydantic)
│   │   ├── api/                  # REST API routes (FastAPI router)
│   │   ├── services/             # Business logic & lifecycle state machine
│   │   ├── repositories/         # Data access layer
│   │   └── tests/                # Unit and integration tests
│   │
│   ├── order/                    # TMF641 — Service Order Management ✅
│   ├── inventory/                # TMF638 — Service Inventory ✅
│   ├── provisioning/             # TMF640 — Service Activation & Configuration ✅
│   ├── qualification/            # TMF645 — Service Qualification
│   ├── assurance/                # TMF628 / TMF642 / TMF657 — Assurance
│   ├── testing/                  # TMF653 — Service Test Management
│   ├── problem/                  # TMF621 / TMF656 — Problem & Trouble Tickets
│   ├── commercial/               # TMF648 / TMF651 — Quote & Agreement
│   │
│   ├── shared/                   # Shared across modules
│   │   ├── models/               # Base SID entity classes
│   │   ├── events/               # TMF event notification schemas
│   │   ├── auth/                 # Authentication & authorisation
│   │   └── db/                   # Database session / connection factory
│   │
│   └── main.py                   # FastAPI app entry-point — mounts all routers
│
├── frontend/                     # UI — one HTML page per domain module
│   ├── index.html                # Dashboard — welcome and module shortcuts
│   ├── catalog.html              # Service Catalog (TMF633) ✅
│   ├── orders.html               # Service Orders (TMF641) ✅
│   ├── inventory.html            # Service Inventory (TMF638) ✅
│   ├── provisioning.html         # Service Activation (TMF640) ✅
│   ├── assurance.html            # Assurance / KPIs (TMF628/642/657)
│   ├── testing.html              # Service Tests (TMF653)
│   ├── problems.html             # Problems & Tickets (TMF621/656)
│   ├── apis.html                 # Interactive API reference
│   ├── settings.html             # Application settings
│   ├── css/
│   │   └── style.css             # Dark-theme design system (shared)
│   └── js/
│       └── remote-storage.js     # Global data client (mirrors GedcomDB pattern)
│
├── tests/
│   ├── helpers/                  # Shared test utilities (isolated tmp environments)
│   ├── unit/                     # Per-endpoint isolated tests
│   └── integration/              # Cross-module workflow tests
│
├── docs/
│   ├── Purpose.md
│   ├── TMF-reference.md
│   ├── app-layout.md             # This file
│   └── plans/                    # Per-feature implementation plans
│
├── .github/
│   ├── instructions/
│   └── prompts/
│
├── Dockerfile                    # Multi-stage build (builder + runtime)
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Backend Architecture

```
Browser (HTML + JS)
        │  fetch REST (JSON / HTTP)
        ▼
src/main.py  (FastAPI)
        │
        ├─ /api/catalog          ──► TMF633 ServiceSpecification
        ├─ /api/orders           ──► TMF641 ServiceOrder
        ├─ /api/inventory        ──► TMF638 Service instances
        ├─ /api/provisioning     ──► TMF640 ServiceConfiguration
        ├─ /api/qualification    ──► TMF645 ServiceQualification
        ├─ /api/assurance        ──► TMF628/642/657 KPIs, Alarms, SLA
        ├─ /api/testing          ──► TMF653 ServiceTest
        ├─ /api/problems         ──► TMF621/656 TroubleTicket, ServiceProblem
        └─ /api/commercial       ──► TMF648/651 Quote, Agreement
```

**Communication patterns (same as myLineage):**
- **Synchronous**: REST APIs (JSON / HTTP) — CRUD on all TMF entities
- **Asynchronous**: TMF event notifications for lifecycle state changes (e.g., `ServiceOrderStateChangeEvent`)

---

## Technology Stack

| Layer | Technology | myLineage equivalent |
|---|---|---|
| Backend framework | FastAPI (Python) | Express (Node.js) |
| Data persistence | PostgreSQL + SQLAlchemy | JSON-DATA flat files |
| Frontend | HTML + Vanilla JS + MDI icons | Same |
| CSS design system | Dark theme (adapted from myLineage `style.css`) | `css/style.css` |
| Auth | JWT / OAuth2 | `auth.js` |
| Audit log | Structured event log per domain | `history-logger.js` |
| Containerisation | Docker multi-stage + docker-compose | Same |
| Tests | pytest (unit + integration) | Jest + supertest |

---

## Navigation Structure (Sidebar)

```
[logo]  TMF Service Layer

[nav]
  🏠  Dashboard         →  index.html
  📋  Catalog           →  catalog.html      (TMF633)
  📦  Orders            →  orders.html       (TMF641)
  🗄️  Inventory         →  inventory.html    (TMF638)
  ⚙️  Provisioning      →  provisioning.html (TMF640)
  ✅  Qualification      →  qualification.html(TMF645)
  📊  Assurance         →  assurance.html    (TMF628/642/657)
  🔬  Testing           →  testing.html      (TMF653)
  🚨  Problems          →  problems.html     (TMF621/656)

[footer]
  🔌  APIs              →  apis.html
  ⚙️  Settings          →  settings.html
```

