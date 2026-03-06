"""Integration tests for the TMF640 Service Activation & Configuration API.

Run with: pytest src/provisioning/tests/test_provisioning_api.py -v

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

BASE = "/tmf-api/serviceActivationConfiguration/v4/serviceActivationJob"
INVENTORY_BASE = "/tmf-api/serviceInventory/v4/service"


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

async def create_service(client, *, name="Test Service", state="inactive"):
    """Create a Service instance in inventory and return its ID."""
    resp = await client.post(INVENTORY_BASE, json={"name": name, "state": state})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def create_job(client, *, name="Test Job", job_type="provision", service_id, **kwargs):
    """Create a ServiceActivationJob and return the parsed JSON body."""
    payload = {"name": name, "job_type": job_type, "service_id": service_id, **kwargs}
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── POST / ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_job_returns_201(client):
    """POST should return 201 with an accepted job."""
    svc_id = await create_service(client, state="inactive")
    payload = {
        "name":       "Provision Broadband",
        "job_type":   "provision",
        "service_id": svc_id,
        "description": "Provision a broadband service",
    }
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["state"] == "accepted"
    assert data["job_type"] == "provision"
    assert data["service_id"] == svc_id
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_job_with_params_returns_201(client):
    """POST with nested params should persist and return them."""
    svc_id = await create_service(client, state="inactive")
    payload = {
        "name":       "Provision with config",
        "job_type":   "provision",
        "service_id": svc_id,
        "params": [
            {"name": "speed_mbps",  "value": "1000", "value_type": "integer"},
            {"name": "technology",  "value": "FTTP", "value_type": "string"},
        ],
    }
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["params"]) == 2
    names = {p["name"] for p in data["params"]}
    assert "speed_mbps" in names
    assert "technology" in names


@pytest.mark.asyncio
async def test_create_job_missing_name_returns_422(client):
    """POST without name should return 422."""
    svc_id = await create_service(client, state="inactive")
    resp = await client.post(BASE, json={"job_type": "provision", "service_id": svc_id})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_job_missing_service_id_returns_422(client):
    """POST without service_id should return 422."""
    resp = await client.post(BASE, json={"name": "Test", "job_type": "provision"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_job_invalid_job_type_returns_422(client):
    """POST with an unknown job_type must return 422."""
    svc_id = await create_service(client, state="inactive")
    resp = await client.post(BASE, json={"name": "Test", "job_type": "explode", "service_id": svc_id})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_job_incompatible_service_state_returns_422(client):
    """POST provision job when service is already active must return 422."""
    svc_id = await create_service(client, state="active")
    resp = await client.post(BASE, json={"name": "Test", "job_type": "provision", "service_id": svc_id})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_job_service_not_found_returns_404(client):
    """POST with a non-existent service_id must return 404."""
    resp = await client.post(BASE, json={"name": "Test", "job_type": "provision", "service_id": "no-such-id"})
    assert resp.status_code == 404


# ── GET / ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_jobs_returns_200_with_pagination_headers(client):
    """GET / should return 200 with X-Total-Count and X-Result-Count headers."""
    svc_id = await create_service(client, state="inactive")
    await create_job(client, job_type="provision", service_id=svc_id, name="Job 1")
    svc_id2 = await create_service(client, state="active", name="Active Service")
    await create_job(client, job_type="modify", service_id=svc_id2, name="Job 2")

    resp = await client.get(BASE)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert int(resp.headers["X-Total-Count"]) >= 2
    assert int(resp.headers["X-Result-Count"]) == len(resp.json())


@pytest.mark.asyncio
async def test_list_jobs_state_filter(client):
    """GET /?state=accepted should return only accepted jobs."""
    svc_id = await create_service(client, state="inactive")
    await create_job(client, job_type="provision", service_id=svc_id, name="Accepted Job")

    resp = await client.get(BASE, params={"state": "accepted"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(j["state"] == "accepted" for j in data)


@pytest.mark.asyncio
async def test_list_jobs_job_type_filter(client):
    """GET /?job_type=provision should return only provision jobs."""
    svc_id = await create_service(client, state="inactive")
    await create_job(client, job_type="provision", service_id=svc_id, name="Provision Job")

    resp = await client.get(BASE, params={"job_type": "provision"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(j["job_type"] == "provision" for j in data)


# ── GET /{id} ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_job_by_id_returns_200(client):
    """GET /{id} should return 200 with the matching job."""
    svc_id = await create_service(client, state="inactive")
    created = await create_job(client, job_type="provision", service_id=svc_id)
    resp = await client.get(f"{BASE}/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_job_not_found_returns_404(client):
    """GET /{id} with unknown ID should return 404."""
    resp = await client.get(f"{BASE}/no-such-id")
    assert resp.status_code == 404


# ── PATCH /{id} ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_job_accepted_to_running(client):
    """PATCH accepted → running must return 200."""
    svc_id = await create_service(client, state="inactive")
    job = await create_job(client, job_type="provision", service_id=svc_id)

    resp = await client.patch(f"{BASE}/{job['id']}", json={"state": "running"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "running"


@pytest.mark.asyncio
async def test_patch_job_invalid_transition_returns_422(client):
    """PATCH with an invalid state transition must return 422."""
    svc_id = await create_service(client, state="inactive")
    job = await create_job(client, job_type="provision", service_id=svc_id)

    # accepted → succeeded is not allowed (must go through running first)
    resp = await client.patch(f"{BASE}/{job['id']}", json={"state": "succeeded"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_job_not_found_returns_404(client):
    """PATCH with unknown ID should return 404."""
    resp = await client.patch(f"{BASE}/no-such-id", json={"state": "running"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_job_provision_to_succeeded_activates_service(client):
    """accepted→running→succeeded for provision type must set Service state to active."""
    svc_id = await create_service(client, state="inactive")
    job = await create_job(client, job_type="provision", service_id=svc_id)

    # Transition: accepted → running
    resp = await client.patch(f"{BASE}/{job['id']}", json={"state": "running"})
    assert resp.status_code == 200

    # Transition: running → succeeded
    resp = await client.patch(f"{BASE}/{job['id']}", json={"state": "succeeded"})
    assert resp.status_code == 200

    # Verify the inventory service is now active
    svc_resp = await client.get(f"{INVENTORY_BASE}/{svc_id}")
    assert svc_resp.status_code == 200
    assert svc_resp.json()["state"] == "active"


@pytest.mark.asyncio
async def test_patch_job_deactivate_succeeded_sets_service_inactive(client):
    """deactivate job succeeded must set Service state back to inactive."""
    svc_id = await create_service(client, state="active")
    job = await create_job(client, job_type="deactivate", service_id=svc_id)

    await client.patch(f"{BASE}/{job['id']}", json={"state": "running"})
    resp = await client.patch(f"{BASE}/{job['id']}", json={"state": "succeeded"})
    assert resp.status_code == 200

    svc_resp = await client.get(f"{INVENTORY_BASE}/{svc_id}")
    assert svc_resp.json()["state"] == "inactive"


@pytest.mark.asyncio
async def test_patch_job_terminate_succeeded_sets_service_terminated(client):
    """terminate job succeeded must set Service state to terminated."""
    svc_id = await create_service(client, state="inactive")
    job = await create_job(client, job_type="terminate", service_id=svc_id)

    await client.patch(f"{BASE}/{job['id']}", json={"state": "running"})
    resp = await client.patch(f"{BASE}/{job['id']}", json={"state": "succeeded"})
    assert resp.status_code == 200

    svc_resp = await client.get(f"{INVENTORY_BASE}/{svc_id}")
    assert svc_resp.json()["state"] == "terminated"


# ── DELETE /{id} ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_job_succeeded_returns_422(client):
    """DELETE a succeeded job must return 422."""
    svc_id = await create_service(client, state="inactive")
    job = await create_job(client, job_type="provision", service_id=svc_id)

    await client.patch(f"{BASE}/{job['id']}", json={"state": "running"})
    await client.patch(f"{BASE}/{job['id']}", json={"state": "succeeded"})

    resp = await client.delete(f"{BASE}/{job['id']}")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_job_failed_returns_204(client):
    """DELETE a failed job must return 204."""
    svc_id = await create_service(client, state="inactive")
    job = await create_job(client, job_type="provision", service_id=svc_id)

    await client.patch(f"{BASE}/{job['id']}", json={"state": "running"})
    await client.patch(f"{BASE}/{job['id']}", json={"state": "failed"})

    resp = await client.delete(f"{BASE}/{job['id']}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_job_cancelled_returns_204(client):
    """DELETE a cancelled job must return 204."""
    svc_id = await create_service(client, state="inactive")
    job = await create_job(client, job_type="provision", service_id=svc_id)

    await client.patch(f"{BASE}/{job['id']}", json={"state": "cancelled"})

    resp = await client.delete(f"{BASE}/{job['id']}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_job_not_found_returns_404(client):
    """DELETE an unknown job must return 404."""
    resp = await client.delete(f"{BASE}/no-such-id")
    assert resp.status_code == 404


# ── Events ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_job_publishes_create_event(client):
    """POST must publish a ServiceActivationJobCreateEvent."""
    svc_id = await create_service(client, state="inactive")
    EventBus.clear()

    await create_job(client, job_type="provision", service_id=svc_id)

    events = EventBus.get_events(limit=50)
    create_events = [e for e in events if e.event_type == "ServiceActivationJobCreateEvent"]
    assert len(create_events) == 1


@pytest.mark.asyncio
async def test_patch_job_publishes_state_change_event(client):
    """PATCH must publish a ServiceActivationJobStateChangeEvent."""
    svc_id = await create_service(client, state="inactive")
    job = await create_job(client, job_type="provision", service_id=svc_id)
    EventBus.clear()

    await client.patch(f"{BASE}/{job['id']}", json={"state": "running"})

    events = EventBus.get_events(limit=50)
    state_events = [e for e in events if e.event_type == "ServiceActivationJobStateChangeEvent"]
    assert len(state_events) == 1
