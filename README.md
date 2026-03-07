# TMF Service Layer

> A modular implementation of the **TM Forum Open Digital Architecture (ODA) Service Layer**, built on TMF Open APIs and the Shared Information/Data (SID) model.

---

## What the Project Does

The **TMF Service Layer** is the core domain of the TM Forum ODA responsible for managing the full service lifecycle — from catalog design through ordering, provisioning, assurance, and testing. It bridges the **Product/Customer domain** and the **Resource/Network domain**, ensuring that Customer Facing Services (CFS) are correctly provisioned, monitored, and maintained via underlying Resource Facing Services (RFS).

This application implements the following functional domains:

| Domain | Key Capability | TMF API | Status |
|---|---|---|---|
| Service Design | Service catalog, specifications, SLA | TMF633 | ✅ Implemented |
| Pre-Sales | Service qualification and availability checks | TMF645 | ✅ Implemented |
| Order Management | Full service order lifecycle management | TMF641 | ✅ Implemented |
| Provisioning | Service activation and configuration | TMF640 | ✅ Implemented |
| Inventory | Active service instances and relationships | TMF638 | ✅ Implemented |
| Assurance | Alarms, performance, SLA management | TMF628, TMF642, TMF657 | ✅ Implemented |
| Testing | Automated service test and validation | TMF653 | ✅ Implemented |
| Problem Management | Incidents, trouble tickets, root cause | TMF621, TMF656 | 📋 Planned |
| Commercial Support | Quotes, agreements, SLAs | TMF648, TMF651 | 📋 Planned |

For the full mapping of ODA components → TMF APIs → SID entities, see [docs/TMF-reference.md](docs/TMF-reference.md).

### Service Catalog Design & Management (TMF633) ✅

The **Service Catalog** module is the first implemented component. It provides the foundation for all other domains by defining service templates before any order, provisioning, or assurance flow begins.

**What is covered:**
- `ServiceSpecification` — define and version service templates (CFS and RFS)
- `ServiceSpecCharacteristic` — configure parameters such as speed, QoS, or technology type
- `ServiceLevelSpecification` — attach SLA constraints to service definitions
- `ServiceSpecRelationship` — model CFS → RFS hierarchies
- Lifecycle management: `active` → `retired` → `obsolete`

### Service Order Management (TMF641) ✅

The **Service Order** module manages the full lifecycle of service orders submitted by customers or other systems. It enforces a strict state machine and automatically creates inventory records on completion.

### Service Inventory (TMF638) ✅

The **Service Inventory** module tracks all active (and historical) service instances. Services are created automatically when an order completes, and can be managed independently through the inventory API.

### Service Activation & Configuration (TMF640) 🔄

> See the [Implemented Modules](#implemented-modules) section for API endpoints, module structure, and usage examples.

---

## Implementation Phases

| Phase | Scope | Status |
|---|---|---|
| Phase 1 | Project setup, infrastructure, shared layer, auth stub, event bus | ✅ Done |
| Phase 2a | TMF633 Service Catalog — ServiceSpecification CRUD + lifecycle | ✅ Done |
| Phase 2b | TMF641 Service Order Management — order lifecycle + FK to catalog | ✅ Done |
| Phase 3 | TMF638 Service Inventory + tech-debt fixes | ✅ Done |
| Phase 4 | TMF640 Service Activation & Configuration (Provisioning) | ✅ Done |
| Phase 5 | TMF645 Service Qualification | ✅ Done |
| Phase 6 | TMF642 / TMF628 / TMF657 Assurance (Alarms, Performance, SLA) | ✅ Done |
| Phase 7 | TMF653 Service Test Management | ✅ Done |
| Phase 8 (TMFC006) | TMF633/TMF638 Characteristic Management — `CharacteristicValueSpecification` + `CharacteristicValue` standalone CRUD | ✅ Done |
| Phase 9 | TMF621 / TMF656 Trouble Ticket & Problem Management | 📋 Planned |
| Phase 10 | TMF648 / TMF651 Quote & Agreement Management | 📋 Planned |
| Phase 11 | Auth hardening (JWT + RBAC), CI/CD, production hardening | 📋 Planned |

---

## Why the Project is Useful

### Key Features

- **Standards-based**: Fully aligned with TM Forum ODA Frameworx, Open APIs, and SID data model
- **CFS ↔ RFS orchestration**: Manages the relationship between customer-facing and resource-facing services end-to-end
- **Dual communication model**: Supports synchronous REST (TMF Open APIs) and asynchronous event-driven flows (TMF events)
- **Modular architecture**: Each functional domain is independently deployable and maintainable
- **Interoperability**: SID-mapped entities ensure consistent integration across OSS/BSS systems and Product, Service, and Resource layers

### Expected Benefits

- Reduced service activation time through automated provisioning orchestration
- Full lifecycle visibility via Service Inventory (TMF638)
- Automated provisioning, monitoring, and troubleshooting workflows
- Standards-compliant integration with existing OSS/BSS platforms

---

## Getting Started

### Prerequisites

- Python 3.11+
- Git

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/mbangas/TMF-Service-Layer.git
   cd TMF-Service-Layer
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux / macOS
   source .venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

> **Note:** The application is currently under active development. Setup and run instructions will be updated as each module is implemented. See [docs/plans/](docs/plans/) for the current development roadmap.

### Updating the Project

To pull the latest changes and update dependencies:

```bash
git pull origin main
pip install -r requirements.txt
```

---

## Project Structure

```
TMF-Service-Layer/
├── docs/
│   ├── Purpose.md          # Project purpose and scope
│   ├── TMF-reference.md    # Full TMF API / SID / ODA reference tables
│   └── plans/              # Implementation plans (per feature)
├── src/                    # Application source code (modular per domain)
└── README.md
```

Each functional domain (catalog, order, inventory, provisioning, assurance, etc.) will live under `src/` as a self-contained module.

---

## Implemented Modules

### Service Catalog Design & Management — TMF633

The **Service Catalog** module is the foundation of the Service Layer. It enables the definition, versioning, and lifecycle management of all services offered by the platform. All downstream domains (Order Management, Provisioning, Inventory) depend on catalog definitions to operate.

#### Responsibilities

- Create, update, version, and retire **ServiceSpecification** entities
- Define **ServiceSpecCharacteristic** (configurable service parameters and their value types)
- Associate **ServiceLevelSpecification (SLS)** to enforce SLA constraints per service
- Manage catalog item lifecycle states: `active`, `retired`, `obsolete`
- Support hierarchical service design: CFS specifications referencing RFS specifications via `ServiceSpecRelationship`

#### Key SID Entities

| SID Entity | Description |
|---|---|
| `ServiceSpecification` | Technical and functional definition of a service (template) |
| `ServiceSpecCharacteristic` | Configurable parameter of a service specification |
| `CharacteristicValueSpecification` | Allowed (or enumerated) values for a characteristic parameter |
| `ServiceLevelSpecification` | SLA constraints associated with a service |
| `ServiceSpecRelationship` | Relationship between specifications (e.g., CFS → RFS) |

#### API Endpoints (TMF633)

| Method | Path | Description |
|---|---|---|
| `GET` | `/serviceSpecification` | List all service specifications |
| `GET` | `/serviceSpecification/{id}` | Retrieve a specific service specification |
| `POST` | `/serviceSpecification` | Create a new service specification |
| `PATCH` | `/serviceSpecification/{id}` | Update a service specification |
| `DELETE` | `/serviceSpecification/{id}` | Remove a service specification |
| `GET` | `/serviceSpecification/{id}/serviceSpecCharacteristic` | List characteristics for a specification |
| `POST` | `/serviceSpecification/{id}/serviceSpecCharacteristic` | Add a characteristic to a specification |
| `GET` | `/serviceSpecification/{id}/serviceSpecCharacteristic/{cid}` | Retrieve a characteristic |
| `PATCH` | `/serviceSpecification/{id}/serviceSpecCharacteristic/{cid}` | Update a characteristic |
| `DELETE` | `/serviceSpecification/{id}/serviceSpecCharacteristic/{cid}` | Remove a characteristic |
| `GET` | `/serviceSpecification/{id}/serviceSpecCharacteristic/{cid}/characteristicValueSpecification` | List value specs |
| `POST` | `/serviceSpecification/{id}/serviceSpecCharacteristic/{cid}/characteristicValueSpecification` | Add a value spec |
| `DELETE` | `/serviceSpecification/{id}/serviceSpecCharacteristic/{cid}/characteristicValueSpecification/{vid}` | Remove a value spec |

#### Module Location

```
src/
└── catalog/
    ├── models/          # SID entity data models (ServiceSpecification, etc.)
    ├── api/             # TMF633 REST API routes
    ├── services/        # Business logic (versioning, lifecycle state machine)
    ├── repositories/    # Data access layer
    └── tests/           # Unit and integration tests
```

#### Usage Example

```python
# Create a new service specification (CFS — Broadband Internet)
POST /serviceSpecification
{
  "name": "Broadband Internet 1Gbps",
  "version": "1.0",
  "lifecycleStatus": "active",
  "serviceSpecCharacteristic": [
    {
      "name": "downloadSpeed",
      "valueType": "integer",
      "serviceSpecCharacteristicValue": [{ "value": 1000, "unitOfMeasure": "Mbps" }]
    },
    {
      "name": "uploadSpeed",
      "valueType": "integer",
      "serviceSpecCharacteristicValue": [{ "value": 200, "unitOfMeasure": "Mbps" }]
    }
  ],
  "serviceLevelSpecification": [
    { "name": "Availability SLA", "availability": 99.9 }
  ]
}
```

### Service Order Management — TMF641

The **Service Order** module is the second implemented component. It manages the end-to-end lifecycle of service orders, from submission through cancellation or completion.

#### Responsibilities

- Accept and validate `ServiceOrder` requests referencing catalog specifications
- Enforce a strict order state machine: `acknowledged → inProgress → completed | cancelled | failed | partial`
- Persist `ServiceOrderItem` entries with their own states and requested actions (`add`, `modify`, `delete`, `noChange`)
- Automatically create `Service` inventory records when an order reaches `completed`
- Publish TMF events when order or item states advance

#### Key SID Entities

| SID Entity | Description |
|---|---|
| `ServiceOrder` | Customer or system request to add, modify, or delete a service |
| `ServiceOrderItem` | Individual line item specifying the action and target service spec |

#### API Endpoints (TMF641)

| Method | Path | Description |
|---|---|---|
| `GET` | `/tmf-api/serviceOrder/v4/serviceOrder` | List all service orders |
| `GET` | `/tmf-api/serviceOrder/v4/serviceOrder/{id}` | Retrieve a specific service order |
| `POST` | `/tmf-api/serviceOrder/v4/serviceOrder` | Create a new service order |
| `PATCH` | `/tmf-api/serviceOrder/v4/serviceOrder/{id}` | Update (advance state of) a service order |
| `DELETE` | `/tmf-api/serviceOrder/v4/serviceOrder/{id}` | Cancel a service order |

#### Module Location

```
src/
└── order/
    ├── models/          # ORM + Pydantic schemas (ServiceOrder, ServiceOrderItem)
    ├── api/             # TMF641 REST API routes
    ├── services/        # Business logic (state machine, inventory auto-create)
    ├── repositories/    # Data access layer
    └── tests/           # Unit and integration tests
```

---

### Service Inventory — TMF638

The **Service Inventory** module tracks all provisioned service instances. Instances are created automatically when an order completes and can also be created, queried, and managed independently.

#### Responsibilities

- Store and manage `Service` instances linked to their originating spec and order
- Enforce a lifecycle state machine: `feasibilityChecked → designed → reserved → inactive → active → terminated`
- Track `ServiceCharacteristic` values per instance
- Prevent deletion of services that are not `inactive` or `terminated`
- Publish TMF events on creation and state change

#### Key SID Entities

| SID Entity | Description |
|---|---|
| `Service` | An active (or historical) service instance delivered to a customer |
| `ServiceCharacteristic` | Instantiated characteristic parameter for a specific service instance |
| `CharacteristicValue` | Specific value assigned to a characteristic on a service instance |

#### API Endpoints (TMF638)

| Method | Path | Description |
|---|---|---|
| `GET` | `/tmf-api/serviceInventory/v4/service` | List service instances (with optional state filter) |
| `GET` | `/tmf-api/serviceInventory/v4/service/{id}` | Retrieve a specific service instance |
| `POST` | `/tmf-api/serviceInventory/v4/service` | Create a new service instance |
| `PATCH` | `/tmf-api/serviceInventory/v4/service/{id}` | Update / advance state of a service instance |
| `DELETE` | `/tmf-api/serviceInventory/v4/service/{id}` | Delete a terminated or inactive service instance |
| `GET` | `/tmf-api/serviceInventory/v4/service/{id}/serviceCharacteristic` | List characteristics of a service |
| `POST` | `/tmf-api/serviceInventory/v4/service/{id}/serviceCharacteristic` | Add a characteristic to a service |
| `GET` | `/tmf-api/serviceInventory/v4/service/{id}/serviceCharacteristic/{cid}` | Retrieve a characteristic |
| `PATCH` | `/tmf-api/serviceInventory/v4/service/{id}/serviceCharacteristic/{cid}` | Update a characteristic |
| `DELETE` | `/tmf-api/serviceInventory/v4/service/{id}/serviceCharacteristic/{cid}` | Remove a characteristic |
| `GET` | `/tmf-api/serviceInventory/v4/service/{id}/serviceCharacteristic/{cid}/characteristicValue` | List values of a characteristic |
| `POST` | `/tmf-api/serviceInventory/v4/service/{id}/serviceCharacteristic/{cid}/characteristicValue` | Add a value |
| `DELETE` | `/tmf-api/serviceInventory/v4/service/{id}/serviceCharacteristic/{cid}/characteristicValue/{vid}` | Remove a value |

#### Module Location

```
src/
└── inventory/
    ├── models/          # ORM + Pydantic schemas (Service, ServiceCharacteristic)
    ├── api/             # TMF638 REST API routes
    ├── services/        # Business logic (state machine, event publishing)
    ├── repositories/    # Data access layer
    └── tests/           # Unit and integration tests
```

---

### Service Qualification — TMF645

The **Service Qualification** module provides pre-sales feasibility checks, sitting between Service Design (TMF633) and Service Order (TMF641) in the TMF lifecycle.

#### API Endpoints (TMF645)

| Method | Path | Description |
|---|---|---|
| `GET` | `/tmf-api/serviceQualificationManagement/v4/checkServiceQualification` | List qualification requests |
| `GET` | `/tmf-api/serviceQualificationManagement/v4/checkServiceQualification/{id}` | Retrieve a qualification |
| `POST` | `/tmf-api/serviceQualificationManagement/v4/checkServiceQualification` | Submit a new qualification request |
| `PATCH` | `/tmf-api/serviceQualificationManagement/v4/checkServiceQualification/{id}` | Advance qualification state |
| `DELETE` | `/tmf-api/serviceQualificationManagement/v4/checkServiceQualification/{id}` | Delete a terminal qualification |

---

### Service Activation & Configuration — TMF640

The **Service Activation & Configuration** module is the provisioning engine of the Service Layer. It drives service lifecycle changes on inventory instances through auditable, job-oriented workflows.

#### Responsibilities

- Raise `ServiceActivationJob` records against any `Service` instance in inventory
- Enforce a job state machine: `accepted → running → succeeded | failed | cancelled`
- On job `succeeded`, automatically transition the target Service to its new lifecycle state
- Attach `ServiceConfigurationParam` key/value entries to a job for configuration history
- Prevent deletion of jobs that are not `failed` or `cancelled`
- Publish TMF events on job creation and state change

#### Job Type → Service State Mapping

| Job Type | Required Service State | Resulting Service State |
|---|---|---|
| `provision` | `inactive` | `active` |
| `activate` | `inactive` | `active` |
| `modify` | `active` | `active` (params updated) |
| `deactivate` | `active` | `inactive` |
| `terminate` | `active` or `inactive` | `terminated` |

#### Key SID Entities

| SID Entity | Description |
|---|---|
| `ServiceActivationJob` | Job that drives activation or configuration of a Service instance |
| `ServiceConfigurationParam` | Key/value configuration parameter attached to a job |

#### API Endpoints (TMF640)

| Method | Path | Description |
|---|---|---|
| `GET` | `/tmf-api/serviceActivationConfiguration/v4/serviceActivationJob` | List activation jobs (with optional state/type/service filters) |
| `GET` | `/tmf-api/serviceActivationConfiguration/v4/serviceActivationJob/{id}` | Retrieve a specific job |
| `POST` | `/tmf-api/serviceActivationConfiguration/v4/serviceActivationJob` | Create a new activation job |
| `PATCH` | `/tmf-api/serviceActivationConfiguration/v4/serviceActivationJob/{id}` | Advance job state (drives inventory state on succeeded) |
| `DELETE` | `/tmf-api/serviceActivationConfiguration/v4/serviceActivationJob/{id}` | Delete a failed or cancelled job |

#### Module Location

```
src/
└── provisioning/
    ├── models/          # ORM + Pydantic schemas (ServiceActivationJob, ServiceConfigurationParam)
    ├── api/             # TMF640 REST API routes
    ├── services/        # Business logic (state machine, inventory integration, event publishing)
    ├── repositories/    # Data access layer
    └── tests/           # Unit and integration tests
```

---

### Service Assurance — TMF642 / TMF628 / TMF657

The **Service Assurance** module closes the monitoring and SLA enforcement loop for active services. It covers three tightly-integrated domains: reactive fault management (alarms), proactive performance measurement, and threshold-based Service Level Objective evaluation.

#### Responsibilities

- Raise and lifecycle-manage `Alarm` events against active service instances (TMF642)
- Schedule, execute, and record `PerformanceMeasurement` jobs per service and metric (TMF628)
- Define `ServiceLevelObjective` thresholds that are automatically evaluated on measurement completion (TMF657)
- Auto-detect SLO violations: comparing recorded metric values against `above`/`below` thresholds
- Publish fault and violation events to the TMF event bus

#### Alarm State Machine (TMF642)

```
raised → acknowledged → cleared
```

#### Measurement State Machine (TMF628)

```
scheduled → completed | failed
```

Completing a measurement with a metric value **automatically triggers SLO violation detection**.

#### SLO State Machine (TMF657)

```
active ↔ violated  (violated only by automatic check_violations, not via PATCH)
active | violated → suspended
suspended → active
```

#### Key SID Entities

| SID Entity | Description |
|---|---|
| `Alarm` | Fault event raised against an active Service instance |
| `PerformanceMeasurement` | Scheduled or completed metric measurement per service |
| `ServiceLevelObjective` | Threshold definition with automatic violation detection |

#### API Endpoints (TMF642 — Alarm Management)

| Method | Path | Description |
|---|---|---|
| `GET` | `/tmf-api/alarmManagement/v4/alarm` | List alarms |
| `GET` | `/tmf-api/alarmManagement/v4/alarm/{id}` | Retrieve an alarm |
| `POST` | `/tmf-api/alarmManagement/v4/alarm` | Raise a new alarm |
| `PATCH` | `/tmf-api/alarmManagement/v4/alarm/{id}` | Acknowledge or clear an alarm |
| `DELETE` | `/tmf-api/alarmManagement/v4/alarm/{id}` | Delete a cleared alarm |

#### API Endpoints (TMF628 — Performance Management)

| Method | Path | Description |
|---|---|---|
| `GET` | `/tmf-api/performanceManagement/v4/performanceMeasurement` | List measurements |
| `GET` | `/tmf-api/performanceManagement/v4/performanceMeasurement/{id}` | Retrieve a measurement |
| `POST` | `/tmf-api/performanceManagement/v4/performanceMeasurement` | Schedule a measurement |
| `PATCH` | `/tmf-api/performanceManagement/v4/performanceMeasurement/{id}` | Complete or fail a measurement |
| `DELETE` | `/tmf-api/performanceManagement/v4/performanceMeasurement/{id}` | Delete a completed/failed measurement |

#### API Endpoints (TMF657 — Service Level Management)

| Method | Path | Description |
|---|---|---|
| `GET` | `/tmf-api/serviceLevelManagement/v4/serviceLevel` | List SLOs |
| `GET` | `/tmf-api/serviceLevelManagement/v4/serviceLevel/{id}` | Retrieve an SLO |
| `POST` | `/tmf-api/serviceLevelManagement/v4/serviceLevel` | Create an SLO |
| `PATCH` | `/tmf-api/serviceLevelManagement/v4/serviceLevel/{id}` | Suspend or restore an SLO |
| `DELETE` | `/tmf-api/serviceLevelManagement/v4/serviceLevel/{id}` | Delete a suspended SLO |

#### Module Location

```
src/
└── assurance/
    ├── models/          # ORM + Pydantic schemas (Alarm, PerformanceMeasurement, ServiceLevelObjective)
    ├── api/             # Aggregate router (alarm_router + measurement_router + slo_router)
    ├── services/        # Business logic (state machines, violation detection, event publishing)
    ├── repositories/    # Data access layer (alarm_repo, measurement_repo, slo_repo)
    └── tests/           # Unit and integration tests
```

---

### Service Test Management — TMF653

The **Service Testing** module provides end-to-end automated and manual test lifecycle management for active service instances. It implements the TMF653 Service Test Management API.

#### Responsibilities

- Define reusable `ServiceTestSpecification` templates with version and type metadata
- Execute `ServiceTest` runs against active service instances referencing a spec or ad-hoc
- Capture `TestMeasure` results (pass/fail/inconclusive) while a test is `inProgress`
- Enforce test lifecycle state machine with automatic start/end timestamp recording
- Guard against running tests against `obsolete` specifications
- Publish TMF events on test create, state change, completion, and failure

#### ServiceTestSpecification State Machine

```
active → retired → obsolete  (terminal — only obsolete specs may be deleted)
```

#### ServiceTest State Machine

```
planned → inProgress → completed
                    → failed
                    → cancelled
planned → cancelled
```

> Direct transition `planned → completed` is **not permitted**. Tests must pass through `inProgress`.

#### Key SID Entities

| SID Entity | Description |
|---|---|
| `ServiceTestSpecification` | Reusable test template with type, version, and optional FK to catalog spec |
| `ServiceTest` | An individual test run against an active service instance |
| `TestMeasure` | A single metric measurement captured during an inProgress test run |

#### API Endpoints (TMF653 — Test Specification)

| Method | Path | Description |
|---|---|---|
| `GET` | `/tmf-api/serviceTest/v4/serviceTestSpecification` | List test specifications |
| `GET` | `/tmf-api/serviceTest/v4/serviceTestSpecification/{id}` | Retrieve a test specification |
| `POST` | `/tmf-api/serviceTest/v4/serviceTestSpecification` | Create a test specification |
| `PATCH` | `/tmf-api/serviceTest/v4/serviceTestSpecification/{id}` | Advance lifecycle state |
| `DELETE` | `/tmf-api/serviceTest/v4/serviceTestSpecification/{id}` | Delete an obsolete specification |

#### API Endpoints (TMF653 — Service Test)

| Method | Path | Description |
|---|---|---|
| `GET` | `/tmf-api/serviceTest/v4/serviceTest` | List service tests |
| `GET` | `/tmf-api/serviceTest/v4/serviceTest/{id}` | Retrieve a service test (with embedded measures) |
| `POST` | `/tmf-api/serviceTest/v4/serviceTest` | Create a new test run |
| `PATCH` | `/tmf-api/serviceTest/v4/serviceTest/{id}` | Advance test state |
| `DELETE` | `/tmf-api/serviceTest/v4/serviceTest/{id}` | Delete a terminal test (cascades measures) |
| `POST` | `/tmf-api/serviceTest/v4/serviceTest/{id}/testMeasure` | Add a measure to an inProgress test |
| `GET` | `/tmf-api/serviceTest/v4/serviceTest/{id}/testMeasure` | List measures for a test |

#### Module Location

```
src/
└── testing/
    ├── models/          # ORM + Pydantic schemas (ServiceTestSpecification, ServiceTest, TestMeasure)
    ├── api/             # TMF653 REST API routes (spec_router + test_router)
    ├── services/        # Business logic (state machines, FK guards, event publishing)
    ├── repositories/    # Data access layer (test_spec_repo, test_repo)
    └── tests/           # Unit and integration tests
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  Product / Customer Layer            │
│          (TMF622 Product Order, TMF648 Quote)        │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                    SERVICE LAYER                     │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │ Catalog  │  │  Order   │  │    Provisioning    │ │
│  │ TMF633   │  │  TMF641  │  │      TMF640        │ │
│  └──────────┘  └──────────┘  └────────────────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │Inventory │  │Assurance │  │      Testing       │ │
│  │ TMF638   │  │TMF628/   │  │      TMF653        │ │
│  │          │  │TMF642/   │  │                    │ │
│  │          │  │TMF657    │  │                    │ │
│  └──────────┘  └──────────┘  └────────────────────┘ │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│               Resource / Network Layer               │
│        (TMF639 Resource Inventory, TMF640 RFS)       │
└─────────────────────────────────────────────────────┘
```

**Communication patterns:**
- **Synchronous**: REST APIs following TMF Open API standards (JSON / HTTP)
- **Asynchronous**: Event-driven flows using TMF event notifications

---

## Documentation

| Document | Description |
|---|---|
| [docs/Purpose.md](docs/Purpose.md) | Project scope and positioning within ODA |
| [docs/TMF-reference.md](docs/TMF-reference.md) | Full reference: ODA components, TMF APIs, SID entities |
| [docs/plans/](docs/plans/) | Feature implementation plans |

---

## Getting Help

- **TM Forum ODA documentation**: [https://www.tmforum.org/oda](https://www.tmforum.org/oda)
- **TMF Open API table**: [https://www.tmforum.org/open-apis](https://www.tmforum.org/open-apis)
- **Issues**: Open a GitHub Issue in this repository for bugs or questions

---

## Contributing

Contributions are welcome. Please follow these guidelines:

1. Fork the repository and create a feature branch from `main`
2. Follow the [Python coding conventions](.github/instructions/python.instructions.md): PEP 8, type hints, snake_case, f-strings, 88-char line limit
3. Write unit tests for all new features with descriptive test names covering edge cases
4. All public functions must include docstrings
5. Open a pull request with a clear description of what was changed and why

For significant changes, create an implementation plan in `docs/plans/` before starting work (see [.github/instructions/copilot-instructions.md](.github/instructions/copilot-instructions.md) for the plan template).

---

## Maintainers

| Name | Role |
|---|---|
| [@mbangas](https://github.com/mbangas) | Project Lead |

---

## License

This project does not yet have a license file. Contact the maintainers for usage permissions.
