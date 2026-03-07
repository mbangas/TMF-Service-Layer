# Plan: Characteristic Management — TMF633 / TMF638

**Implementar a gestão completa de Characteristic, CharacteristicSpecification, CharacteristicValueSpecification e CharacteristicValue**, expandindo os domínios de Catalog (TMF633) e Inventory (TMF638) com entidades novas, endpoints standalone, frontend e testes.

---

### Estado Atual

| Entidade | Dom. | ORM | Schema | API Standalone |
|---|---|---|---|---|
| `ServiceSpecCharacteristic` | Catalog | ✅ (embedded) | ✅ (embedded) | ❌ |
| `CharacteristicValueSpecification` | Catalog | ❌ | ❌ | ❌ |
| `ServiceCharacteristic` | Inventory | ✅ (embedded) | ✅ (embedded) | ❌ |
| `CharacteristicValue` | Inventory | ❌ | ❌ | ❌ |

---

### Phase 1 — Catalog Backend (TMF633)
*Todos os steps podem ser executados em sequência dentro desta fase.*

1. **ORM — Novo modelo `CharacteristicValueSpecificationOrm`** em `src/catalog/models/orm.py`:
   - Campos: `id`, `value_type`, `value`, `value_from`, `value_to`, `range_interval`, `regex`, `unit_of_measure`, `is_default`, `char_spec_id` (FK → `service_spec_characteristic.id` CASCADE)
   - Adicionar relationship `characteristic_value_specification` no `ServiceSpecCharacteristicOrm` (back_populates, `lazy="selectin"`, cascade all/delete-orphan)

2. **Schemas — Pydantic** em `src/catalog/models/schemas.py`:
   - Novos: `CharacteristicValueSpecCreate`, `CharacteristicValueSpecResponse`
   - Atualizar `ServiceSpecCharacteristicCreate` para aceitar `characteristic_value_specification: list[CharacteristicValueSpecCreate]`
   - Atualizar `ServiceSpecCharacteristicResponse` para incluir `characteristic_value_specification: list[CharacteristicValueSpecResponse]`

3. **Repository** — Criar `src/catalog/repositories/characteristic_repo.py`:
   - `CharacteristicSpecRepository` com métodos: `get_all_by_spec_id`, `get_by_id`, `create`, `update`, `patch`, `delete`
   - `CharacteristicValueSpecRepository` com métodos: `get_all_by_char_id`, `get_by_id`, `create`, `delete`
   - Padrão: async, SQLAlchemy `AsyncSession`, igual a `src/catalog/repositories/service_spec_repo.py`

4. **Service** — Criar `src/catalog/services/characteristic_service.py`:
   - `CharacteristicSpecService` — orquestra repo, mapeia ORM → Response
   - `CharacteristicValueSpecService`

5. **Router** — Criar `src/catalog/api/characteristic_router.py`:
   - Prefix: `/tmf-api/serviceCatalogManagement/v4/serviceSpecification/{spec_id}/serviceSpecCharacteristic`
   - `GET /` — lista características da spec (com `X-Total-Count`)
   - `POST /` — cria característica
   - `GET /{char_id}` — obtém característica
   - `PATCH /{char_id}` / `PUT /{char_id}` / `DELETE /{char_id}`
   - Sub-recurso: `GET /{char_id}/characteristicValueSpecification`
   - Sub-recurso: `POST /{char_id}/characteristicValueSpecification`
   - Sub-recurso: `GET /{char_id}/characteristicValueSpecification/{vs_id}` / `DELETE /{vs_id}`

6. **Registar router** em `src/main.py` — seguir padrão dos routers existentes

---

### Phase 2 — Inventory Backend (TMF638)
*Depende de Phase 1 ser concluída (migration partilhada). Steps internos paralelos.*

7. **ORM — Novo modelo `CharacteristicValueOrm`** em `src/inventory/models/orm.py`:
   - Campos: `id`, `value`, `value_type`, `alias`, `unit_of_measure`, `char_id` (FK → `service_characteristic.id` CASCADE)
   - Adicionar relationship `characteristic_value` no `ServiceCharacteristicOrm`

8. **Schemas** em `src/inventory/models/schemas.py`:
   - Novos: `CharacteristicValueCreate`, `CharacteristicValueResponse`
   - Atualizar `ServiceCharacteristicCreate` e `ServiceCharacteristicResponse` para incluir lista de `CharacteristicValue`

9. **Repository** — Criar `src/inventory/repositories/characteristic_repo.py`:
   - `ServiceCharacteristicRepository` — standalone CRUD por `service_id`
   - `CharacteristicValueRepository` — CRUD por `char_id`

10. **Service** — Criar `src/inventory/services/characteristic_service.py`

11. **Router** — Criar `src/inventory/api/characteristic_router.py`:
    - Prefix: `/tmf-api/serviceInventory/v4/service/{service_id}/serviceCharacteristic`
    - CRUD completo + sub-recurso `characteristicValue`

12. **Registar router** em `src/main.py`

---

### Phase 3 — Database Migration
*Depende de Phase 1 e 2 (modelos ORM finalizados).*

13. **Nova migração `alembic/versions/0009_characteristic_extensions.py`**:
    - `down_revision = "0008_catalog_tmfc006"`
    - Criar tabela `characteristic_value_specification`:
      - `id`, `value_type`, `value`, `value_from`, `value_to`, `range_interval`, `regex`, `unit_of_measure`, `is_default`, `char_spec_id` (FK → `service_spec_characteristic.id` CASCADE), timestamps
      - Índice em `char_spec_id`
    - Criar tabela `characteristic_value`:
      - `id`, `value`, `value_type`, `alias`, `unit_of_measure`, `char_id` (FK → `service_characteristic.id` CASCADE), timestamps
      - Índice em `char_id`

---

### Phase 4 — Frontend
*Paralela com Phases 1-3 conceptualmente; depende dos endpoints para testes manuais.*

14. **`frontend/catalog.html`** — Adicionar tab "Characteristics":
    - Selector de ServiceSpecification (dropdown populado por API)
    - Tabela listando `ServiceSpecCharacteristic` da spec selecionada
    - Botão "Add Characteristic" → modal com campos: `name`, `description`, `value_type`, `is_unique`, `min_cardinality`, `max_cardinality`, `extensible`
    - Sub-panel por characteristic: listar e adicionar `CharacteristicValueSpecification`
    - Padrão visual: igual aos tabs existentes (Specifications, Catalogs, Categories, Candidates)

15. **`frontend/inventory.html`** — Adicionar secção Characteristics no detalhe de Service:
    - Tabela inline de `ServiceCharacteristic` ao expandir um serviço
    - Botão "Add Characteristic" → modal com campos: `name`, `value`, `value_type`
    - Sub-panel por characteristic: listar e adicionar `CharacteristicValue`

16. **`frontend/js/api-client.js`** — Novos métodos:
    - `CharacteristicSpecClient`: `listBySpec(specId)`, `create(specId, data)`, `update(specId, charId, data)`, `delete(specId, charId)`
    - `CharacteristicValueSpecClient`: `listByChar(specId, charId)`, `create(specId, charId, data)`, `delete(specId, charId, vsId)`
    - `ServiceCharacteristicClient`: `listByService(serviceId)`, `create(serviceId, data)`, `delete(serviceId, charId)`
    - `CharacteristicValueClient`: `listByChar(serviceId, charId)`, `create(serviceId, charId, data)`, `delete(serviceId, charId, valId)`

---

### Phase 5 — Tests
*Depende das Phases 1-3.*

17. **`src/catalog/tests/test_characteristic_api.py`** — Padrão como `src/catalog/tests/test_catalog_api.py`:
    - Criar spec → criar characteristic → listar → PATCH → DELETE
    - Criar characteristic → criar CharacteristicValueSpec → listar → DELETE
    - Validação de erros (404, 422)

18. **`src/inventory/tests/test_characteristic_api.py`**:
    - Criar service → criar characteristic → listar → PATCH → DELETE
    - Criar characteristic → criar CharacteristicValue → listar → DELETE

---

### Phase 6 — Documentação
19. Guardar o plano em `docs/plans/09 - plan-characteristic-management.md`

---

### Relevant Files

| Ficheiro | Ação |
|---|---|
| `src/catalog/models/orm.py` | Adicionar `CharacteristicValueSpecificationOrm` + relationship |
| `src/catalog/models/schemas.py` | Novos schemas + atualizar existentes |
| `src/inventory/models/orm.py` | Adicionar `CharacteristicValueOrm` + relationship |
| `src/inventory/models/schemas.py` | Novos schemas + atualizar existentes |
| `alembic/versions/` | `0009_characteristic_extensions.py` (novo) |
| `src/catalog/repositories/service_spec_repo.py` | Referência de padrão |
| `src/main.py` | Registar 2 novos routers |
| `frontend/catalog.html` | Novo tab Characteristics |
| `frontend/inventory.html` | Secção Characteristics |
| `frontend/js/api-client.js` | 4 novos clientes API |

---

### Verification
1. `docker-compose up` → migração `0009` aplica sem erros
2. `POST /tmf-api/serviceCatalogManagement/v4/serviceSpecification/{id}/serviceSpecCharacteristic` → retorna 201 com `id`
3. `POST /{char_id}/characteristicValueSpecification` → retorna 201
4. `GET /serviceSpecification/{id}` → inclui lista de `service_spec_characteristic` com `characteristic_value_specification` aninhado
5. Mesmos testes para inventory domain
6. UI: tab "Characteristics" no catalog.html funciona; características aparecem no inventory.html
7. `pytest src/catalog/tests/test_characteristic_api.py` e `pytest src/inventory/tests/test_characteristic_api.py` — todos verdes

---

### Decisions
- **`CharacteristicValueSpecification`** é filho de `ServiceSpecCharacteristic` (Catalog/TMF633) — descreve os valores **permitidos** numa spec
- **`CharacteristicValue`** é filho de `ServiceCharacteristic` (Inventory/TMF638) — representa o valor **real** numa instância de serviço
- Endpoints seguem estrutura sub-recurso REST (nested under parent ID) para conformidade TMF
- Não altera o comportamento atual de embeds no `ServiceSpecification` ou `Service` para retrocompatibilidade
- Scope **excluído**: CharacteristicRelationship, CharacteristicSpecRelationship (TMF extras não pedidos)
