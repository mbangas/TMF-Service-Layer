"""Integration tests for the Assurance APIs — TMF642, TMF628, TMF657.

Run with: pytest src/assurance/tests/test_assurance_api.py -v

Shared ``test_engine`` and ``db_session`` fixtures are provided by ``src/conftest.py``.
An in-memory SQLite database is used; no PostgreSQL is required.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.shared.db.session import get_db
from src.shared.events.bus import EventBus

ALARM_BASE = "/tmf-api/alarmManagement/v4/alarm"
MEASUREMENT_BASE = "/tmf-api/performanceManagement/v4/performanceMeasurement"
SLO_BASE = "/tmf-api/serviceLevelManagement/v4/serviceLevel"
CATALOG_BASE = "/tmf-api/serviceCatalogManagement/v4/serviceSpecification"
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

async def _create_active_service(client) -> str:
    """Create a Service inventory record that is in 'active' state and return its ID."""
    resp = await client.post(INVENTORY_BASE, json={"name": "Test Service"})
    assert resp.status_code == 201, resp.text
    service_id = resp.json()["id"]
    # inactive → active via PATCH
    resp = await client.patch(f"{INVENTORY_BASE}/{service_id}", json={"state": "active"})
    assert resp.status_code == 200, resp.text
    return service_id


async def _create_spec_with_sls(client) -> tuple[str, str]:
    """Create a ServiceSpecification that includes one SLS; return (spec_id, sls_id)."""
    resp = await client.post(
        CATALOG_BASE,
        json={
            "name": "Test Spec with SLS",
            "serviceLevelSpecification": [{"name": "Availability SLA", "availability": 99.9}],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    spec_id = body["id"]
    sls_id = body["serviceLevelSpecification"][0]["id"]
    return spec_id, sls_id


# ════════════════════════════════════════════════════════════════════════════════
# TMF642 — Alarm Management
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_alarms_empty(client):
    """GET /alarm should return an empty list when no alarms exist."""
    resp = await client.get(ALARM_BASE)
    assert resp.status_code == 200
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"


@pytest.mark.asyncio
async def test_create_alarm_returns_201(client):
    """POST /alarm should return 201 with a raised alarm."""
    service_id = await _create_active_service(client)
    resp = await client.post(
        ALARM_BASE,
        json={"name": "Link Down", "service_id": service_id, "severity": "critical"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["state"] == "raised"
    assert data["name"] == "Link Down"
    assert data["severity"] == "critical"
    assert data["service_id"] == service_id
    assert "id" in data
    assert "href" in data


@pytest.mark.asyncio
async def test_create_alarm_inactive_service_returns_422(client):
    """POST /alarm with an inactive service should return 422."""
    resp = await client.post(INVENTORY_BASE, json={"name": "Inactive Service"})
    service_id = resp.json()["id"]
    resp = await client.post(
        ALARM_BASE, json={"name": "Bad Alarm", "service_id": service_id}
    )
    assert resp.status_code == 422
    assert "active" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_alarm_invalid_service_returns_404(client):
    """POST /alarm with a non-existent service ID should return 404."""
    resp = await client.post(
        ALARM_BASE, json={"name": "Ghost Alarm", "service_id": "non-existent-id"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_alarm_invalid_severity_returns_422(client):
    """POST /alarm with an invalid severity should return 422."""
    service_id = await _create_active_service(client)
    resp = await client.post(
        ALARM_BASE,
        json={"name": "Bad Severity", "service_id": service_id, "severity": "extreme"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_alarm_returns_200(client):
    """GET /alarm/{id} should return the alarm."""
    service_id = await _create_active_service(client)
    created = (await client.post(ALARM_BASE, json={"name": "CPU High", "service_id": service_id})).json()
    resp = await client.get(f"{ALARM_BASE}/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_alarm_not_found_returns_404(client):
    """GET /alarm/{id} with unknown ID should return 404."""
    resp = await client.get(f"{ALARM_BASE}/no-such-alarm")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_alarm_state_raised_to_acknowledged(client):
    """PATCH /alarm/{id} raised→acknowledged should succeed and set acknowledged_at."""
    service_id = await _create_active_service(client)
    alarm = (await client.post(ALARM_BASE, json={"name": "Alarm A", "service_id": service_id})).json()
    resp = await client.patch(f"{ALARM_BASE}/{alarm['id']}", json={"state": "acknowledged"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "acknowledged"
    assert data["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_patch_alarm_state_acknowledged_to_cleared(client):
    """PATCH /alarm/{id} acknowledged→cleared should succeed and set cleared_at."""
    service_id = await _create_active_service(client)
    alarm = (await client.post(ALARM_BASE, json={"name": "Alarm B", "service_id": service_id})).json()
    await client.patch(f"{ALARM_BASE}/{alarm['id']}", json={"state": "acknowledged"})
    resp = await client.patch(f"{ALARM_BASE}/{alarm['id']}", json={"state": "cleared"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "cleared"
    assert data["cleared_at"] is not None


@pytest.mark.asyncio
async def test_patch_alarm_invalid_transition_returns_422(client):
    """PATCH /alarm/{id} with invalid state transition should return 422."""
    service_id = await _create_active_service(client)
    alarm = (await client.post(ALARM_BASE, json={"name": "Alarm C", "service_id": service_id})).json()
    # raised → cleared is not a valid transition
    resp = await client.patch(f"{ALARM_BASE}/{alarm['id']}", json={"state": "cleared"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_alarm_not_cleared_returns_422(client):
    """DELETE /alarm/{id} in raised state should return 422."""
    service_id = await _create_active_service(client)
    alarm = (await client.post(ALARM_BASE, json={"name": "Alarm D", "service_id": service_id})).json()
    resp = await client.delete(f"{ALARM_BASE}/{alarm['id']}")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_alarm_cleared_returns_204(client):
    """DELETE /alarm/{id} in cleared state should return 204."""
    service_id = await _create_active_service(client)
    alarm = (await client.post(ALARM_BASE, json={"name": "Alarm E", "service_id": service_id})).json()
    await client.patch(f"{ALARM_BASE}/{alarm['id']}", json={"state": "acknowledged"})
    await client.patch(f"{ALARM_BASE}/{alarm['id']}", json={"state": "cleared"})
    resp = await client.delete(f"{ALARM_BASE}/{alarm['id']}")
    assert resp.status_code == 204
    # Confirm it's gone
    assert (await client.get(f"{ALARM_BASE}/{alarm['id']}")).status_code == 404


# ════════════════════════════════════════════════════════════════════════════════
# TMF628 — Performance Measurement
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_measurements_empty(client):
    """GET /performanceMeasurement should return an empty list initially."""
    resp = await client.get(MEASUREMENT_BASE)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_measurement_returns_201(client):
    """POST /performanceMeasurement should return 201 with scheduled state."""
    service_id = await _create_active_service(client)
    resp = await client.post(
        MEASUREMENT_BASE,
        json={"name": "Latency Check", "metric_name": "latency_ms", "service_id": service_id},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["state"] == "scheduled"
    assert data["metric_name"] == "latency_ms"
    assert data["service_id"] == service_id


@pytest.mark.asyncio
async def test_create_measurement_invalid_service_returns_404(client):
    """POST /performanceMeasurement with non-existent service should return 404."""
    resp = await client.post(
        MEASUREMENT_BASE,
        json={"name": "Bad Measurement", "metric_name": "cpu", "service_id": "no-such-id"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_measurement_returns_200(client):
    """GET /performanceMeasurement/{id} should return the measurement."""
    service_id = await _create_active_service(client)
    m = (
        await client.post(
            MEASUREMENT_BASE,
            json={"name": "M Get", "metric_name": "cpu", "service_id": service_id},
        )
    ).json()
    resp = await client.get(f"{MEASUREMENT_BASE}/{m['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == m["id"]


@pytest.mark.asyncio
async def test_patch_measurement_scheduled_to_completed(client):
    """PATCH /performanceMeasurement/{id} scheduled→completed should succeed."""
    service_id = await _create_active_service(client)
    m = (
        await client.post(
            MEASUREMENT_BASE,
            json={"name": "M Complete", "metric_name": "cpu", "service_id": service_id},
        )
    ).json()
    resp = await client.patch(
        f"{MEASUREMENT_BASE}/{m['id']}", json={"state": "completed", "metric_value": 42.5}
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "completed"


@pytest.mark.asyncio
async def test_patch_measurement_scheduled_to_failed(client):
    """PATCH /performanceMeasurement/{id} scheduled→failed should succeed."""
    service_id = await _create_active_service(client)
    m = (
        await client.post(
            MEASUREMENT_BASE,
            json={"name": "M Fail", "metric_name": "cpu", "service_id": service_id},
        )
    ).json()
    resp = await client.patch(f"{MEASUREMENT_BASE}/{m['id']}", json={"state": "failed"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "failed"


@pytest.mark.asyncio
async def test_patch_measurement_invalid_transition_returns_422(client):
    """PATCH /performanceMeasurement/{id} with invalid transition returns 422."""
    service_id = await _create_active_service(client)
    m = (
        await client.post(
            MEASUREMENT_BASE,
            json={"name": "M Invalid", "metric_name": "cpu", "service_id": service_id},
        )
    ).json()
    # scheduled → scheduled is not a valid forward transition (no change is fine, but
    # let's try an explicitly wrong one: completed → scheduled)
    await client.patch(f"{MEASUREMENT_BASE}/{m['id']}", json={"state": "completed"})
    resp = await client.patch(f"{MEASUREMENT_BASE}/{m['id']}", json={"state": "scheduled"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_measurement_scheduled_returns_422(client):
    """DELETE /performanceMeasurement/{id} in scheduled state should return 422."""
    service_id = await _create_active_service(client)
    m = (
        await client.post(
            MEASUREMENT_BASE,
            json={"name": "M Del Test", "metric_name": "cpu", "service_id": service_id},
        )
    ).json()
    resp = await client.delete(f"{MEASUREMENT_BASE}/{m['id']}")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_measurement_completed_returns_204(client):
    """DELETE /performanceMeasurement/{id} in completed state should return 204."""
    service_id = await _create_active_service(client)
    m = (
        await client.post(
            MEASUREMENT_BASE,
            json={"name": "M Del Complete", "metric_name": "cpu", "service_id": service_id},
        )
    ).json()
    await client.patch(f"{MEASUREMENT_BASE}/{m['id']}", json={"state": "completed"})
    resp = await client.delete(f"{MEASUREMENT_BASE}/{m['id']}")
    assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════════════════
# TMF657 — Service Level Management
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_slos_empty(client):
    """GET /serviceLevel should return an empty list initially."""
    resp = await client.get(SLO_BASE)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_slo_returns_201(client):
    """POST /serviceLevel should return 201 with active state."""
    service_id = await _create_active_service(client)
    resp = await client.post(
        SLO_BASE,
        json={
            "name": "Latency SLO",
            "metric_name": "latency_ms",
            "threshold_value": 100.0,
            "direction": "above",
            "service_id": service_id,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["state"] == "active"
    assert data["metric_name"] == "latency_ms"
    assert data["threshold_value"] == 100.0


@pytest.mark.asyncio
async def test_create_slo_invalid_service_returns_404(client):
    """POST /serviceLevel with non-existent service should return 404."""
    resp = await client.post(
        SLO_BASE,
        json={"name": "Bad SLO", "metric_name": "cpu", "service_id": "no-such-id"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_slo_with_valid_sls_returns_201(client):
    """POST /serviceLevel with a valid sls_id should return 201."""
    service_id = await _create_active_service(client)
    _, sls_id = await _create_spec_with_sls(client)
    resp = await client.post(
        SLO_BASE,
        json={
            "name": "Availability SLO",
            "metric_name": "availability_pct",
            "threshold_value": 99.9,
            "direction": "below",
            "service_id": service_id,
            "sls_id": sls_id,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["sls_id"] == sls_id


@pytest.mark.asyncio
async def test_create_slo_with_invalid_sls_returns_404(client):
    """POST /serviceLevel with a non-existent sls_id should return 404."""
    service_id = await _create_active_service(client)
    resp = await client.post(
        SLO_BASE,
        json={
            "name": "Bad SLO",
            "metric_name": "cpu",
            "service_id": service_id,
            "sls_id": "no-such-sls",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_slo_returns_200(client):
    """GET /serviceLevel/{id} should return the SLO."""
    service_id = await _create_active_service(client)
    slo = (
        await client.post(
            SLO_BASE,
            json={"name": "SLO Get", "metric_name": "cpu", "service_id": service_id},
        )
    ).json()
    resp = await client.get(f"{SLO_BASE}/{slo['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == slo["id"]


@pytest.mark.asyncio
async def test_patch_slo_active_to_suspended(client):
    """PATCH /serviceLevel/{id} active→suspended should succeed."""
    service_id = await _create_active_service(client)
    slo = (
        await client.post(
            SLO_BASE,
            json={"name": "SLO Suspend", "metric_name": "latency", "service_id": service_id},
        )
    ).json()
    resp = await client.patch(f"{SLO_BASE}/{slo['id']}", json={"state": "suspended"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "suspended"


@pytest.mark.asyncio
async def test_patch_slo_suspended_to_active(client):
    """PATCH /serviceLevel/{id} suspended→active should succeed."""
    service_id = await _create_active_service(client)
    slo = (
        await client.post(
            SLO_BASE,
            json={"name": "SLO Reactivate", "metric_name": "latency", "service_id": service_id},
        )
    ).json()
    await client.patch(f"{SLO_BASE}/{slo['id']}", json={"state": "suspended"})
    resp = await client.patch(f"{SLO_BASE}/{slo['id']}", json={"state": "active"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "active"


@pytest.mark.asyncio
async def test_patch_slo_invalid_transition_returns_422(client):
    """PATCH /serviceLevel/{id} with an invalid transition should return 422."""
    service_id = await _create_active_service(client)
    slo = (
        await client.post(
            SLO_BASE,
            json={"name": "SLO Invalid", "metric_name": "latency", "service_id": service_id},
        )
    ).json()
    # active → violated is NOT allowed via PATCH (only via check_violations)
    resp = await client.patch(f"{SLO_BASE}/{slo['id']}", json={"state": "violated"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_slo_active_returns_422(client):
    """DELETE /serviceLevel/{id} in active state should return 422."""
    service_id = await _create_active_service(client)
    slo = (
        await client.post(
            SLO_BASE,
            json={"name": "SLO Del A", "metric_name": "cpu", "service_id": service_id},
        )
    ).json()
    resp = await client.delete(f"{SLO_BASE}/{slo['id']}")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_slo_suspended_returns_204(client):
    """DELETE /serviceLevel/{id} in suspended state should return 204."""
    service_id = await _create_active_service(client)
    slo = (
        await client.post(
            SLO_BASE,
            json={"name": "SLO Del S", "metric_name": "cpu", "service_id": service_id},
        )
    ).json()
    await client.patch(f"{SLO_BASE}/{slo['id']}", json={"state": "suspended"})
    resp = await client.delete(f"{SLO_BASE}/{slo['id']}")
    assert resp.status_code == 204


# ════════════════════════════════════════════════════════════════════════════════
# Auto-violation detection
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_completing_measurement_above_threshold_violates_slo(client):
    """Completing a measurement with value > threshold (direction=above) violates the SLO."""
    service_id = await _create_active_service(client)

    # SLO: latency_ms must stay BELOW 100 ms (direction=above triggers if > 100)
    slo = (
        await client.post(
            SLO_BASE,
            json={
                "name": "Latency SLO",
                "metric_name": "latency_ms",
                "threshold_value": 100.0,
                "direction": "above",
                "service_id": service_id,
            },
        )
    ).json()
    assert slo["state"] == "active"

    # Measurement reporting 150 ms latency → breach
    m = (
        await client.post(
            MEASUREMENT_BASE,
            json={"name": "Latency Probe", "metric_name": "latency_ms", "service_id": service_id},
        )
    ).json()
    await client.patch(f"{MEASUREMENT_BASE}/{m['id']}", json={"state": "completed", "metric_value": 150.0})

    # SLO should now be violated
    slo_resp = await client.get(f"{SLO_BASE}/{slo['id']}")
    assert slo_resp.json()["state"] == "violated"

    # Violation event should have been published
    events = EventBus.get_events(10)
    violation_events = [e for e in events if e.event_type == "ServiceLevelObjectiveViolationEvent"]
    assert len(violation_events) == 1


@pytest.mark.asyncio
async def test_completing_measurement_below_threshold_does_not_violate_slo(client):
    """Completing a measurement with value <= threshold (direction=above) does NOT violate."""
    service_id = await _create_active_service(client)

    slo = (
        await client.post(
            SLO_BASE,
            json={
                "name": "Latency SLO OK",
                "metric_name": "latency_ms",
                "threshold_value": 100.0,
                "direction": "above",
                "service_id": service_id,
            },
        )
    ).json()

    m = (
        await client.post(
            MEASUREMENT_BASE,
            json={"name": "Latency OK Probe", "metric_name": "latency_ms", "service_id": service_id},
        )
    ).json()
    await client.patch(f"{MEASUREMENT_BASE}/{m['id']}", json={"state": "completed", "metric_value": 50.0})

    # SLO should remain active
    slo_resp = await client.get(f"{SLO_BASE}/{slo['id']}")
    assert slo_resp.json()["state"] == "active"


@pytest.mark.asyncio
async def test_completing_measurement_below_direction_threshold_violates_slo(client):
    """Completing a measurement with value < threshold (direction=below) violates the SLO."""
    service_id = await _create_active_service(client)

    # SLO: availability must stay ABOVE 99.5% (direction=below triggers if < 99.5)
    slo = (
        await client.post(
            SLO_BASE,
            json={
                "name": "Availability SLO",
                "metric_name": "availability_pct",
                "threshold_value": 99.5,
                "direction": "below",
                "service_id": service_id,
            },
        )
    ).json()

    m = (
        await client.post(
            MEASUREMENT_BASE,
            json={
                "name": "Availability Probe",
                "metric_name": "availability_pct",
                "service_id": service_id,
            },
        )
    ).json()
    # Report 98% availability — below the 99.5% threshold
    await client.patch(
        f"{MEASUREMENT_BASE}/{m['id']}", json={"state": "completed", "metric_value": 98.0}
    )

    slo_resp = await client.get(f"{SLO_BASE}/{slo['id']}")
    assert slo_resp.json()["state"] == "violated"


@pytest.mark.asyncio
async def test_failing_measurement_does_not_trigger_slo_check(client):
    """Transitioning a measurement to 'failed' must NOT trigger SLO violation check."""
    service_id = await _create_active_service(client)

    slo = (
        await client.post(
            SLO_BASE,
            json={
                "name": "SLO No Trigger",
                "metric_name": "cpu_pct",
                "threshold_value": 80.0,
                "direction": "above",
                "service_id": service_id,
            },
        )
    ).json()

    m = (
        await client.post(
            MEASUREMENT_BASE,
            json={"name": "CPU Probe", "metric_name": "cpu_pct", "service_id": service_id},
        )
    ).json()
    # Fail the measurement (no metric_value applied, SLO check must not fire)
    await client.patch(f"{MEASUREMENT_BASE}/{m['id']}", json={"state": "failed"})

    # SLO must remain active
    slo_resp = await client.get(f"{SLO_BASE}/{slo['id']}")
    assert slo_resp.json()["state"] == "active"
