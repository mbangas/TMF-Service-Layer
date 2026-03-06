"""Unit tests for the OrderService business logic.

These tests mock the repository layer so no database is required.
Run with: pytest src/order/tests/test_order_service.py -v
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.order.models.orm import ServiceOrderOrm
from src.order.models.schemas import ServiceOrderCreate, ServiceOrderPatch
from src.order.repositories.service_order_repo import ServiceOrderRepository
from src.order.services.order_service import OrderService
from src.shared.events.bus import EventBus


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_orm(
    order_id: str = "test-id",
    state: str = "acknowledged",
    completion_date=None,
) -> ServiceOrderOrm:
    """Build a minimal ServiceOrderOrm for testing."""
    orm = ServiceOrderOrm(
        id=order_id,
        href=f"/tmf-api/serviceOrdering/v4/serviceOrder/{order_id}",
        name="Test Order",
        state=state,
        order_date=datetime.now(tz=timezone.utc),
        completion_date=completion_date,
    )
    orm.order_item = []
    return orm


def make_service(repo: ServiceOrderRepository) -> OrderService:
    """Build an OrderService wired to the given mock repo."""
    return OrderService(repo)


def make_repo(**kwargs) -> MagicMock:
    """Return a MagicMock repo with sensible async defaults."""
    repo = MagicMock(spec=ServiceOrderRepository)
    for attr, val in kwargs.items():
        getattr(repo, attr).return_value = val
    return repo


# ── create_order ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_order_forces_acknowledged_state():
    """create_order must always set state='acknowledged' regardless of input."""
    orm = make_orm(state="acknowledged")
    repo = MagicMock(spec=ServiceOrderRepository)
    repo.create = AsyncMock(return_value=orm)

    EventBus.clear()
    service = make_service(repo)
    data = ServiceOrderCreate(name="Test", order_item=[])
    result = await service.create_order(data)

    assert result.state == "acknowledged"
    called_state = repo.create.call_args[1]["state"]
    assert called_state == "acknowledged"


@pytest.mark.asyncio
async def test_create_order_sets_order_date():
    """create_order must supply a non-None order_date to the repo."""
    orm = make_orm()
    orm.order_date = datetime.now(tz=timezone.utc)
    repo = MagicMock(spec=ServiceOrderRepository)
    repo.create = AsyncMock(return_value=orm)

    EventBus.clear()
    service = make_service(repo)
    data = ServiceOrderCreate(name="Test", order_item=[])
    await service.create_order(data)

    called_order_date = repo.create.call_args[1]["order_date"]
    assert called_order_date is not None
    assert isinstance(called_order_date, datetime)


@pytest.mark.asyncio
async def test_create_order_publishes_create_event():
    """create_order must publish exactly one ServiceOrderCreateEvent."""
    orm = make_orm()
    repo = MagicMock(spec=ServiceOrderRepository)
    repo.create = AsyncMock(return_value=orm)

    EventBus.clear()
    service = make_service(repo)
    data = ServiceOrderCreate(name="Test", order_item=[])
    await service.create_order(data)

    events = EventBus.get_events()
    assert len(events) == 1
    assert events[0].event_type == "ServiceOrderCreateEvent"


# ── patch_order ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_publishes_state_change_event():
    """patch_order must publish a ServiceOrderStateChangeEvent when state changes."""
    orm_before = make_orm(state="acknowledged")
    orm_after  = make_orm(state="inProgress")
    repo = MagicMock(spec=ServiceOrderRepository)
    repo.get_by_id = AsyncMock(side_effect=[orm_before, orm_after])
    repo.patch = AsyncMock(return_value=orm_after)

    EventBus.clear()
    service = make_service(repo)
    data = ServiceOrderPatch(state="inProgress")
    await service.patch_order("test-id", data)

    events = EventBus.get_events()
    assert any(e.event_type == "ServiceOrderStateChangeEvent" for e in events)


@pytest.mark.asyncio
async def test_patch_sets_completion_date_on_terminal():
    """patch_order must set completion_date when transitioning to a terminal state."""
    orm_before = make_orm(state="inProgress")
    orm_after  = make_orm(state="completed")
    repo = MagicMock(spec=ServiceOrderRepository)
    repo.get_by_id = AsyncMock(side_effect=[orm_before, orm_after])
    repo.patch = AsyncMock(return_value=orm_after)

    EventBus.clear()
    service = make_service(repo)
    data = ServiceOrderPatch(state="completed")
    await service.patch_order("test-id", data)

    # The service sets completion_date directly on the existing orm object
    assert orm_before.completion_date is not None


@pytest.mark.asyncio
async def test_patch_does_not_set_completion_date_on_non_terminal():
    """patch_order must NOT set completion_date for non-terminal transitions."""
    orm_before = make_orm(state="acknowledged")
    orm_after  = make_orm(state="inProgress")
    repo = MagicMock(spec=ServiceOrderRepository)
    repo.get_by_id = AsyncMock(side_effect=[orm_before, orm_after])
    repo.patch = AsyncMock(return_value=orm_after)

    EventBus.clear()
    service = make_service(repo)
    data = ServiceOrderPatch(state="inProgress")
    await service.patch_order("test-id", data)

    assert orm_before.completion_date is None


# ── delete_order ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_cancelled_succeeds():
    """delete_order must succeed for a cancelled order."""
    orm = make_orm(state="cancelled")
    repo = MagicMock(spec=ServiceOrderRepository)
    repo.get_by_id = AsyncMock(return_value=orm)
    repo.delete = AsyncMock(return_value=True)

    service = make_service(repo)
    await service.delete_order("test-id")  # should not raise

    repo.delete.assert_called_once_with("test-id")


@pytest.mark.asyncio
async def test_delete_inprogress_raises_422():
    """delete_order must raise 422 for an inProgress order."""
    from fastapi import HTTPException

    orm = make_orm(state="inProgress")
    repo = MagicMock(spec=ServiceOrderRepository)
    repo.get_by_id = AsyncMock(return_value=orm)

    service = make_service(repo)
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_order("test-id")

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_delete_nonexistent_raises_404():
    """delete_order must raise 404 if the order does not exist."""
    from fastapi import HTTPException

    repo = MagicMock(spec=ServiceOrderRepository)
    repo.get_by_id = AsyncMock(return_value=None)

    service = make_service(repo)
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_order("ghost-id")

    assert exc_info.value.status_code == 404


# ── Parametric lifecycle transition matrix ────────────────────────────────────

VALID_TRANSITIONS = [
    ("acknowledged", "inProgress"),
    ("acknowledged", "cancelled"),
    ("inProgress",   "completed"),
    ("inProgress",   "failed"),
    ("inProgress",   "cancelled"),
]

INVALID_TRANSITIONS = [
    ("acknowledged", "completed"),
    ("acknowledged", "failed"),
    ("inProgress",   "acknowledged"),
    ("completed",    "inProgress"),
    ("completed",    "cancelled"),
    ("failed",       "inProgress"),
    ("cancelled",    "acknowledged"),
    ("cancelled",    "inProgress"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("from_state,to_state", VALID_TRANSITIONS)
async def test_valid_lifecycle_transitions(from_state, to_state):
    """Valid state transitions must not raise."""
    orm_before = make_orm(state=from_state)
    orm_after  = make_orm(state=to_state)
    repo = MagicMock(spec=ServiceOrderRepository)
    repo.get_by_id = AsyncMock(side_effect=[orm_before, orm_after])
    repo.patch = AsyncMock(return_value=orm_after)

    EventBus.clear()
    service = make_service(repo)
    data = ServiceOrderPatch(state=to_state)
    result = await service.patch_order("test-id", data)
    assert result.state == to_state


@pytest.mark.asyncio
@pytest.mark.parametrize("from_state,to_state", INVALID_TRANSITIONS)
async def test_invalid_lifecycle_transitions(from_state, to_state):
    """Invalid state transitions must raise HTTPException 422."""
    from fastapi import HTTPException

    orm = make_orm(state=from_state)
    repo = MagicMock(spec=ServiceOrderRepository)
    repo.get_by_id = AsyncMock(return_value=orm)

    service = make_service(repo)
    data = ServiceOrderPatch(state=to_state)
    with pytest.raises(HTTPException) as exc_info:
        await service.patch_order("test-id", data)

    assert exc_info.value.status_code == 422
