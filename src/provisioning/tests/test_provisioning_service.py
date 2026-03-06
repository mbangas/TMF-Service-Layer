"""Unit tests for ProvisioningService business logic.

These tests mock the repository and inventory service layers so no database
is required.
Run with: pytest src/provisioning/tests/test_provisioning_service.py -v
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.inventory.models.orm import ServiceOrm
from src.inventory.repositories.service_repo import ServiceRepository
from src.inventory.services.inventory_service import InventoryService
from src.provisioning.models.orm import ServiceActivationJobOrm
from src.provisioning.models.schemas import (
    ServiceActivationJobCreate,
    ServiceActivationJobPatch,
)
from src.provisioning.repositories.activation_job_repo import ActivationJobRepository
from src.provisioning.services.provisioning_service import ProvisioningService
from src.shared.events.bus import EventBus


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_service_orm(service_id: str = "svc-id", state: str = "inactive") -> ServiceOrm:
    """Build a minimal ServiceOrm for testing."""
    orm = ServiceOrm(id=service_id, name="Test Service", state=state)
    orm.service_characteristic = []
    return orm


def make_job_orm(
    job_id: str = "job-id",
    state: str = "accepted",
    job_type: str = "provision",
    service_id: str = "svc-id",
) -> ServiceActivationJobOrm:
    """Build a minimal ServiceActivationJobOrm for testing."""
    orm = ServiceActivationJobOrm(
        id=job_id,
        href=f"/tmf-api/serviceActivationConfiguration/v4/serviceActivationJob/{job_id}",
        name="Test Job",
        job_type=job_type,
        state=state,
        service_id=service_id,
    )
    orm.params = []
    return orm


def make_provisioning_service(
    inventory_repo_overrides: dict | None = None,
    job_repo_overrides: dict | None = None,
) -> tuple[ProvisioningService, MagicMock, MagicMock]:
    """Build a ProvisioningService with mocked dependencies.

    Returns:
        Tuple of (ProvisioningService, mock_job_repo, mock_inventory_svc).
    """
    # Build mock inventory repo + service
    inv_repo = MagicMock(spec=ServiceRepository)
    for attr, val in (inventory_repo_overrides or {}).items():
        getattr(inv_repo, attr).return_value = val
    inv_svc = InventoryService(inv_repo)

    # Build mock job repo
    job_repo = MagicMock(spec=ActivationJobRepository)
    for attr, val in (job_repo_overrides or {}).items():
        getattr(job_repo, attr).return_value = val

    svc = ProvisioningService(repo=job_repo, inventory_service=inv_svc)
    return svc, job_repo, inv_repo


# ── create_job ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_job_valid_returns_response():
    """create_job with valid type and compatible service state returns a response."""
    service_orm = make_service_orm(state="inactive")
    job_orm     = make_job_orm(job_type="provision", state="accepted")

    svc, job_repo, inv_repo = make_provisioning_service()
    inv_repo.get_by_id = AsyncMock(return_value=service_orm)
    job_repo.create    = AsyncMock(return_value=job_orm)

    EventBus.clear()
    data = ServiceActivationJobCreate(name="Test", job_type="provision", service_id="svc-id")
    result = await svc.create_job(data)

    assert result.state == "accepted"
    assert result.job_type == "provision"


@pytest.mark.asyncio
async def test_create_job_publishes_create_event():
    """create_job must publish exactly one ServiceActivationJobCreateEvent."""
    service_orm = make_service_orm(state="inactive")
    job_orm     = make_job_orm()

    svc, job_repo, inv_repo = make_provisioning_service()
    inv_repo.get_by_id = AsyncMock(return_value=service_orm)
    job_repo.create    = AsyncMock(return_value=job_orm)

    EventBus.clear()
    data = ServiceActivationJobCreate(name="Test", job_type="provision", service_id="svc-id")
    await svc.create_job(data)

    events = EventBus.get_events(limit=10)
    assert len(events) == 1
    assert events[0].event_type == "ServiceActivationJobCreateEvent"


@pytest.mark.asyncio
async def test_create_job_invalid_type_raises_422():
    """create_job with unknown job_type must raise 422."""
    from fastapi import HTTPException

    svc, job_repo, inv_repo = make_provisioning_service()

    data = ServiceActivationJobCreate(name="Bad", job_type="explode", service_id="svc-id")
    with pytest.raises(HTTPException) as exc_info:
        await svc.create_job(data)

    assert exc_info.value.status_code == 422
    assert "explode" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_job_service_not_found_raises_404():
    """create_job when the target service does not exist must raise 404."""
    from fastapi import HTTPException

    svc, job_repo, inv_repo = make_provisioning_service()
    inv_repo.get_by_id = AsyncMock(return_value=None)

    data = ServiceActivationJobCreate(name="Test", job_type="provision", service_id="no-such-id")
    with pytest.raises(HTTPException) as exc_info:
        await svc.create_job(data)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("job_type,service_state", [
    ("provision",   "active"),       # provision requires inactive
    ("activate",    "active"),       # activate requires inactive
    ("modify",      "inactive"),     # modify requires active
    ("deactivate",  "inactive"),     # deactivate requires active
    ("terminate",   "terminated"),   # terminate requires active or inactive
])
async def test_create_job_incompatible_service_state_raises_422(job_type, service_state):
    """create_job with incompatible service state must raise 422."""
    from fastapi import HTTPException

    service_orm = make_service_orm(state=service_state)
    svc, job_repo, inv_repo = make_provisioning_service()
    inv_repo.get_by_id = AsyncMock(return_value=service_orm)

    data = ServiceActivationJobCreate(name="Test", job_type=job_type, service_id="svc-id")
    with pytest.raises(HTTPException) as exc_info:
        await svc.create_job(data)

    assert exc_info.value.status_code == 422


# ── patch_job — state transitions ─────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("from_state,to_state", [
    ("accepted", "running"),
    ("accepted", "cancelled"),
    ("running",  "succeeded"),
    ("running",  "failed"),
    ("running",  "cancelled"),
])
async def test_patch_job_valid_transitions(from_state, to_state):
    """Each valid job state transition must succeed."""
    existing = make_job_orm(state=from_state, job_type="provision", service_id="svc-id")
    patched  = make_job_orm(state=to_state,  job_type="provision", service_id="svc-id")

    service_orm = make_service_orm(state="inactive")

    svc, job_repo, inv_repo = make_provisioning_service()
    job_repo.get_by_id = AsyncMock(return_value=existing)
    job_repo.patch     = AsyncMock(return_value=patched)

    # Inventory patch_service is needed for succeeded transitions
    inv_repo.get_by_id = AsyncMock(return_value=service_orm)
    patched_service = make_service_orm(state="active")
    inv_repo.patch     = AsyncMock(return_value=patched_service)

    EventBus.clear()
    data = ServiceActivationJobPatch(state=to_state)
    result = await svc.patch_job("job-id", data)

    assert result.state == to_state


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_state", ["succeeded", "failed", "cancelled"])
async def test_patch_job_invalid_transition_from_terminal_raises_422(terminal_state):
    """Transitioning from a terminal job state must raise 422."""
    from fastapi import HTTPException

    existing = make_job_orm(state=terminal_state)

    svc, job_repo, inv_repo = make_provisioning_service()
    job_repo.get_by_id = AsyncMock(return_value=existing)

    data = ServiceActivationJobPatch(state="running")
    with pytest.raises(HTTPException) as exc_info:
        await svc.patch_job("job-id", data)

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("job_type,expected_service_state", [
    ("provision",  "active"),
    ("activate",   "active"),
    ("modify",     "active"),
    ("deactivate", "inactive"),
    ("terminate",  "terminated"),
])
async def test_patch_job_succeeded_drives_inventory_state(job_type, expected_service_state):
    """On succeeded, the inventory service must receive the correct new service state."""
    running_job   = make_job_orm(state="running", job_type=job_type, service_id="svc-id")
    succeeded_job = make_job_orm(state="succeeded", job_type=job_type, service_id="svc-id")

    # Determine what service state should be before the job succeeds
    pre_state_map = {
        "provision": "inactive", "activate": "inactive", "modify": "active",
        "deactivate": "active", "terminate": "active",
    }
    service_orm = make_service_orm(state=pre_state_map[job_type])
    patched_service = make_service_orm(state=expected_service_state)

    svc, job_repo, inv_repo = make_provisioning_service()
    job_repo.get_by_id = AsyncMock(return_value=running_job)
    job_repo.patch     = AsyncMock(return_value=succeeded_job)
    inv_repo.get_by_id = AsyncMock(return_value=service_orm)
    inv_repo.patch     = AsyncMock(return_value=patched_service)

    EventBus.clear()
    data = ServiceActivationJobPatch(state="succeeded")
    await svc.patch_job("job-id", data)

    # The inventory repo.patch must have been called with the expected state
    inv_repo.patch.assert_called_once()
    call_args = inv_repo.patch.call_args
    # call_args[0][1] is the ServicePatch object
    patch_arg = call_args[0][1]
    assert patch_arg.state == expected_service_state


@pytest.mark.asyncio
async def test_patch_job_succeeded_publishes_state_change_event():
    """patch_job must publish a ServiceActivationJobStateChangeEvent on state change."""
    existing = make_job_orm(state="running", job_type="provision")
    patched  = make_job_orm(state="succeeded", job_type="provision")
    service_orm = make_service_orm(state="inactive")
    patched_service = make_service_orm(state="active")

    svc, job_repo, inv_repo = make_provisioning_service()
    job_repo.get_by_id = AsyncMock(return_value=existing)
    job_repo.patch     = AsyncMock(return_value=patched)
    inv_repo.get_by_id = AsyncMock(return_value=service_orm)
    inv_repo.patch     = AsyncMock(return_value=patched_service)

    EventBus.clear()
    data = ServiceActivationJobPatch(state="succeeded")
    await svc.patch_job("job-id", data)

    events = EventBus.get_events(limit=10)
    state_change_events = [e for e in events if e.event_type == "ServiceActivationJobStateChangeEvent"]
    assert len(state_change_events) >= 1


@pytest.mark.asyncio
async def test_patch_job_not_found_raises_404():
    """patch_job with unknown job ID must raise 404."""
    from fastapi import HTTPException

    svc, job_repo, _ = make_provisioning_service()
    job_repo.get_by_id = AsyncMock(return_value=None)

    data = ServiceActivationJobPatch(state="running")
    with pytest.raises(HTTPException) as exc_info:
        await svc.patch_job("no-such-id", data)

    assert exc_info.value.status_code == 404


# ── delete_job ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["failed", "cancelled"])
async def test_delete_job_deletable_states_succeed(state):
    """Deleting a failed or cancelled job must succeed (no exception)."""
    orm = make_job_orm(state=state)

    svc, job_repo, _ = make_provisioning_service()
    job_repo.get_by_id = AsyncMock(return_value=orm)
    job_repo.delete    = AsyncMock(return_value=True)

    await svc.delete_job("job-id")  # must not raise
    job_repo.delete.assert_called_once_with("job-id")


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["accepted", "running", "succeeded"])
async def test_delete_job_non_deletable_states_raise_422(state):
    """Deleting a job in a non-deletable state must raise 422."""
    from fastapi import HTTPException

    orm = make_job_orm(state=state)

    svc, job_repo, _ = make_provisioning_service()
    job_repo.get_by_id = AsyncMock(return_value=orm)

    with pytest.raises(HTTPException) as exc_info:
        await svc.delete_job("job-id")

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_delete_job_not_found_raises_404():
    """delete_job with unknown ID must raise 404."""
    from fastapi import HTTPException

    svc, job_repo, _ = make_provisioning_service()
    job_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await svc.delete_job("no-such-id")

    assert exc_info.value.status_code == 404
