"""Integration tests for the TMF638 Service Inventory Management API.

Run with: pytest src/inventory/tests/test_inventory_api.py -v

These tests use an in-memory SQLite database (via aiosqlite) so no PostgreSQL
is required to run them locally.

Shared ``test_engine`` and ``db_session`` fixtures are provided by
``src/conftest.py``.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.shared.db.session import get_db
from src.shared.events.bus import EventBus

BASE = "/tmf-api/serviceInventory/v4/service"


@pytest_asyncio.fixture
async def client(db_session):
    """Return an AsyncClient with the database dependency overridden."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    EventBus.clear()


# ── Helper ─────────────────────────────────────────────────────────────────────

async def create_svc(client, *, name="Test Service", state="inactive", **kwargs):
    """Create a Service instance and return the parsed JSON body."""
    payload = {"name": name, "state": state, **kwargs}
    response = await client.post(BASE, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# ── POST / ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_service_returns_201(client):
    """POST should return 201 with the created resource."""
    payload = {
        "name": "Broadband Internet — Customer A",
        "description": "1Gbps residential broadband",
        "service_type": "CFS",
        "state": "inactive",
    }
    response = await client.post(BASE, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Broadband Internet — Customer A"
    assert data["state"] == "inactive"
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_service_missing_name_returns_422(client):
    """POST without a name should return 422."""
    response = await client.post(BASE, json={"description": "No name"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_service_terminated_initial_state_returns_422(client):
    """POST with initial state 'terminated' must return 422."""
    response = await client.post(BASE, json={"name": "Bad", "state": "terminated"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_service_with_characteristics(client):
    """POST with nested characteristics should persist and return them."""
    payload = {
        "name": "VoIP Service",
        "state": "inactive",
        "service_characteristic": [
            {"name": "codec", "value": "G.711", "value_type": "string"},
            {"name": "jitter_ms", "value": "20", "value_type": "integer"},
        ],
    }
    response = await client.post(BASE, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert len(data["service_characteristic"]) == 2
    names = {c["name"] for c in data["service_characteristic"]}
    assert "codec" in names
    assert "jitter_ms" in names


# ── GET / ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_services_returns_200_with_pagination_headers(client):
    """GET / should return 200 with X-Total-Count and X-Result-Count headers."""
    await create_svc(client, name="Service 1")
    await create_svc(client, name="Service 2")

    response = await client.get(BASE)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert int(response.headers["X-Total-Count"]) >= 2
    assert int(response.headers["X-Result-Count"]) == len(data)


@pytest.mark.asyncio
async def test_list_services_state_filter(client):
    """GET /?state=active should return only active services."""
    await create_svc(client, name="Active Svc", state="active")
    await create_svc(client, name="Inactive Svc", state="inactive")

    response = await client.get(BASE, params={"state": "active"})
    assert response.status_code == 200
    data = response.json()
    assert all(s["state"] == "active" for s in data)


# ── GET /{id} ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_service_by_id_returns_200(client):
    """GET /{id} should return 200 with the matching service."""
    created = await create_svc(client, name="My VPN")
    response = await client.get(f"{BASE}/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_service_not_found_returns_404(client):
    """GET /{id} with an unknown ID should return 404."""
    response = await client.get(f"{BASE}/no-such-id")
    assert response.status_code == 404


# ── PATCH /{id} ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_service_valid_transition(client):
    """PATCH /{id} with valid state inactive→active should return 200."""
    svc = await create_svc(client, state="inactive")
    response = await client.patch(f"{BASE}/{svc['id']}", json={"state": "active"})
    assert response.status_code == 200
    assert response.json()["state"] == "active"


@pytest.mark.asyncio
async def test_patch_service_invalid_transition_returns_422(client):
    """PATCH /{id} with an invalid state transition must return 422."""
    svc = await create_svc(client, state="inactive")
    response = await client.patch(f"{BASE}/{svc['id']}", json={"state": "terminated"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_service_not_found_returns_404(client):
    """PATCH on an unknown ID should return 404."""
    response = await client.patch(f"{BASE}/no-such-id", json={"state": "active"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_service_name_only(client):
    """PATCH /{id} with only name should update the name without changing state."""
    svc = await create_svc(client, name="Old Name", state="inactive")
    response = await client.patch(f"{BASE}/{svc['id']}", json={"name": "New Name"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["state"] == "inactive"


# ── DELETE /{id} ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_terminated_service_returns_204(client):
    """DELETE a terminated service should return 204 and be gone."""
    svc = await create_svc(client, state="inactive")
    # inactive → active → terminated
    await client.patch(f"{BASE}/{svc['id']}", json={"state": "active"})
    await client.patch(f"{BASE}/{svc['id']}", json={"state": "terminated"})

    response = await client.delete(f"{BASE}/{svc['id']}")
    assert response.status_code == 204

    # Confirm it's gone
    get_response = await client.get(f"{BASE}/{svc['id']}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_inactive_service_returns_204(client):
    """DELETE an inactive service should also return 204."""
    svc = await create_svc(client, state="inactive")
    response = await client.delete(f"{BASE}/{svc['id']}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_active_service_returns_422(client):
    """DELETE an active service must return 422."""
    svc = await create_svc(client, state="active")
    response = await client.delete(f"{BASE}/{svc['id']}")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_service_not_found_returns_404(client):
    """DELETE on an unknown ID should return 404."""
    response = await client.delete(f"{BASE}/no-such-id")
    assert response.status_code == 404
