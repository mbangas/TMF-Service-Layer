"""Integration tests for the Quote API — TMF648.

Run with: pytest src/commercial/tests/test_quote_api.py -v

Shared ``test_engine`` and ``db_session`` fixtures are provided by ``src/conftest.py``.
An in-memory SQLite database is used; no PostgreSQL is required.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.shared.db.session import get_db
from src.shared.events.bus import EventBus

QUOTE_BASE = "/tmf-api/quoteManagement/v4/quote"
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

async def _create_spec(client) -> str:
    """Create a ServiceSpecification and return its ID."""
    resp = await client.post(CATALOG_BASE, json={"name": "Test Spec"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_quote(client, **kwargs) -> dict:
    """Create a Quote and return its JSON body."""
    payload = {"name": "Test Quote"}
    payload.update(kwargs)
    resp = await client.post(QUOTE_BASE, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ══════════════════════════════════════════════════════════════════════════════
# List
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_quotes_empty(client):
    """GET /quote should return an empty list when no quotes exist."""
    resp = await client.get(QUOTE_BASE)
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"


@pytest.mark.asyncio
async def test_list_quotes_returns_created(client):
    """GET /quote should list previously created quotes."""
    await _create_quote(client)
    resp = await client.get(QUOTE_BASE)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert resp.headers["X-Total-Count"] == "1"


@pytest.mark.asyncio
async def test_list_quotes_filter_by_state(client):
    """GET /quote?state=inProgress should only return inProgress quotes."""
    await _create_quote(client, name="Q1")
    await _create_quote(client, name="Q2")
    resp = await client.get(QUOTE_BASE, params={"state": "inProgress"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["state"] == "inProgress"


@pytest.mark.asyncio
async def test_list_quotes_filter_by_category(client):
    """GET /quote?category=enterprise should only return matching quotes."""
    await _create_quote(client, name="Enterprise Q", category="enterprise")
    await _create_quote(client, name="Residential Q", category="residential")
    resp = await client.get(QUOTE_BASE, params={"category": "enterprise"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["category"] == "enterprise"


# ══════════════════════════════════════════════════════════════════════════════
# Create
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_quote_minimal_returns_201(client):
    """POST /quote with only name should return 201 in inProgress state."""
    resp = await client.post(QUOTE_BASE, json={"name": "Enterprise Fiber"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Enterprise Fiber"
    assert data["state"] == "inProgress"
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_quote_with_spec_returns_201(client):
    """POST /quote with a valid related_service_spec_id should return 201."""
    spec_id = await _create_spec(client)
    resp = await client.post(QUOTE_BASE, json={"name": "Spec Quote", "related_service_spec_id": spec_id})
    assert resp.status_code == 201
    assert resp.json()["related_service_spec_id"] == spec_id


@pytest.mark.asyncio
async def test_create_quote_invalid_spec_returns_404(client):
    """POST /quote with a non-existent spec ID should return 404."""
    resp = await client.post(QUOTE_BASE, json={"name": "Bad Quote", "related_service_spec_id": "no-such-id"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_quote_with_category(client):
    """POST /quote with category should persist the field."""
    resp = await client.post(QUOTE_BASE, json={"name": "Cat Quote", "category": "enterprise"})
    assert resp.status_code == 201
    assert resp.json()["category"] == "enterprise"


# ══════════════════════════════════════════════════════════════════════════════
# Get
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_quote_returns_200(client):
    """GET /quote/{id} should return the quote."""
    quote = await _create_quote(client)
    resp = await client.get(f"{QUOTE_BASE}/{quote['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == quote["id"]


@pytest.mark.asyncio
async def test_get_quote_not_found_returns_404(client):
    """GET /quote/{id} with unknown ID should return 404."""
    resp = await client.get(f"{QUOTE_BASE}/no-such-id")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# State Machine — Patch
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_patch_quote_inprogress_to_pending(client):
    """PATCH state inProgress→pending should succeed."""
    quote = await _create_quote(client)
    resp = await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "pending"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "pending"


@pytest.mark.asyncio
async def test_patch_quote_pending_to_approved(client):
    """PATCH state pending→approved should succeed."""
    quote = await _create_quote(client)
    await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "pending"})
    resp = await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "approved"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "approved"


@pytest.mark.asyncio
async def test_patch_quote_approved_to_accepted_sets_completion_date(client):
    """PATCH state approved→accepted should succeed and auto-set completion_date."""
    quote = await _create_quote(client)
    await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "pending"})
    await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "approved"})
    resp = await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "accepted"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "accepted"
    assert data["completion_date"] is not None


@pytest.mark.asyncio
async def test_patch_quote_pending_to_rejected_sets_completion_date(client):
    """PATCH state pending→rejected should auto-set completion_date."""
    quote = await _create_quote(client)
    await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "pending"})
    resp = await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "rejected"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "rejected"
    assert data["completion_date"] is not None


@pytest.mark.asyncio
async def test_patch_quote_invalid_transition_returns_422(client):
    """PATCH state inProgress→accepted is not a valid transition; should return 422."""
    quote = await _create_quote(client)
    resp = await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "accepted"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_quote_terminal_state_returns_422(client):
    """PATCH state from accepted (terminal) should return 422."""
    quote = await _create_quote(client)
    await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "pending"})
    await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "approved"})
    await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "accepted"})
    resp = await client.patch(f"{QUOTE_BASE}/{quote['id']}", json={"state": "cancelled"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_quote_not_found_returns_404(client):
    """PATCH /quote/{id} with an unknown ID should return 404."""
    resp = await client.patch(f"{QUOTE_BASE}/no-such-id", json={"state": "pending"})
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Delete
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_delete_quote_returns_204(client):
    """DELETE /quote/{id} should return 204 and the resource should be gone."""
    quote = await _create_quote(client)
    resp = await client.delete(f"{QUOTE_BASE}/{quote['id']}")
    assert resp.status_code == 204
    get_resp = await client.get(f"{QUOTE_BASE}/{quote['id']}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_quote_not_found_returns_404(client):
    """DELETE /quote/{id} with unknown ID should return 404."""
    resp = await client.delete(f"{QUOTE_BASE}/no-such-id")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Quote Items
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_add_item_to_quote_returns_201(client):
    """POST /quote/{id}/quoteItem should return 201 and the item is included in parent."""
    quote = await _create_quote(client)
    resp = await client.post(
        f"{QUOTE_BASE}/{quote['id']}/quoteItem",
        json={"action": "add", "item_price": 99.90, "price_type": "recurring"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["action"] == "add"
    assert data["item_price"] == 99.90
    assert data["price_type"] == "recurring"


@pytest.mark.asyncio
async def test_list_items_returns_all(client):
    """GET /quote/{id}/quoteItem should return all items."""
    quote = await _create_quote(client)
    await client.post(f"{QUOTE_BASE}/{quote['id']}/quoteItem", json={"action": "add"})
    await client.post(f"{QUOTE_BASE}/{quote['id']}/quoteItem", json={"action": "modify"})
    resp = await client.get(f"{QUOTE_BASE}/{quote['id']}/quoteItem")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_delete_item_returns_204(client):
    """DELETE /quote/{id}/quoteItem/{item_id} should return 204."""
    quote = await _create_quote(client)
    item_resp = await client.post(
        f"{QUOTE_BASE}/{quote['id']}/quoteItem", json={"action": "add"}
    )
    item_id = item_resp.json()["id"]
    del_resp = await client.delete(f"{QUOTE_BASE}/{quote['id']}/quoteItem/{item_id}")
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_add_item_to_nonexistent_quote_returns_404(client):
    """POST /quote/{id}/quoteItem for unknown quote should return 404."""
    resp = await client.post(
        f"{QUOTE_BASE}/no-such-quote/quoteItem", json={"action": "add"}
    )
    assert resp.status_code == 404
