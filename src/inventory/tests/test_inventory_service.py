"""Unit tests for InventoryService business logic.

These tests mock the repository layer so no database is required.
Run with: pytest src/inventory/tests/test_inventory_service.py -v
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.inventory.models.orm import ServiceOrm
from src.inventory.models.schemas import ServiceCreate, ServicePatch
from src.inventory.repositories.service_repo import ServiceRepository
from src.inventory.services.inventory_service import InventoryService
from src.shared.events.bus import EventBus


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_orm(
    service_id: str = "test-id",
    state: str = "inactive",
    name: str = "Test Service",
) -> ServiceOrm:
    """Build a minimal ServiceOrm for testing."""
    orm = ServiceOrm(
        id=service_id,
        href=f"/tmf-api/serviceInventory/v4/service/{service_id}",
        name=name,
        state=state,
    )
    orm.service_characteristic = []
    return orm


def make_repo(**kwargs) -> MagicMock:
    """Return a MagicMock repo with sensible async defaults."""
    repo = MagicMock(spec=ServiceRepository)
    for attr, val in kwargs.items():
        getattr(repo, attr).return_value = val
    return repo


def make_service(repo: ServiceRepository) -> InventoryService:
    """Construct an InventoryService wired to the given mock repo."""
    return InventoryService(repo)


# ── create_service ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_service_defaults_inactive_state():
    """ServiceCreate with default state should produce an 'inactive' service."""
    orm = make_orm(state="inactive")
    repo = make_repo()
    repo.create = AsyncMock(return_value=orm)

    EventBus.clear()
    svc = make_service(repo)
    data = ServiceCreate(name="Test", state="inactive")
    result = await svc.create_service(data)

    assert result.state == "inactive"


@pytest.mark.asyncio
async def test_create_service_publishes_create_event():
    """create_service must publish exactly one ServiceCreateEvent."""
    orm = make_orm()
    repo = make_repo()
    repo.create = AsyncMock(return_value=orm)

    EventBus.clear()
    svc = make_service(repo)
    data = ServiceCreate(name="Test")
    await svc.create_service(data)

    events = EventBus.get_events(limit=10)
    assert len(events) == 1
    assert events[0].event_type == "ServiceCreateEvent"


@pytest.mark.asyncio
async def test_create_service_rejects_terminated_initial_state():
    """Creating a service with state='terminated' must raise 422."""
    from fastapi import HTTPException

    repo = make_repo()
    svc = make_service(repo)
    data = ServiceCreate(name="Bad", state="terminated")

    with pytest.raises(HTTPException) as exc_info:
        await svc.create_service(data)

    assert exc_info.value.status_code == 422
    assert "terminated" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_service_rejects_unknown_state():
    """Creating a service with an unknown state must raise 422."""
    from fastapi import HTTPException

    repo = make_repo()
    svc = make_service(repo)
    data = ServiceCreate(name="Bad", state="nonexistent")

    with pytest.raises(HTTPException) as exc_info:
        await svc.create_service(data)

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_create_service_with_active_state_succeeds():
    """Creating a service with state='active' (e.g. auto-provisioned) is valid."""
    orm = make_orm(state="active")
    repo = make_repo()
    repo.create = AsyncMock(return_value=orm)

    EventBus.clear()
    svc = make_service(repo)
    data = ServiceCreate(name="Auto-provisioned", state="active")
    result = await svc.create_service(data)

    assert result.state == "active"


# ── patch_service — valid transitions ─────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("from_state,to_state", [
    ("feasibilityChecked", "designed"),
    ("designed",           "reserved"),
    ("reserved",           "inactive"),
    ("inactive",           "active"),
    ("active",             "terminated"),
])
async def test_patch_service_valid_transitions(from_state, to_state):
    """Each valid sequential state transition must succeed."""
    existing = make_orm(state=from_state)
    patched  = make_orm(state=to_state)
    repo = make_repo()
    repo.get_by_id = AsyncMock(return_value=existing)
    repo.patch = AsyncMock(return_value=patched)

    EventBus.clear()
    svc = make_service(repo)
    data = ServicePatch(state=to_state)
    result = await svc.patch_service("test-id", data)

    assert result.state == to_state


# ── patch_service — invalid transitions ───────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("from_state,to_state", [
    ("inactive",           "feasibilityChecked"),
    ("active",             "inactive"),
    ("terminated",         "active"),
    ("terminated",         "inactive"),
    ("feasibilityChecked", "active"),
    ("designed",           "terminated"),
    ("inactive",           "terminated"),
])
async def test_patch_service_invalid_transitions(from_state, to_state):
    """Each invalid state transition must raise 422."""
    from fastapi import HTTPException

    existing = make_orm(state=from_state)
    repo = make_repo()
    repo.get_by_id = AsyncMock(return_value=existing)

    svc = make_service(repo)
    data = ServicePatch(state=to_state)

    with pytest.raises(HTTPException) as exc_info:
        await svc.patch_service("test-id", data)

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_patch_service_publishes_state_change_event():
    """patch_service must publish a ServiceStateChangeEvent when state changes."""
    existing = make_orm(state="inactive")
    patched  = make_orm(state="active")
    repo = make_repo()
    repo.get_by_id = AsyncMock(return_value=existing)
    repo.patch = AsyncMock(return_value=patched)

    EventBus.clear()
    svc = make_service(repo)
    await svc.patch_service("test-id", ServicePatch(state="active"))

    events = EventBus.get_events(limit=10)
    assert len(events) == 1
    assert events[0].event_type == "ServiceStateChangeEvent"


@pytest.mark.asyncio
async def test_patch_service_no_event_when_state_unchanged():
    """patch_service must NOT publish an event when no state transition occurs."""
    existing = make_orm(state="inactive")
    patched  = make_orm(state="inactive", name="Updated Name")
    repo = make_repo()
    repo.get_by_id = AsyncMock(return_value=existing)
    repo.patch = AsyncMock(return_value=patched)

    EventBus.clear()
    svc = make_service(repo)
    await svc.patch_service("test-id", ServicePatch(name="Updated Name"))

    events = EventBus.get_events(limit=10)
    assert len(events) == 0


# ── delete_service ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_service_terminated_ok():
    """Deleting a terminated service must succeed without error."""
    orm = make_orm(state="terminated")
    repo = make_repo()
    repo.get_by_id = AsyncMock(return_value=orm)
    repo.delete = AsyncMock(return_value=True)

    svc = make_service(repo)
    await svc.delete_service("test-id")  # should not raise

    repo.delete.assert_called_once_with("test-id")


@pytest.mark.asyncio
async def test_delete_service_inactive_ok():
    """Deleting an inactive service must also succeed."""
    orm = make_orm(state="inactive")
    repo = make_repo()
    repo.get_by_id = AsyncMock(return_value=orm)
    repo.delete = AsyncMock(return_value=True)

    svc = make_service(repo)
    await svc.delete_service("test-id")

    repo.delete.assert_called_once_with("test-id")


@pytest.mark.asyncio
async def test_delete_service_active_raises_422():
    """Deleting an active service must raise 422."""
    from fastapi import HTTPException

    orm = make_orm(state="active")
    repo = make_repo()
    repo.get_by_id = AsyncMock(return_value=orm)

    svc = make_service(repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.delete_service("test-id")

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_delete_service_not_found_raises_404():
    """Deleting a non-existent service must raise 404."""
    from fastapi import HTTPException

    repo = make_repo()
    repo.get_by_id = AsyncMock(return_value=None)

    svc = make_service(repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.delete_service("no-such-id")

    assert exc_info.value.status_code == 404
