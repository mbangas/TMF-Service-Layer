"""Integration tests for the TMF645 Service Qualification Management API.

Run with: pytest src/qualification/tests/test_qualification_api.py -v

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

BASE = "/tmf-api/serviceQualificationManagement/v4/checkServiceQualification"
CATALOG_BASE = "/tmf-api/serviceCatalogManagement/v4/serviceSpecification"


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


# ── Helpers ────────────────────────────────────────────────────────────────────

async def create_spec(client, *, name="Test Spec"):
    """Create a ServiceSpecification in catalog and return its ID."""
    resp = await client.post(CATALOG_BASE, json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def create_qualification(client, *, name="Test Qual", items=None, **kwargs):
    """Create a ServiceQualification and return the parsed JSON body."""
    payload = {"name": name, **({"items": items} if items is not None else {}), **kwargs}
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── POST / ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_qualification_returns_201(client):
    """POST should return 201 with an acknowledged qualification."""
    resp = await client.post(BASE, json={"name": "FTTH Feasibility Check"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["state"] == "acknowledged"
    assert data["name"] == "FTTH Feasibility Check"
    assert "id" in data
    assert "href" in data
    assert data["items"] == []


@pytest.mark.asyncio
async def test_create_qualification_with_items_returns_201(client):
    """POST with nested items (no spec ref) should return 201 with items."""
    payload = {
        "name": "Qualification with items",
        "items": [
            {"qualifier_message": "Feasible via fibre", "state": "approved"},
            {"qualifier_message": "Coverage limited", "state": "unableToProvide"},
        ],
    }
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["items"]) == 2
    states = {i["state"] for i in data["items"]}
    assert "approved" in states
    assert "unableToProvide" in states


@pytest.mark.asyncio
async def test_create_qualification_with_valid_spec_ref_returns_201(client):
    """POST with items referencing an existing spec should return 201."""
    spec_id = await create_spec(client, name="Broadband 1Gbps")
    payload = {
        "name": "Check broadband feasibility",
        "items": [{"service_spec_id": spec_id, "state": "approved"}],
    }
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["items"][0]["service_spec_id"] == spec_id


@pytest.mark.asyncio
async def test_create_qualification_with_invalid_spec_ref_returns_404(client):
    """POST with item referencing a non-existent spec should return 404."""
    payload = {
        "name": "Bad spec ref",
        "items": [{"service_spec_id": "no-such-spec"}],
    }
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_qualification_missing_name_returns_422(client):
    """POST without name should return 422."""
    resp = await client.post(BASE, json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_qualification_invalid_item_state_returns_422(client):
    """POST with an invalid item state should return 422."""
    resp = await client.post(
        BASE,
        json={"name": "Bad", "items": [{"state": "invalid-state"}]},
    )
    assert resp.status_code == 422


# ── GET / ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_qualifications_empty_returns_200(client):
    """GET / on empty table should return 200 with empty list."""
    resp = await client.get(BASE)
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"
    assert resp.headers["X-Result-Count"] == "0"


@pytest.mark.asyncio
async def test_list_qualifications_returns_pagination_headers(client):
    """GET / should return X-Total-Count and X-Result-Count headers."""
    await create_qualification(client, name="Qual A")
    await create_qualification(client, name="Qual B")

    resp = await client.get(BASE)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert int(resp.headers["X-Total-Count"]) >= 2
    assert int(resp.headers["X-Result-Count"]) >= 2


@pytest.mark.asyncio
async def test_list_qualifications_state_filter(client):
    """GET /?state= should filter by lifecycle state."""
    qual = await create_qualification(client, name="Filterable")
    # Transition to inProgress
    await client.patch(f"{BASE}/{qual['id']}", json={"state": "inProgress"})

    resp = await client.get(BASE, params={"state": "inProgress"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(q["state"] == "inProgress" for q in data)


# ── GET /{id} ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_qualification_returns_200(client):
    """GET /{id} should return the qualification."""
    qual = await create_qualification(client, name="Single Qual")
    resp = await client.get(f"{BASE}/{qual['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == qual["id"]
    assert resp.json()["name"] == "Single Qual"


@pytest.mark.asyncio
async def test_get_qualification_not_found_returns_404(client):
    """GET /{id} with unknown ID should return 404."""
    resp = await client.get(f"{BASE}/no-such-id")
    assert resp.status_code == 404


# ── PATCH /{id} ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_state_acknowledged_to_inprogress(client):
    """PATCH acknowledged → inProgress should succeed."""
    qual = await create_qualification(client, name="Patch Test")
    resp = await client.patch(f"{BASE}/{qual['id']}", json={"state": "inProgress"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "inProgress"


@pytest.mark.asyncio
async def test_patch_state_inprogress_to_accepted(client):
    """PATCH inProgress → accepted should succeed."""
    qual = await create_qualification(client, name="Accept Test")
    await client.patch(f"{BASE}/{qual['id']}", json={"state": "inProgress"})
    resp = await client.patch(f"{BASE}/{qual['id']}", json={"state": "accepted"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "accepted"


@pytest.mark.asyncio
async def test_patch_state_inprogress_to_rejected(client):
    """PATCH inProgress → rejected should succeed."""
    qual = await create_qualification(client, name="Reject Test")
    await client.patch(f"{BASE}/{qual['id']}", json={"state": "inProgress"})
    resp = await client.patch(f"{BASE}/{qual['id']}", json={"state": "rejected"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "rejected"


@pytest.mark.asyncio
async def test_patch_invalid_transition_returns_422(client):
    """PATCH with an invalid state transition should return 422."""
    qual = await create_qualification(client, name="Invalid Transition")
    # acknowledged → accepted is NOT a valid direct transition
    resp = await client.patch(f"{BASE}/{qual['id']}", json={"state": "accepted"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_terminal_state_returns_422(client):
    """PATCH from a terminal state should return 422."""
    qual = await create_qualification(client, name="Terminal Test")
    await client.patch(f"{BASE}/{qual['id']}", json={"state": "inProgress"})
    await client.patch(f"{BASE}/{qual['id']}", json={"state": "accepted"})
    # accepted is terminal — any further transition must be rejected
    resp = await client.patch(f"{BASE}/{qual['id']}", json={"state": "cancelled"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_name_and_description(client):
    """PATCH should update mutable fields without changing state."""
    qual = await create_qualification(client, name="Original Name")
    resp = await client.patch(
        f"{BASE}/{qual['id']}",
        json={"name": "Updated Name", "description": "New desc"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
    assert resp.json()["description"] == "New desc"
    assert resp.json()["state"] == "acknowledged"


@pytest.mark.asyncio
async def test_patch_not_found_returns_404(client):
    """PATCH on unknown ID should return 404."""
    resp = await client.patch(f"{BASE}/no-such-id", json={"state": "inProgress"})
    assert resp.status_code == 404


# ── DELETE /{id} ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_accepted_qualification_returns_204(client):
    """DELETE an accepted qualification should return 204."""
    qual = await create_qualification(client, name="Delete Accepted")
    await client.patch(f"{BASE}/{qual['id']}", json={"state": "inProgress"})
    await client.patch(f"{BASE}/{qual['id']}", json={"state": "accepted"})

    resp = await client.delete(f"{BASE}/{qual['id']}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_cancelled_qualification_returns_204(client):
    """DELETE a cancelled qualification should return 204."""
    qual = await create_qualification(client, name="Delete Cancelled")
    await client.patch(f"{BASE}/{qual['id']}", json={"state": "cancelled"})

    resp = await client.delete(f"{BASE}/{qual['id']}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_inprogress_qualification_returns_422(client):
    """DELETE an inProgress qualification should return 422."""
    qual = await create_qualification(client, name="Cannot Delete")
    await client.patch(f"{BASE}/{qual['id']}", json={"state": "inProgress"})

    resp = await client.delete(f"{BASE}/{qual['id']}")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_not_found_returns_404(client):
    """DELETE on unknown ID should return 404."""
    resp = await client.delete(f"{BASE}/no-such-id")
    assert resp.status_code == 404


# ── Events ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_publishes_create_event(client):
    """POST should publish exactly one ServiceQualificationCreateEvent."""
    EventBus.clear()
    await create_qualification(client, name="Event Test")
    events = EventBus.get_events(10)
    create_events = [e for e in events if e.event_type == "ServiceQualificationCreateEvent"]
    assert len(create_events) == 1


@pytest.mark.asyncio
async def test_patch_state_publishes_state_change_event(client):
    """PATCH with state change should publish a ServiceQualificationStateChangeEvent."""
    EventBus.clear()
    qual = await create_qualification(client, name="State Event Test")
    await client.patch(f"{BASE}/{qual['id']}", json={"state": "inProgress"})
    events = EventBus.get_events(10)
    change_events = [e for e in events if e.event_type == "ServiceQualificationStateChangeEvent"]
    assert len(change_events) == 1
