"""Integration tests for the Agreement API — TMF651.

Run with: pytest src/commercial/tests/test_agreement_api.py -v

Shared ``test_engine`` and ``db_session`` fixtures are provided by ``src/conftest.py``.
An in-memory SQLite database is used; no PostgreSQL is required.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.shared.db.session import get_db
from src.shared.events.bus import EventBus

AGREEMENT_BASE = "/tmf-api/agreementManagement/v4/agreement"
QUOTE_BASE = "/tmf-api/quoteManagement/v4/quote"
INVENTORY_BASE = "/tmf-api/serviceInventory/v4/service"
CATALOG_BASE = "/tmf-api/serviceCatalogManagement/v4/serviceSpecification"


@pytest_asyncio.fixture
async def client(db_session):
    """AsyncClient with the database dependency overridden."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    EventBus.clear()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _create_accepted_quote(client) -> str:
    """Create a Quote in 'accepted' state and return its ID."""
    resp = await client.post(QUOTE_BASE, json={"name": "Accepted Quote"})
    quote_id = resp.json()["id"]
    await client.patch(f"{QUOTE_BASE}/{quote_id}", json={"state": "pending"})
    await client.patch(f"{QUOTE_BASE}/{quote_id}", json={"state": "approved"})
    await client.patch(f"{QUOTE_BASE}/{quote_id}", json={"state": "accepted"})
    return quote_id


async def _create_service(client) -> str:
    """Create a Service in inventory and return its ID."""
    resp = await client.post(INVENTORY_BASE, json={"name": "Test Service"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_agreement(client, **kwargs) -> dict:
    """Create an Agreement and return its JSON body."""
    payload = {"name": "Test Agreement", "agreement_type": "commercial"}
    payload.update(kwargs)
    resp = await client.post(AGREEMENT_BASE, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ══════════════════════════════════════════════════════════════════════════════
# List
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_agreements_empty(client):
    """GET /agreement should return an empty list when no agreements exist."""
    resp = await client.get(AGREEMENT_BASE)
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"


@pytest.mark.asyncio
async def test_list_agreements_returns_created(client):
    """GET /agreement should list previously created agreements."""
    await _create_agreement(client)
    resp = await client.get(AGREEMENT_BASE)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.headers["X-Total-Count"] == "1"


@pytest.mark.asyncio
async def test_list_agreements_filter_by_state(client):
    """GET /agreement?state=inProgress should only return matching agreements."""
    await _create_agreement(client, name="A1")
    await _create_agreement(client, name="A2")
    resp = await client.get(AGREEMENT_BASE, params={"state": "inProgress"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["state"] == "inProgress"


@pytest.mark.asyncio
async def test_list_agreements_filter_by_type(client):
    """GET /agreement?agreement_type=SLA should only return SLA agreements."""
    await _create_agreement(client, name="SLA Agr", agreement_type="SLA")
    await _create_agreement(client, name="Commercial Agr", agreement_type="commercial")
    resp = await client.get(AGREEMENT_BASE, params={"agreement_type": "SLA"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["agreement_type"] == "SLA"


# ══════════════════════════════════════════════════════════════════════════════
# Create
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_agreement_minimal_returns_201(client):
    """POST /agreement with name and type should return 201 in inProgress state."""
    resp = await client.post(
        AGREEMENT_BASE, json={"name": "SLA Agreement", "agreement_type": "SLA"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "SLA Agreement"
    assert data["state"] == "inProgress"
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_agreement_with_quote_returns_201(client):
    """POST /agreement with a valid related_quote_id should return 201."""
    quote_id = await _create_accepted_quote(client)
    resp = await client.post(
        AGREEMENT_BASE, json={"name": "Agr with Quote", "related_quote_id": quote_id}
    )
    assert resp.status_code == 201
    assert resp.json()["related_quote_id"] == quote_id


@pytest.mark.asyncio
async def test_create_agreement_invalid_quote_returns_404(client):
    """POST /agreement with a non-existent quote ID should return 404."""
    resp = await client.post(
        AGREEMENT_BASE, json={"name": "Bad Agreement", "related_quote_id": "no-such-quote"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_agreement_with_service_returns_201(client):
    """POST /agreement with a valid related_service_id should return 201."""
    service_id = await _create_service(client)
    resp = await client.post(
        AGREEMENT_BASE, json={"name": "Agr with Service", "related_service_id": service_id}
    )
    assert resp.status_code == 201
    assert resp.json()["related_service_id"] == service_id


@pytest.mark.asyncio
async def test_create_agreement_invalid_service_returns_404(client):
    """POST /agreement with a non-existent service ID should return 404."""
    resp = await client.post(
        AGREEMENT_BASE, json={"name": "Bad Service Agr", "related_service_id": "no-such-service"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_agreement_invalid_type_returns_422(client):
    """POST /agreement with an unknown agreement_type should return 422."""
    resp = await client.post(
        AGREEMENT_BASE, json={"name": "Bad Type", "agreement_type": "unknown"}
    )
    assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# Get
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_agreement_returns_200(client):
    """GET /agreement/{id} should return the agreement."""
    agr = await _create_agreement(client)
    resp = await client.get(f"{AGREEMENT_BASE}/{agr['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == agr["id"]


@pytest.mark.asyncio
async def test_get_agreement_not_found_returns_404(client):
    """GET /agreement/{id} with unknown ID should return 404."""
    resp = await client.get(f"{AGREEMENT_BASE}/no-such-id")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# State Machine — Patch
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_patch_agreement_inprogress_to_active(client):
    """PATCH state inProgress→active should succeed and set status_change_date."""
    agr = await _create_agreement(client)
    resp = await client.patch(f"{AGREEMENT_BASE}/{agr['id']}", json={"state": "active"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "active"
    assert data["status_change_date"] is not None


@pytest.mark.asyncio
async def test_patch_agreement_active_to_expired(client):
    """PATCH state active→expired should succeed."""
    agr = await _create_agreement(client)
    await client.patch(f"{AGREEMENT_BASE}/{agr['id']}", json={"state": "active"})
    resp = await client.patch(f"{AGREEMENT_BASE}/{agr['id']}", json={"state": "expired"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "expired"


@pytest.mark.asyncio
async def test_patch_agreement_active_to_terminated(client):
    """PATCH state active→terminated should succeed."""
    agr = await _create_agreement(client)
    await client.patch(f"{AGREEMENT_BASE}/{agr['id']}", json={"state": "active"})
    resp = await client.patch(f"{AGREEMENT_BASE}/{agr['id']}", json={"state": "terminated"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "terminated"


@pytest.mark.asyncio
async def test_patch_agreement_inprogress_to_cancelled(client):
    """PATCH state inProgress→cancelled should succeed."""
    agr = await _create_agreement(client)
    resp = await client.patch(f"{AGREEMENT_BASE}/{agr['id']}", json={"state": "cancelled"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "cancelled"


@pytest.mark.asyncio
async def test_patch_agreement_invalid_transition_returns_422(client):
    """PATCH state inProgress→expired is invalid; should return 422."""
    agr = await _create_agreement(client)
    resp = await client.patch(f"{AGREEMENT_BASE}/{agr['id']}", json={"state": "expired"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_agreement_terminal_state_returns_422(client):
    """PATCH state from expired (terminal) should return 422."""
    agr = await _create_agreement(client)
    await client.patch(f"{AGREEMENT_BASE}/{agr['id']}", json={"state": "active"})
    await client.patch(f"{AGREEMENT_BASE}/{agr['id']}", json={"state": "expired"})
    resp = await client.patch(f"{AGREEMENT_BASE}/{agr['id']}", json={"state": "active"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_agreement_not_found_returns_404(client):
    """PATCH /agreement/{id} with an unknown ID should return 404."""
    resp = await client.patch(f"{AGREEMENT_BASE}/no-such-id", json={"state": "active"})
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Delete
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_delete_agreement_returns_204(client):
    """DELETE /agreement/{id} should return 204 and the resource should be gone."""
    agr = await _create_agreement(client)
    resp = await client.delete(f"{AGREEMENT_BASE}/{agr['id']}")
    assert resp.status_code == 204
    get_resp = await client.get(f"{AGREEMENT_BASE}/{agr['id']}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_agreement_not_found_returns_404(client):
    """DELETE /agreement/{id} with unknown ID should return 404."""
    resp = await client.delete(f"{AGREEMENT_BASE}/no-such-id")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# SLA metrics (agreementItem)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_add_sla_to_agreement_returns_201(client):
    """POST /agreement/{id}/agreementItem should return 201 with the SLA."""
    agr = await _create_agreement(client)
    resp = await client.post(
        f"{AGREEMENT_BASE}/{agr['id']}/agreementItem",
        json={
            "name": "Availability SLA",
            "metric": "availability",
            "metric_threshold": 99.9,
            "metric_unit": "percent",
            "conformance_period": "monthly",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["metric"] == "availability"
    assert data["metric_threshold"] == 99.9
    assert data["metric_unit"] == "percent"


@pytest.mark.asyncio
async def test_list_slas_returns_all(client):
    """GET /agreement/{id}/agreementItem should return all SLA metrics."""
    agr = await _create_agreement(client)
    await client.post(
        f"{AGREEMENT_BASE}/{agr['id']}/agreementItem",
        json={"name": "Availability", "metric": "availability", "metric_threshold": 99.9},
    )
    await client.post(
        f"{AGREEMENT_BASE}/{agr['id']}/agreementItem",
        json={"name": "Latency", "metric": "latency", "metric_threshold": 10.0},
    )
    resp = await client.get(f"{AGREEMENT_BASE}/{agr['id']}/agreementItem")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_delete_sla_returns_204(client):
    """DELETE /agreement/{id}/agreementItem/{sla_id} should return 204."""
    agr = await _create_agreement(client)
    sla_resp = await client.post(
        f"{AGREEMENT_BASE}/{agr['id']}/agreementItem",
        json={"name": "Availability", "metric": "availability", "metric_threshold": 99.9},
    )
    sla_id = sla_resp.json()["id"]
    del_resp = await client.delete(f"{AGREEMENT_BASE}/{agr['id']}/agreementItem/{sla_id}")
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_add_sla_to_nonexistent_agreement_returns_404(client):
    """POST /agreement/{id}/agreementItem for unknown agreement should return 404."""
    resp = await client.post(
        f"{AGREEMENT_BASE}/no-such-agr/agreementItem",
        json={"name": "SLA", "metric": "availability", "metric_threshold": 99.9},
    )
    assert resp.status_code == 404
