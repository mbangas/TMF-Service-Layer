"""Integration tests for the Service Test Management APIs — TMF653.

Run with: pytest src/testing/tests/test_testing_api.py -v

Shared ``test_engine`` and ``db_session`` fixtures are provided by ``src/conftest.py``.
An in-memory SQLite database is used; no PostgreSQL is required.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.shared.db.session import get_db
from src.shared.events.bus import EventBus

SPEC_BASE = "/tmf-api/serviceTest/v4/serviceTestSpecification"
TEST_BASE = "/tmf-api/serviceTest/v4/serviceTest"
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


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _create_active_service(client) -> str:
    """Create a Service inventory record in 'active' state and return its ID."""
    resp = await client.post(INVENTORY_BASE, json={"name": "Test Service"})
    assert resp.status_code == 201, resp.text
    service_id = resp.json()["id"]
    resp = await client.patch(
        f"{INVENTORY_BASE}/{service_id}", json={"state": "active"}
    )
    assert resp.status_code == 200, resp.text
    return service_id


async def _create_spec(client, **kwargs) -> dict:
    """Create a ServiceTestSpecification and return the response body."""
    payload = {"name": "Connectivity Check", **kwargs}
    resp = await client.post(SPEC_BASE, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_test(client, service_id: str, **kwargs) -> dict:
    """Create a ServiceTest and return the response body."""
    payload = {"name": "Ping Test", "service_id": service_id, **kwargs}
    resp = await client.post(TEST_BASE, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ════════════════════════════════════════════════════════════════════════════
# ServiceTestSpecification — CRUD
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_specs_empty(client):
    """GET /serviceTestSpecification should return empty list when none exist."""
    resp = await client.get(SPEC_BASE)
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"


@pytest.mark.asyncio
async def test_create_spec_returns_201(client):
    """POST /serviceTestSpecification should return 201 with active state."""
    resp = await client.post(
        SPEC_BASE,
        json={"name": "Latency Spec", "test_type": "performance", "version": "1.0"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["state"] == "active"
    assert data["name"] == "Latency Spec"
    assert data["test_type"] == "performance"
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_spec_with_invalid_service_spec_returns_404(client):
    """POST /serviceTestSpecification with non-existent service_spec_id → 404."""
    resp = await client.post(
        SPEC_BASE, json={"name": "Bad Spec", "service_spec_id": "no-such-spec"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_spec_returns_200(client):
    """GET /serviceTestSpecification/{id} should return the spec."""
    created = await _create_spec(client)
    resp = await client.get(f"{SPEC_BASE}/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_spec_not_found_returns_404(client):
    """GET /serviceTestSpecification/{id} with unknown ID → 404."""
    resp = await client.get(f"{SPEC_BASE}/no-such-spec")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_spec_name(client):
    """PATCH /serviceTestSpecification/{id} should update name."""
    created = await _create_spec(client)
    resp = await client.patch(
        f"{SPEC_BASE}/{created['id']}", json={"name": "Updated Name"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_spec_lifecycle_active_to_retired_to_obsolete(client):
    """Spec lifecycle: active → retired → obsolete should succeed."""
    created = await _create_spec(client)
    spec_id = created["id"]

    resp = await client.patch(f"{SPEC_BASE}/{spec_id}", json={"state": "retired"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "retired"

    resp = await client.patch(f"{SPEC_BASE}/{spec_id}", json={"state": "obsolete"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "obsolete"


@pytest.mark.asyncio
async def test_spec_invalid_transition_active_to_obsolete_returns_422(client):
    """Spec: active → obsolete direct transition is blocked (422)."""
    created = await _create_spec(client)
    resp = await client.patch(
        f"{SPEC_BASE}/{created['id']}", json={"state": "obsolete"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_spec_active_returns_422(client):
    """DELETE /serviceTestSpecification/{id} in active state → 422."""
    created = await _create_spec(client)
    resp = await client.delete(f"{SPEC_BASE}/{created['id']}")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_spec_obsolete_returns_204(client):
    """DELETE /serviceTestSpecification/{id} in obsolete state → 204."""
    created = await _create_spec(client)
    spec_id = created["id"]
    await client.patch(f"{SPEC_BASE}/{spec_id}", json={"state": "retired"})
    await client.patch(f"{SPEC_BASE}/{spec_id}", json={"state": "obsolete"})
    resp = await client.delete(f"{SPEC_BASE}/{spec_id}")
    assert resp.status_code == 204
    # Confirm gone
    assert (await client.get(f"{SPEC_BASE}/{spec_id}")).status_code == 404


# ════════════════════════════════════════════════════════════════════════════
# ServiceTest — CRUD
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_tests_empty(client):
    """GET /serviceTest should return empty list when none exist."""
    resp = await client.get(TEST_BASE)
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"


@pytest.mark.asyncio
async def test_create_test_returns_201(client):
    """POST /serviceTest should return 201 with planned state."""
    service_id = await _create_active_service(client)
    resp = await client.post(
        TEST_BASE, json={"name": "Ping Test", "service_id": service_id, "mode": "automated"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["state"] == "planned"
    assert data["name"] == "Ping Test"
    assert data["mode"] == "automated"
    assert data["service_id"] == service_id
    assert data["measures"] == []
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_test_inactive_service_returns_422(client):
    """POST /serviceTest with inactive service → 422."""
    resp = await client.post(INVENTORY_BASE, json={"name": "Inactive Service"})
    service_id = resp.json()["id"]
    resp = await client.post(
        TEST_BASE, json={"name": "Bad Test", "service_id": service_id}
    )
    assert resp.status_code == 422
    assert "active" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_test_invalid_service_returns_404(client):
    """POST /serviceTest with non-existent service_id → 404."""
    resp = await client.post(
        TEST_BASE, json={"name": "Ghost Test", "service_id": "no-such-service"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_test_with_obsolete_spec_returns_422(client):
    """POST /serviceTest with an obsolete test spec → 422."""
    service_id = await _create_active_service(client)
    spec = await _create_spec(client)
    spec_id = spec["id"]
    await client.patch(f"{SPEC_BASE}/{spec_id}", json={"state": "retired"})
    await client.patch(f"{SPEC_BASE}/{spec_id}", json={"state": "obsolete"})

    resp = await client.post(
        TEST_BASE,
        json={"name": "Bad Test", "service_id": service_id, "test_spec_id": spec_id},
    )
    assert resp.status_code == 422
    assert "obsolete" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_test_with_active_spec_returns_201(client):
    """POST /serviceTest with valid active spec → 201."""
    service_id = await _create_active_service(client)
    spec = await _create_spec(client)
    resp = await client.post(
        TEST_BASE,
        json={"name": "Spec Test", "service_id": service_id, "test_spec_id": spec["id"]},
    )
    assert resp.status_code == 201
    assert resp.json()["test_spec_id"] == spec["id"]


@pytest.mark.asyncio
async def test_get_test_returns_200(client):
    """GET /serviceTest/{id} should return the test."""
    service_id = await _create_active_service(client)
    created = await _create_test(client, service_id)
    resp = await client.get(f"{TEST_BASE}/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_test_not_found_returns_404(client):
    """GET /serviceTest/{id} with unknown ID → 404."""
    resp = await client.get(f"{TEST_BASE}/no-such-test")
    assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════════════
# ServiceTest — State Machine
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_test_planned_to_inprogress_sets_start_date(client):
    """planned → inProgress should set start_date_time."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    resp = await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "inProgress"
    assert data["start_date_time"] is not None


@pytest.mark.asyncio
async def test_test_inprogress_to_completed_sets_end_date(client):
    """inProgress → completed should set end_date_time."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})
    resp = await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "completed"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "completed"
    assert data["end_date_time"] is not None


@pytest.mark.asyncio
async def test_test_inprogress_to_failed_sets_end_date(client):
    """inProgress → failed should set end_date_time."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})
    resp = await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "failed"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "failed"
    assert resp.json()["end_date_time"] is not None


@pytest.mark.asyncio
async def test_test_planned_to_cancelled_sets_end_date(client):
    """planned → cancelled should set end_date_time."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    resp = await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "cancelled"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "cancelled"
    assert resp.json()["end_date_time"] is not None


@pytest.mark.asyncio
async def test_test_planned_to_completed_is_blocked(client):
    """planned → completed direct transition is blocked (422)."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    resp = await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "completed"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_test_transition_from_terminal_state_blocked(client):
    """State transition from a terminal state (completed) is blocked (422)."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "completed"})
    resp = await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})
    assert resp.status_code == 422
    assert "terminal" in resp.json()["detail"].lower()


# ════════════════════════════════════════════════════════════════════════════
# ServiceTest — Delete guards
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_delete_test_planned_returns_422(client):
    """DELETE /serviceTest/{id} in planned state → 422."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    resp = await client.delete(f"{TEST_BASE}/{test['id']}")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_test_completed_returns_204(client):
    """DELETE /serviceTest/{id} in completed state → 204."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "completed"})
    resp = await client.delete(f"{TEST_BASE}/{test['id']}")
    assert resp.status_code == 204
    assert (await client.get(f"{TEST_BASE}/{test['id']}")).status_code == 404


# ════════════════════════════════════════════════════════════════════════════
# TestMeasure
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_add_measure_when_inprogress_returns_201(client):
    """POST .../testMeasure on inProgress test → 201."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})

    resp = await client.post(
        f"{TEST_BASE}/{test['id']}/testMeasure",
        json={"metric_name": "latency_ms", "metric_value": 42.5, "result": "pass"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["metric_name"] == "latency_ms"
    assert data["metric_value"] == 42.5
    assert data["result"] == "pass"
    assert data["service_test_id"] == test["id"]


@pytest.mark.asyncio
async def test_add_measure_when_not_inprogress_returns_422(client):
    """POST .../testMeasure on planned test → 422."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    resp = await client.post(
        f"{TEST_BASE}/{test['id']}/testMeasure",
        json={"metric_name": "cpu_pct"},
    )
    assert resp.status_code == 422
    assert "inProgress" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_add_measure_invalid_result_returns_422(client):
    """POST .../testMeasure with invalid result string → 422."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})
    resp = await client.post(
        f"{TEST_BASE}/{test['id']}/testMeasure",
        json={"metric_name": "cpu_pct", "result": "unknown"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_measures_returns_all(client):
    """GET .../testMeasure should return all measures for the test."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})
    await client.post(
        f"{TEST_BASE}/{test['id']}/testMeasure",
        json={"metric_name": "latency_ms", "metric_value": 10.0},
    )
    await client.post(
        f"{TEST_BASE}/{test['id']}/testMeasure",
        json={"metric_name": "packet_loss_pct", "metric_value": 0.1},
    )

    resp = await client.get(f"{TEST_BASE}/{test['id']}/testMeasure")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_measures_embedded_in_get_test(client):
    """GET /serviceTest/{id} should embed measures in response."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})
    await client.post(
        f"{TEST_BASE}/{test['id']}/testMeasure",
        json={"metric_name": "rtt_ms", "metric_value": 5.0, "result": "pass"},
    )

    resp = await client.get(f"{TEST_BASE}/{test['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["measures"]) == 1
    assert data["measures"][0]["metric_name"] == "rtt_ms"


@pytest.mark.asyncio
async def test_measures_cascade_deleted_with_test(client):
    """Deleting a completed test should remove its measures."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})
    await client.post(
        f"{TEST_BASE}/{test['id']}/testMeasure",
        json={"metric_name": "latency_ms"},
    )
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "completed"})
    await client.delete(f"{TEST_BASE}/{test['id']}")
    # Test should be gone; list_measures should return 404
    resp = await client.get(f"{TEST_BASE}/{test['id']}/testMeasure")
    assert resp.status_code == 404


# ════════════════════════════════════════════════════════════════════════════
# Events
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_test_publishes_event(client):
    """POST /serviceTest should publish ServiceTestCreateEvent."""
    service_id = await _create_active_service(client)
    EventBus.clear()
    await _create_test(client, service_id)
    events = EventBus.get_events(10)
    assert any(e.event_type == "ServiceTestCreateEvent" for e in events)


@pytest.mark.asyncio
async def test_complete_test_publishes_complete_event(client):
    """Completing a test should publish ServiceTestCompleteEvent."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})
    EventBus.clear()
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "completed"})
    events = EventBus.get_events(10)
    assert any(e.event_type == "ServiceTestCompleteEvent" for e in events)


@pytest.mark.asyncio
async def test_fail_test_publishes_failed_event(client):
    """Failing a test should publish ServiceTestFailedEvent."""
    service_id = await _create_active_service(client)
    test = await _create_test(client, service_id)
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "inProgress"})
    EventBus.clear()
    await client.patch(f"{TEST_BASE}/{test['id']}", json={"state": "failed"})
    events = EventBus.get_events(10)
    assert any(e.event_type == "ServiceTestFailedEvent" for e in events)
