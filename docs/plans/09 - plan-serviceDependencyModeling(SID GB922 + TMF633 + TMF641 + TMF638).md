# Plan: Service Dependency Modeling (SID GB922 + TMF633 + TMF641 + TMF638)

## Objective

Implement the three relationship entities that form the traceability backbone from catalog design through ordering to provisioned inventory:

- `ServiceSpecRelationship` — TMF633 / SID GB922 `ServiceSpecificationRelationship`
- `ServiceOrderItemRelationship` — TMF641 (dependency type)
- `ServiceRelationship` — TMF638 / SID GB922

None of the three exists today in any layer of the codebase. This plan covers the full vertical slice: database migration, ORM, Pydantic schemas, repositories, service logic (including propagation and provisioning gating), REST API routes, frontend UI panels, and automated tests. It also updates the README with the complete TMF reference table for the solution.

---

## Steps

### Phase A — Database Migration

**Step 1.** Create `alembic/versions/0010_service_dependencies.py` (revises `0009_characteristic_extensions`), adding three tables:

- **`service_spec_relationship`**
  - `id` String(36) PK
  - `relationship_type` String(64) NOT NULL — enum: `dependency | isContainedIn | isReplacedBy | hasPart`
  - `spec_id` FK→`service_specification.id` RESTRICT
  - `related_spec_id` FK→`service_specification.id` RESTRICT
  - `related_spec_name` String(255), `related_spec_href` String(512)
  - UNIQUE constraint on (`spec_id`, `related_spec_id`, `relationship_type`)
  - `created_at`, `updated_at`

- **`service_order_item_relationship`**
  - `id` String(36) PK
  - `relationship_type` String(64) NOT NULL
  - `order_item_orm_id` FK→`service_order_item.id` CASCADE
  - `related_item_label` String(64) — the client-assigned `order_item_id` string label (per TMF641 spec, e.g. `"1"`, `"2"`)
  - `created_at`, `updated_at`

- **`service_relationship`**
  - `id` String(36) PK
  - `relationship_type` String(64) NOT NULL
  - `service_id` FK→`service.id` CASCADE
  - `related_service_id` FK→`service.id` RESTRICT
  - `related_service_name` String(255), `related_service_href` String(512)
  - UNIQUE constraint on (`service_id`, `related_service_id`, `relationship_type`)
  - `created_at`, `updated_at`

---

### Phase B — ORM Models

**Step 2.** `src/catalog/models/orm.py`:
- Add `ServiceSpecRelationshipOrm` class (table `service_spec_relationship`), pattern mirrors `ServiceLevelSpecificationOrm`.
- Add `spec_relationships: Mapped[list[ServiceSpecRelationshipOrm]]` backref on `ServiceSpecificationOrm` with `cascade="all, delete-orphan"`, `lazy="selectin"`.

**Step 3.** `src/order/models/orm.py`:
- Add `ServiceOrderItemRelationshipOrm` class (table `service_order_item_relationship`).
- Add `item_relationships: Mapped[list[ServiceOrderItemRelationshipOrm]]` backref on `ServiceOrderItemOrm` with `cascade="all, delete-orphan"`, `lazy="selectin"`.

**Step 4.** `src/inventory/models/orm.py`:
- Add `ServiceRelationshipOrm` class (table `service_relationship`).
- Add `service_relationships: Mapped[list[ServiceRelationshipOrm]]` backref on `ServiceOrm` with `cascade="all, delete-orphan"`, `lazy="selectin"`.

---

### Phase C — Pydantic Schemas

**Step 5.** `src/catalog/models/schemas.py`:
- Add `ServiceSpecRelationshipCreate` (fields: `relationship_type`, `related_spec_id`, `related_spec_name`, `related_spec_href`).
- Add `ServiceSpecRelationshipResponse` (adds `id`, `spec_id`, `created_at`, `updated_at`; `model_config = ConfigDict(from_attributes=True)`).
- Add `spec_relationships: list[ServiceSpecRelationshipResponse]` to `ServiceSpecificationResponse`.

**Step 6.** `src/order/models/schemas.py`:
- Add `ServiceOrderItemRelationshipCreate` (fields: `relationship_type`, `related_item_label`).
- Add `ServiceOrderItemRelationshipResponse`.
- Add `item_relationships: list[ServiceOrderItemRelationshipResponse]` to `ServiceOrderItemResponse`.

**Step 7.** `src/inventory/models/schemas.py`:
- Add `ServiceRelationshipCreate` (fields: `relationship_type`, `related_service_id`, `related_service_name`, `related_service_href`).
- Add `ServiceRelationshipResponse`.
- Add `service_relationships: list[ServiceRelationshipResponse]` to `ServiceResponse`.

---

### Phase D — Repositories

*(Steps 8–10 are independent and can be implemented in parallel.)*

**Step 8.** New `src/catalog/repositories/spec_relationship_repo.py`:
- Methods: `list_by_spec(spec_id)`, `create(spec_id, data)`, `get(rel_id)`, `delete(rel_id)`.
- Pattern follows `src/catalog/repositories/service_spec_repo.py`.

**Step 9.** New `src/order/repositories/order_item_relationship_repo.py`:
- Methods: `list_by_item(order_item_orm_id)`, `create(order_item_orm_id, data)`, `get(rel_id)`, `delete(rel_id)`.

**Step 10.** New `src/inventory/repositories/service_relationship_repo.py`:
- Methods: `list_by_service(service_id)`, `create(service_id, data)`, `get(rel_id)`, `delete(rel_id)`.

---

### Phase E — Service Logic

**Step 11.** `src/catalog/services/catalog_service.py`:
- Add `add_spec_relationship(spec_id, data)` — validate no self-reference, no duplicate triple, then persist.
- Add `list_spec_relationships(spec_id)`.
- Add `delete_spec_relationship(spec_id, rel_id)`.
- Optional: depth-limited cycle check (DFS ≤ 10 hops) for `relationship_type = "dependency"` to prevent circular CFS→RFS chains.

**Step 12.** `src/order/services/order_service.py`:
- Add `add_order_item_relationship(order_id, item_id, data)` — validate `related_item_label` references a real `order_item_id` within the same order, reject self-reference.
- Add `list_order_item_relationships(order_id, item_id)`.
- Add `delete_order_item_relationship(order_id, item_id, rel_id)`.

**Step 13.** `src/inventory/services/inventory_service.py`:
- Add `add_service_relationship(service_id, data)`, `list_service_relationships(service_id)`, `delete_service_relationship(service_id, rel_id)`.

**Step 14 — Dependency Propagation.**  
Extend the order-completion handler in `src/inventory/services/inventory_service.py` (the function that creates `ServiceOrm` entries when an order reaches `completed`):
- After all `ServiceOrm` instances are created, read `ServiceSpecRelationship` entries for each spec.
- Map `related_spec_id` → the newly created `ServiceOrm` instance for that spec.
- Insert `ServiceRelationship` rows accordingly.
- This ensures inventory automatically mirrors the catalog dependency topology without manual operator input.

**Step 15 — Provisioning Gating.**  
Extend `src/provisioning/services/provisioning_service.py` job dispatch logic:
- Before dispatching a `ServiceActivationJob` for an order item, check `ServiceOrderItemRelationship` for `relationship_type = "dependency"`.
- If a dependency exists, query sibling order items by `related_item_label` within the same order.
- Only dispatch the job when all referenced predecessor items have reached state `completed`.
- Items that are held emit a `blocked_on` field in the job response for observability.

---

### Phase F — API Routes

**Step 16.** New `src/catalog/api/spec_relationship_router.py`:
```
GET    /tmf-api/serviceCatalogManagement/v4/serviceSpecification/{spec_id}/serviceSpecRelationship
POST   /tmf-api/serviceCatalogManagement/v4/serviceSpecification/{spec_id}/serviceSpecRelationship
DELETE /tmf-api/serviceCatalogManagement/v4/serviceSpecification/{spec_id}/serviceSpecRelationship/{rel_id}
```

**Step 17.** New `src/order/api/order_item_relationship_router.py`:
```
GET    /tmf-api/serviceOrderManagement/v4/serviceOrder/{order_id}/serviceOrderItem/{item_id}/serviceOrderItemRelationship
POST   /tmf-api/serviceOrderManagement/v4/serviceOrder/{order_id}/serviceOrderItem/{item_id}/serviceOrderItemRelationship
DELETE /tmf-api/serviceOrderManagement/v4/serviceOrder/{order_id}/serviceOrderItem/{item_id}/serviceOrderItemRelationship/{rel_id}
```

**Step 18.** New `src/inventory/api/service_relationship_router.py`:
```
GET    /tmf-api/serviceInventoryManagement/v4/service/{service_id}/serviceRelationship
POST   /tmf-api/serviceInventoryManagement/v4/service/{service_id}/serviceRelationship
DELETE /tmf-api/serviceInventoryManagement/v4/service/{service_id}/serviceRelationship/{rel_id}
```

**Step 19.** Register all three new routers in `src/main.py`.

---

### Phase G — Frontend

**Step 20.** `frontend/js/api-client.js` — add three new API method groups:
- `specRelationships.list(specId)`, `.create(specId, body)`, `.delete(specId, relId)`
- `orderItemRelationships.list(orderId, itemId)`, `.create(...)`, `.delete(...)`
- `serviceRelationships.list(serviceId)`, `.create(serviceId, body)`, `.delete(serviceId, relId)`

**Step 21.** `frontend/catalog.html` — add "Dependencies" tab to the ServiceSpec detail panel:
- Render fetched relationships as a tree with type badge (dependency | isContainedIn | isReplacedBy | hasPart).
- "Add Dependency" form: dropdown of existing specs + type selector + submit.
- Delete button per relationship row.

**Step 22.** `frontend/orders.html` — add "Item Dependencies" section under each order item:
- Display dependency list showing predecessor label → current item label.
- Allow linking items within the same order via a small form.

**Step 23.** `frontend/inventory.html` — add "Service Relationships" section on service detail view:
- Show CFS→RFS tree with type labels.
- Read-only for auto-propagated entries; allow manual additions.

**Step 24.** `frontend/provisioning.html` — add dependency indicator on job queue rows:
- Blocked items display a "⏳ waiting for item {label}" badge.
- Unblocked items show a normal dispatch button.

---

### Phase H — Tests

*(Steps 25–27 are independent and can be run in parallel.)*

**Step 25.** New `src/catalog/tests/test_spec_relationship_api.py`:
- CRUD happy path (create, list, delete).
- Self-reference rejected (422).
- Duplicate triple rejected (409).
- Non-existent `related_spec_id` rejected (404/422).

**Step 26.** New `src/order/tests/test_order_item_relationship_api.py`:
- CRUD happy path.
- Invalid `related_item_label` (not in same order) rejected (422).
- Self-reference rejected.

**Step 27.** New `src/inventory/tests/test_service_relationship_api.py`:
- CRUD happy path.
- Cascade delete verified (deleting service removes its relationships).
- RESTRICT verified (cannot delete a service that is a `related_service_id` elsewhere).

**Step 28.** Extend `src/inventory/tests/` order-completion test:
- Assert auto-propagated `ServiceRelationship` rows appear when order transitions to `completed` and specs had `ServiceSpecRelationship` entries.

**Step 29.** Extend `src/provisioning/tests/` provisioning test:
- Assert a dependency-gated job is NOT dispatched while predecessor item is `inProgress`.
- Assert job IS dispatched after predecessor reaches `completed`.

---

### Phase I — README Update

**Step 30.** `README.md` — update the domain table and add a complete TMF reference table covering all implemented and planned endpoints:

| Domain | SID Entity | TMF API | Endpoint Pattern | Status |
|---|---|---|---|---|
| Service Design | ServiceSpecification | TMF633 | `/serviceSpecification` | ✅ Implemented |
| Service Design | **ServiceSpecRelationship** | **TMF633** | `/serviceSpecification/{id}/serviceSpecRelationship` | **🔧 Phase 9** |
| Service Design | ServiceSpecCharacteristic | TMF633 | `/serviceSpecification/{id}/serviceSpecCharacteristic` | ✅ Implemented |
| Service Design | CharacteristicValueSpecification | TMF633 / TMFC006 | `/serviceSpecCharacteristic/{id}/characteristicValueSpecification` | ✅ Implemented |
| Service Design | ServiceLevelSpecification | TMF633 | `/serviceSpecification/{id}/serviceLevelSpecification` | ✅ Implemented |
| Service Design | ServiceCategory | TMF633 | `/serviceCategory` | ✅ Implemented |
| Service Design | ServiceCandidate | TMF633 | `/serviceCandidate` | ✅ Implemented |
| Service Design | ServiceCatalog | TMF633 | `/serviceCatalog` | ✅ Implemented |
| Pre-Sales | ServiceQualification | TMF645 | `/serviceQualification` | ✅ Implemented |
| Order Management | ServiceOrder + ServiceOrderItem | TMF641 | `/serviceOrder` | ✅ Implemented |
| Order Management | **ServiceOrderItemRelationship** | **TMF641** | `/serviceOrder/{id}/serviceOrderItem/{id}/serviceOrderItemRelationship` | **🔧 Phase 9** |
| Inventory | Service + ServiceCharacteristic | TMF638 | `/service` | ✅ Implemented |
| Inventory | CharacteristicValue | TMF638 / TMFC006 | `/service/{id}/serviceCharacteristic/{id}/characteristicValue` | ✅ Implemented |
| Inventory | **ServiceRelationship** | **TMF638** | `/service/{id}/serviceRelationship` | **🔧 Phase 9** |
| Provisioning | ServiceActivationJob | TMF640 | `/serviceActivationJob` | ✅ Implemented |
| Assurance | Alarm | TMF642 | `/alarm` | ✅ Implemented |
| Assurance | PerformanceMeasurement | TMF628 | `/performanceMeasurement` | ✅ Implemented |
| Assurance | ServiceLevelObjective | TMF657 | `/serviceLevelObjective` | ✅ Implemented |
| Testing | ServiceTest + TestResult | TMF653 | `/serviceTest` | ✅ Implemented |
| Problem Mgmt | TroubleTicket | TMF621 | `/troubleTicket` | 📋 Phase 10 |
| Problem Mgmt | ServiceProblem | TMF656 | `/serviceProblem` | 📋 Phase 10 |
| Commercial | Quote + QuoteItem | TMF648 | `/quote` | 📋 Phase 11 |
| Commercial | Agreement + ServiceLevelAgreement | TMF651 | `/agreement` | 📋 Phase 11 |

---

## Timeline

| Step(s) | Work | Estimate |
|---|---|---|
| 1 | Alembic migration 0010 | 0.5 day |
| 2–4 | ORM models (3 files) | 0.5 day |
| 5–7 | Pydantic schemas (3 files) | 0.5 day |
| 8–10 | Repositories (3 new files, parallel) | 1 day |
| 11–13 | Service CRUD methods (3 files) | 1 day |
| 14 | Dependency propagation (inventory service) | 0.5 day |
| 15 | Provisioning gating logic | 1 day |
| 16–19 | API routes + main.py registration | 1 day |
| 20–24 | Frontend (4 pages + api-client.js) | 2 days |
| 25–29 | Tests (5 test files / extensions) | 1.5 days |
| 30 | README update | 0.5 day |
| **Total** | | **~10 days** |

---

## Resources

- TMF633 Service Catalog Management API v4 specification
- TMF641 Service Order Management API v4 specification
- TMF638 Service Inventory Management API v4 specification
- SID GB922 `ServiceSpecificationRelationship`, `ServiceRelationship` entity definitions
- Existing `src/catalog/repositories/service_spec_repo.py` — repository pattern reference
- Existing `src/catalog/api/router.py` — router pattern reference
- Existing `alembic/versions/0009_characteristic_extensions.py` — migration pattern reference
- Existing `src/inventory/services/inventory_service.py` — order-completion handler to extend
- Existing `src/provisioning/services/provisioning_service.py` — provisioning dispatch to extend

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Circular dependency chains (A→B→C→A) cause infinite loops during propagation | Medium | High | Add depth-limited DFS cycle check (≤10 hops) in `add_spec_relationship` for `dependency` type before persisting |
| RESTRICT FK on `related_service_id` blocks service deletion unexpectedly | Medium | Medium | Surface clear 409 Conflict error with message identifying blocking relationships; document in API |
| Provisioning gating introduces deadlock (two items each waiting on the other) | Low | High | Validate at order-item relationship creation that no cycle exists within the same order |
| Auto-propagation creates stale relationships if spec dependencies change post-order | Low | Low | Propagation is a one-time snapshot at order completion; document that inventory relationships are not kept in sync with catalog changes |
| Frontend tree rendering performance with very large spec graphs | Low | Low | Cap tree depth to 5 levels in UI; paginate relationship lists |
| Migration 0010 FK conflicts if existing data violates new constraints | Very Low | Medium | RESTRICT FKs only apply to new inserts; existing rows are unaffected; migration is additive only |

---

## Key Design Decisions

- **Self-reference guard**: A spec/service cannot reference itself as a related entity. Validated at the service layer → 422 Unprocessable Entity.
- **Duplicate guard**: The triple `(spec_id, related_spec_id, relationship_type)` must be unique. Enforced by a DB UNIQUE constraint and a service-layer pre-check returning 409 Conflict.
- **TMF641 label model**: `ServiceOrderItemRelationship.related_item_label` stores the client-assigned `order_item_id` string (e.g. `"1"`, `"2"`), not the DB UUID. This follows the TMF641 spec commentary that items reference each other by their label, not internal pk. The service layer resolves the label to the ORM id for validation.
- **Propagation model**: Inventory `ServiceRelationship` entries are a point-in-time snapshot created at order completion. They are not retroactively updated if the catalog's `ServiceSpecRelationship` changes afterwards.
- **Cascade policy**: `service_relationship.service_id` → CASCADE (deleting a service removes its relationships); `service_relationship.related_service_id` → RESTRICT (prevents deleting a service that others depend on).
- **SID `@type` annotation**: The `type` field on relationship responses carries `"ServiceSpecificationRelationship"` / `"ServiceRelationship"` to satisfy SID GB922 conformance while the REST path follows TMF633/TMF638 naming.
- **Out of scope for this phase**: cross-order dependencies, bi-directional relationship enforcement, TMF notification events for relationship changes, Resource-level dependency tracing (TMF634/TMF639).
