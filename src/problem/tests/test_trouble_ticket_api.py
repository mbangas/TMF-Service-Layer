"""Integration tests for the Trouble Ticket API — TMF621.

Run with: pytest src/problem/tests/test_trouble_ticket_api.py -v

Shared ``test_engine`` and ``db_session`` fixtures are provided by ``src/conftest.py``.
An in-memory SQLite database is used; no PostgreSQL is required.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.shared.db.session import get_db
from src.shared.events.bus import EventBus

TICKET_BASE = "/tmf-api/troubleTicketManagement/v4/troubleTicket"
ALARM_BASE = "/tmf-api/alarmManagement/v4/alarm"
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


async def _create_active_service(client) -> str:
    """Create a Service inventory record in 'active' state and return its ID."""
    service_id = await _create_service(client)
    resp = await client.patch(f"{INVENTORY_BASE}/{service_id}", json={"state": "active"})
    assert resp.status_code == 200, resp.text
    return service_id


async def _create_alarm(client, service_id: str) -> str:
    """Create an Alarm linked to an active service and return its ID."""
    resp = await client.post(ALARM_BASE, json={"name": "Test Alarm", "service_id": service_id})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_ticket(client, **kwargs) -> dict:
    """Create a TroubleTicket and return its JSON body."""
    payload = {"name": "Test Ticket"}
    payload.update(kwargs)
    resp = await client.post(TICKET_BASE, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ══════════════════════════════════════════════════════════════════════════════
# List
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_tickets_empty(client):
    """GET /troubleTicket should return an empty list when no tickets exist."""
    resp = await client.get(TICKET_BASE)
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"


@pytest.mark.asyncio
async def test_list_tickets_returns_created(client):
    """GET /troubleTicket should list previously created tickets."""
    await _create_ticket(client)
    resp = await client.get(TICKET_BASE)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert resp.headers["X-Total-Count"] == "1"


@pytest.mark.asyncio
async def test_list_tickets_filter_by_state(client):
    """GET /troubleTicket?state=submitted should only return submitted tickets."""
    await _create_ticket(client, name="T1")
    await _create_ticket(client, name="T2")
    resp = await client.get(TICKET_BASE, params={"state": "submitted"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["state"] == "submitted"


@pytest.mark.asyncio
async def test_list_tickets_filter_by_severity(client):
    """GET /troubleTicket?severity=critical should only return critical tickets."""
    await _create_ticket(client, name="Critical", severity="critical")
    await _create_ticket(client, name="Minor", severity="minor")
    resp = await client.get(TICKET_BASE, params={"severity": "critical"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["severity"] == "critical"


# ══════════════════════════════════════════════════════════════════════════════
# Create
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_ticket_minimal_returns_201(client):
    """POST /troubleTicket with only name should return 201 in submitted state."""
    resp = await client.post(TICKET_BASE, json={"name": "Connectivity Issue"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Connectivity Issue"
    assert data["state"] == "submitted"
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_ticket_with_service_returns_201(client):
    """POST /troubleTicket with a valid service_id should return 201."""
    service_id = await _create_service(client)
    resp = await client.post(TICKET_BASE, json={"name": "T with Service", "related_service_id": service_id})
    assert resp.status_code == 201
    assert resp.json()["related_service_id"] == service_id


@pytest.mark.asyncio
async def test_create_ticket_invalid_service_returns_404(client):
    """POST /troubleTicket with a non-existent service_id should return 404."""
    resp = await client.post(TICKET_BASE, json={"name": "Bad Ticket", "related_service_id": "no-such-id"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_ticket_with_alarm_returns_201(client):
    """POST /troubleTicket with a valid alarm_id should return 201."""
    service_id = await _create_active_service(client)
    alarm_id = await _create_alarm(client, service_id)
    resp = await client.post(
        TICKET_BASE,
        json={"name": "Ticket with Alarm", "related_service_id": service_id, "related_alarm_id": alarm_id},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["related_alarm_id"] == alarm_id


@pytest.mark.asyncio
async def test_create_ticket_invalid_alarm_returns_404(client):
    """POST /troubleTicket with a non-existent alarm_id should return 404."""
    resp = await client.post(TICKET_BASE, json={"name": "Bad Ticket", "related_alarm_id": "no-such-alarm"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_ticket_invalid_severity_returns_422(client):
    """POST /troubleTicket with an unknown severity should return 422."""
    resp = await client.post(TICKET_BASE, json={"name": "Bad Severity Ticket", "severity": "extreme"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_ticket_with_initial_note(client):
    """POST /troubleTicket with initial notes should persist the notes on creation."""
    resp = await client.post(
        TICKET_BASE,
        json={"name": "Ticket with Note", "notes": [{"text": "First observation", "author": "NOC"}]},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["notes"]) == 1
    assert data["notes"][0]["text"] == "First observation"
    assert data["notes"][0]["author"] == "NOC"


# ══════════════════════════════════════════════════════════════════════════════
# Get
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_ticket_returns_200(client):
    """GET /troubleTicket/{id} should return the ticket."""
    ticket = await _create_ticket(client)
    resp = await client.get(f"{TICKET_BASE}/{ticket['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == ticket["id"]


@pytest.mark.asyncio
async def test_get_ticket_not_found_returns_404(client):
    """GET /troubleTicket/{id} with unknown ID should return 404."""
    resp = await client.get(f"{TICKET_BASE}/no-such-ticket")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# State Machine — Patch
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_patch_ticket_submitted_to_inprogress(client):
    """PATCH state submitted→inProgress should succeed."""
    ticket = await _create_ticket(client)
    resp = await client.patch(f"{TICKET_BASE}/{ticket['id']}", json={"state": "inProgress"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "inProgress"


@pytest.mark.asyncio
async def test_patch_ticket_inprogress_to_pending(client):
    """PATCH state inProgress→pending should succeed."""
    ticket = await _create_ticket(client)
    await client.patch(f"{TICKET_BASE}/{ticket['id']}", json={"state": "inProgress"})
    resp = await client.patch(f"{TICKET_BASE}/{ticket['id']}", json={"state": "pending"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "pending"


@pytest.mark.asyncio
async def test_patch_ticket_inprogress_to_resolved(client):
    """PATCH state inProgress→resolved should succeed and set resolution_date."""
    ticket = await _create_ticket(client)
    await client.patch(f"{TICKET_BASE}/{ticket['id']}", json={"state": "inProgress"})
    resp = await client.patch(
        f"{TICKET_BASE}/{ticket['id']}",
        json={"state": "resolved", "resolution": "Issue fixed by replacing ONT"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "resolved"
    assert data["resolution"] == "Issue fixed by replacing ONT"
    assert data["resolution_date"] is not None


@pytest.mark.asyncio
async def test_patch_ticket_resolved_to_closed(client):
    """PATCH state resolved→closed should succeed."""
    ticket = await _create_ticket(client)
    await client.patch(f"{TICKET_BASE}/{ticket['id']}", json={"state": "inProgress"})
    await client.patch(f"{TICKET_BASE}/{ticket['id']}", json={"state": "resolved"})
    resp = await client.patch(f"{TICKET_BASE}/{ticket['id']}", json={"state": "closed"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "closed"


@pytest.mark.asyncio
async def test_patch_ticket_invalid_transition_returns_422(client):
    """PATCH state submitted→closed is not a valid transition; should return 422."""
    ticket = await _create_ticket(client)
    resp = await client.patch(f"{TICKET_BASE}/{ticket['id']}", json={"state": "closed"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_ticket_terminal_state_returns_422(client):
    """PATCH state from closed (terminal state) should return 422."""
    ticket = await _create_ticket(client)
    await client.patch(f"{TICKET_BASE}/{ticket['id']}", json={"state": "inProgress"})
    await client.patch(f"{TICKET_BASE}/{ticket['id']}", json={"state": "resolved"})
    await client.patch(f"{TICKET_BASE}/{ticket['id']}", json={"state": "closed"})
    # Now try to transition from terminal state
    resp = await client.patch(f"{TICKET_BASE}/{ticket['id']}", json={"state": "inProgress"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_ticket_not_found_returns_404(client):
    """PATCH /troubleTicket/{id} with unknown ID should return 404."""
    resp = await client.patch(f"{TICKET_BASE}/no-such-id", json={"state": "inProgress"})
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Delete
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_delete_ticket_returns_204(client):
    """DELETE /troubleTicket/{id} should return 204 and remove the ticket."""
    ticket = await _create_ticket(client)
    resp = await client.delete(f"{TICKET_BASE}/{ticket['id']}")
    assert resp.status_code == 204
    assert (await client.get(f"{TICKET_BASE}/{ticket['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_delete_ticket_not_found_returns_404(client):
    """DELETE /troubleTicket/{id} with unknown ID should return 404."""
    resp = await client.delete(f"{TICKET_BASE}/no-such-id")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Notes
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_notes_empty(client):
    """GET /troubleTicket/{id}/note should return empty list for a new ticket."""
    ticket = await _create_ticket(client)
    resp = await client.get(f"{TICKET_BASE}/{ticket['id']}/note")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_add_note_returns_201(client):
    """POST /troubleTicket/{id}/note should return 201 and persist the note."""
    ticket = await _create_ticket(client)
    resp = await client.post(
        f"{TICKET_BASE}/{ticket['id']}/note",
        json={"text": "Customer confirmed issue persists.", "author": "NOC-A"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["text"] == "Customer confirmed issue persists."
    assert data["author"] == "NOC-A"
    assert "id" in data
    assert "note_date" in data


@pytest.mark.asyncio
async def test_add_note_reflected_in_ticket_detail(client):
    """Notes added via note endpoint should appear in GET /troubleTicket/{id} notes list."""
    ticket = await _create_ticket(client)
    await client.post(f"{TICKET_BASE}/{ticket['id']}/note", json={"text": "Note 1"})
    await client.post(f"{TICKET_BASE}/{ticket['id']}/note", json={"text": "Note 2"})
    resp = await client.get(f"{TICKET_BASE}/{ticket['id']}")
    assert resp.status_code == 200
    notes = resp.json()["notes"]
    assert len(notes) == 2


@pytest.mark.asyncio
async def test_add_note_to_nonexistent_ticket_returns_404(client):
    """POST note to a non-existent ticket should return 404."""
    resp = await client.post(f"{TICKET_BASE}/no-such-id/note", json={"text": "Ghost note"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_note_returns_204(client):
    """DELETE /troubleTicket/{id}/note/{note_id} should remove the note."""
    ticket = await _create_ticket(client)
    note_resp = await client.post(
        f"{TICKET_BASE}/{ticket['id']}/note",
        json={"text": "Temporary note"},
    )
    note_id = note_resp.json()["id"]
    # Delete it
    resp = await client.delete(f"{TICKET_BASE}/{ticket['id']}/note/{note_id}")
    assert resp.status_code == 204
    # Verify it's gone
    detail = (await client.get(f"{TICKET_BASE}/{ticket['id']}")).json()
    assert all(n["id"] != note_id for n in detail.get("notes", []))


@pytest.mark.asyncio
async def test_delete_note_not_found_returns_404(client):
    """DELETE note with unknown note_id should return 404."""
    ticket = await _create_ticket(client)
    resp = await client.delete(f"{TICKET_BASE}/{ticket['id']}/note/no-such-note")
    assert resp.status_code == 404
