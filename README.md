# TMF Service Layer

> A modular implementation of the **TM Forum Open Digital Architecture (ODA) Service Layer**, built on TMF Open APIs and the Shared Information/Data (SID) model.

---

## What the Project Does

The **TMF Service Layer** is the core domain of the TM Forum ODA responsible for managing the full service lifecycle — from catalog design through ordering, provisioning, assurance, and testing. It bridges the **Product/Customer domain** and the **Resource/Network domain**, ensuring that Customer Facing Services (CFS) are correctly provisioned, monitored, and maintained via underlying Resource Facing Services (RFS).

This application implements the following functional domains:

| Domain | Key Capability | TMF API | Status |
|---|---|---|---|
| Service Design | Service catalog, specifications, SLA | TMF633 | ✅ Implemented |
| Pre-Sales | Service qualification and availability checks | TMF645 | 🔄 Planned |
| Order Management | Full service order lifecycle management | TMF641 | 🔄 Planned |
| Provisioning | Service activation and configuration | TMF640 | 🔄 Planned |
| Inventory | Active service instances and relationships | TMF638 | 🔄 Planned |
| Assurance | Alarms, performance, SLA management | TMF628, TMF642, TMF657 | 🔄 Planned |
| Testing | Automated service test and validation | TMF653 | 🔄 Planned |
| Problem Management | Incidents, trouble tickets, root cause | TMF621, TMF656 | 🔄 Planned |
| Commercial Support | Quotes, agreements, SLAs | TMF648, TMF651 | 🔄 Planned |

For the full mapping of ODA components → TMF APIs → SID entities, see [docs/TMF-reference.md](docs/TMF-reference.md).

### Service Catalog Design & Management (TMF633) ✅

The **Service Catalog** module is the first implemented component. It provides the foundation for all other domains by defining service templates before any order, provisioning, or assurance flow begins.

**What is covered:**
- `ServiceSpecification` — define and version service templates (CFS and RFS)
- `ServiceSpecCharacteristic` — configure parameters such as speed, QoS, or technology type
- `ServiceLevelSpecification` — attach SLA constraints to service definitions
- `ServiceSpecRelationship` — model CFS → RFS hierarchies
- Lifecycle management: `active` → `retired` → `obsolete`

> See the [Implemented Modules](#implemented-modules) section for API endpoints, module structure, and a usage example.

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
| `ServiceSpecCharacteristicValue` | Allowed values for a given characteristic |
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
