"""Integration tests for the Service Problem API — TMF656.

Run with: pytest src/problem/tests/test_service_problem_api.py -v

Shared ``test_engine`` and ``db_session`` fixtures are provided by ``src/conftest.py``.
An in-memory SQLite database is used; no PostgreSQL is required.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.shared.db.session import get_db
from src.shared.events.bus import EventBus

PROBLEM_BASE = "/tmf-api/serviceProblemManagement/v4/problem"
TICKET_BASE = "/tmf-api/troubleTicketManagement/v4/troubleTicket"
INVENTORY_BASE = "/tmf-api/serviceInventory/v4/service"


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

async def _create_service(client) -> str:
    """Create a Service inventory record and return its ID."""
    resp = await client.post(INVENTORY_BASE, json={"name": "Test Service"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_ticket(client) -> str:
    """Create a TroubleTicket and return its ID."""
    resp = await client.post(TICKET_BASE, json={"name": "Test Ticket"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_problem(client, **kwargs) -> dict:
    """Create a ServiceProblem and return its JSON body."""
    payload = {"name": "Test Problem"}
    payload.update(kwargs)
    resp = await client.post(PROBLEM_BASE, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ══════════════════════════════════════════════════════════════════════════════
# List
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_problems_empty(client):
    """GET /problem should return an empty list when no problems exist."""
    resp = await client.get(PROBLEM_BASE)
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"


@pytest.mark.asyncio
async def test_list_problems_returns_created(client):
    """GET /problem should list previously created problems."""
    await _create_problem(client)
    resp = await client.get(PROBLEM_BASE)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert resp.headers["X-Total-Count"] == "1"


@pytest.mark.asyncio
async def test_list_problems_filter_by_state(client):
    """GET /problem?state=submitted should only return submitted problems."""
    await _create_problem(client, name="P1")
    await _create_problem(client, name="P2")
    resp = await client.get(PROBLEM_BASE, params={"state": "submitted"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["state"] == "submitted"


@pytest.mark.asyncio
async def test_list_problems_filter_by_impact(client):
    """GET /problem?impact=criticalSystemImpact should only return matching problems."""
    await _create_problem(client, name="Critical", impact="criticalSystemImpact")
    await _create_problem(client, name="Local", impact="localImpact")
    resp = await client.get(PROBLEM_BASE, params={"impact": "criticalSystemImpact"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["impact"] == "criticalSystemImpact"


# ══════════════════════════════════════════════════════════════════════════════
# Create
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_problem_minimal_returns_201(client):
    """POST /problem with only name should return 201 in submitted state."""
    resp = await client.post(PROBLEM_BASE, json={"name": "BGP Flapping"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "BGP Flapping"
    assert data["state"] == "submitted"
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_problem_with_service_returns_201(client):
    """POST /problem with a valid related_service_id should return 201."""
    service_id = await _create_service(client)
    resp = await client.post(PROBLEM_BASE, json={"name": "P with Service", "related_service_id": service_id})
    assert resp.status_code == 201
    assert resp.json()["related_service_id"] == service_id


@pytest.mark.asyncio
async def test_create_problem_invalid_service_returns_404(client):
    """POST /problem with a non-existent service_id should return 404."""
    resp = await client.post(PROBLEM_BASE, json={"name": "Bad Problem", "related_service_id": "no-such-id"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_problem_with_ticket_returns_201(client):
    """POST /problem with a valid related_ticket_id should return 201."""
    ticket_id = await _create_ticket(client)
    resp = await client.post(PROBLEM_BASE, json={"name": "P with Ticket", "related_ticket_id": ticket_id})
    assert resp.status_code == 201
    assert resp.json()["related_ticket_id"] == ticket_id


@pytest.mark.asyncio
async def test_create_problem_invalid_ticket_returns_404(client):
    """POST /problem with a non-existent ticket_id should return 404."""
    resp = await client.post(PROBLEM_BASE, json={"name": "Bad Problem", "related_ticket_id": "no-such-ticket"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_problem_invalid_impact_returns_422(client):
    """POST /problem with an unknown impact value should return 422."""
    resp = await client.post(PROBLEM_BASE, json={"name": "Bad Impact", "impact": "catastrophicImpact"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_problem_full_payload_returns_201(client):
    """POST /problem with all fields should persist every attribute."""
    service_id = await _create_service(client)
    ticket_id = await _create_ticket(client)
    resp = await client.post(
        PROBLEM_BASE,
        json={
            "name": "Full Problem",
            "description": "Root cause investigation for outage",
            "impact": "serviceImpact",
            "priority": 2,
            "category": "networkFailure",
            "related_service_id": service_id,
            "related_ticket_id": ticket_id,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["description"] == "Root cause investigation for outage"
    assert data["impact"] == "serviceImpact"
    assert data["priority"] == 2
    assert data["category"] == "networkFailure"
    assert data["related_service_id"] == service_id
    assert data["related_ticket_id"] == ticket_id


# ══════════════════════════════════════════════════════════════════════════════
# Get
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_problem_returns_200(client):
    """GET /problem/{id} should return the problem."""
    problem = await _create_problem(client)
    resp = await client.get(f"{PROBLEM_BASE}/{problem['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == problem["id"]


@pytest.mark.asyncio
async def test_get_problem_not_found_returns_404(client):
    """GET /problem/{id} with unknown ID should return 404."""
    resp = await client.get(f"{PROBLEM_BASE}/no-such-problem")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# State Machine — Patch
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_patch_problem_submitted_to_confirmed(client):
    """PATCH state submitted→confirmed should succeed."""
    problem = await _create_problem(client)
    resp = await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "confirmed"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "confirmed"


@pytest.mark.asyncio
async def test_patch_problem_submitted_to_rejected(client):
    """PATCH state submitted→rejected should succeed."""
    problem = await _create_problem(client)
    resp = await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "rejected"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "rejected"


@pytest.mark.asyncio
async def test_patch_problem_confirmed_to_active(client):
    """PATCH state confirmed→active should succeed."""
    problem = await _create_problem(client)
    await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "confirmed"})
    resp = await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "active"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "active"


@pytest.mark.asyncio
async def test_patch_problem_active_to_resolved(client):
    """PATCH state active→resolved should succeed and set resolution_date."""
    problem = await _create_problem(client)
    await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "confirmed"})
    await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "active"})
    resp = await client.patch(
        f"{PROBLEM_BASE}/{problem['id']}",
        json={"state": "resolved", "resolution": "BGP route reflector reconfigured"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "resolved"
    assert data["resolution"] == "BGP route reflector reconfigured"
    assert data["resolution_date"] is not None


@pytest.mark.asyncio
async def test_patch_problem_resolved_to_closed(client):
    """PATCH state resolved→closed should succeed."""
    problem = await _create_problem(client)
    await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "confirmed"})
    await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "active"})
    await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "resolved"})
    resp = await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "closed"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "closed"


@pytest.mark.asyncio
async def test_patch_problem_invalid_transition_returns_422(client):
    """PATCH state submitted→active is not a valid transition; should return 422."""
    problem = await _create_problem(client)
    resp = await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "active"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_problem_rejected_terminal_returns_422(client):
    """PATCH state from rejected (terminal state) should return 422."""
    problem = await _create_problem(client)
    await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "rejected"})
    resp = await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "confirmed"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_problem_closed_terminal_returns_422(client):
    """PATCH state from closed (terminal state) should return 422."""
    problem = await _create_problem(client)
    await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "confirmed"})
    await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "active"})
    await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "resolved"})
    await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "closed"})
    resp = await client.patch(f"{PROBLEM_BASE}/{problem['id']}", json={"state": "active"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_problem_not_found_returns_404(client):
    """PATCH /problem/{id} with unknown ID should return 404."""
    resp = await client.patch(f"{PROBLEM_BASE}/no-such-id", json={"state": "confirmed"})
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Delete
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_delete_problem_returns_204(client):
    """DELETE /problem/{id} should return 204 and remove the problem."""
    problem = await _create_problem(client)
    resp = await client.delete(f"{PROBLEM_BASE}/{problem['id']}")
    assert resp.status_code == 204
    assert (await client.get(f"{PROBLEM_BASE}/{problem['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_delete_problem_not_found_returns_404(client):
    """DELETE /problem/{id} with unknown ID should return 404."""
    resp = await client.delete(f"{PROBLEM_BASE}/no-such-id")
    assert resp.status_code == 404
