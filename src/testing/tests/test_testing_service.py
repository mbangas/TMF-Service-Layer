"""Unit tests for the Testing service layer — TestSpecificationService and ServiceTestService.

These tests mock the repository and dependent service layers so no database
connection is required.

Run with: pytest src/testing/tests/test_testing_service.py -v
"""

from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.inventory.models.orm import ServiceOrm
from src.inventory.repositories.service_repo import ServiceRepository
from src.shared.events.bus import EventBus
from src.testing.models.orm import ServiceTestOrm, ServiceTestSpecificationOrm, TestMeasureOrm
from src.testing.models.schemas import (
    ServiceTestCreate,
    ServiceTestPatch,
    ServiceTestSpecificationCreate,
    ServiceTestSpecificationPatch,
    TestMeasureCreate,
)
from src.testing.repositories.test_repo import ServiceTestRepository
from src.testing.repositories.test_spec_repo import TestSpecificationRepository
from src.testing.services.testing_service import (
    ServiceTestService,
    TestSpecificationService,
    _validate_state_transition,
)


# ── ORM helpers ───────────────────────────────────────────────────────────────

def make_service_orm(service_id: str = "svc-id", state: str = "active") -> ServiceOrm:
    return ServiceOrm(id=service_id, name="Test Service", state=state)


def make_spec_orm(
    spec_id: str = "spec-id",
    state: str = "active",
) -> ServiceTestSpecificationOrm:
    now = datetime.now(tz=timezone.utc)
    return ServiceTestSpecificationOrm(
        id=spec_id,
        href=f"/tmf-api/serviceTest/v4/serviceTestSpecification/{spec_id}",
        name="Test Spec",
        state=state,
        created_at=now,
        updated_at=now,
    )


def make_test_orm(
    test_id: str = "test-id",
    state: str = "planned",
    service_id: str = "svc-id",
) -> ServiceTestOrm:
    now = datetime.now(tz=timezone.utc)
    return ServiceTestOrm(
        id=test_id,
        href=f"/tmf-api/serviceTest/v4/serviceTest/{test_id}",
        name="Test Run",
        state=state,
        service_id=service_id,
        created_at=now,
        updated_at=now,
    )


def make_measure_orm(
    measure_id: str = "measure-id",
    test_id: str = "test-id",
    metric_name: str = "latency_ms",
) -> TestMeasureOrm:
    return TestMeasureOrm(
        id=measure_id,
        service_test_id=test_id,
        metric_name=metric_name,
        metric_value=42.0,
    )


# ── _validate_state_transition ────────────────────────────────────────────────

def test_validate_state_transition_valid_spec():
    """Valid spec transition active→retired should not raise."""
    from src.testing.models.schemas import TEST_SPEC_TRANSITIONS
    _validate_state_transition("active", "retired", TEST_SPEC_TRANSITIONS, "Spec")


def test_validate_state_transition_invalid_spec_raises_422():
    """Invalid spec transition active→obsolete should raise 422."""
    from src.testing.models.schemas import TEST_SPEC_TRANSITIONS
    with pytest.raises(HTTPException) as exc_info:
        _validate_state_transition("active", "obsolete", TEST_SPEC_TRANSITIONS, "Spec")
    assert exc_info.value.status_code == 422
    assert "active" in exc_info.value.detail
    assert "obsolete" in exc_info.value.detail


def test_validate_state_transition_terminal_spec_raises_422():
    """Transition from terminal obsolete state should raise 422."""
    from src.testing.models.schemas import TEST_SPEC_TRANSITIONS
    with pytest.raises(HTTPException) as exc_info:
        _validate_state_transition("obsolete", "active", TEST_SPEC_TRANSITIONS, "Spec")
    assert exc_info.value.status_code == 422
    assert "terminal" in exc_info.value.detail.lower()


def test_validate_test_transitions_valid():
    """Valid test transitions: planned→inProgress, inProgress→completed|failed|cancelled."""
    from src.testing.models.schemas import TEST_TRANSITIONS
    _validate_state_transition("planned", "inProgress", TEST_TRANSITIONS, "Test")
    _validate_state_transition("planned", "cancelled", TEST_TRANSITIONS, "Test")
    _validate_state_transition("inProgress", "completed", TEST_TRANSITIONS, "Test")
    _validate_state_transition("inProgress", "failed", TEST_TRANSITIONS, "Test")
    _validate_state_transition("inProgress", "cancelled", TEST_TRANSITIONS, "Test")


def test_validate_test_planned_to_completed_invalid():
    """planned → completed direct transition is NOT allowed."""
    from src.testing.models.schemas import TEST_TRANSITIONS
    with pytest.raises(HTTPException) as exc_info:
        _validate_state_transition("planned", "completed", TEST_TRANSITIONS, "Test")
    assert exc_info.value.status_code == 422


def test_validate_test_terminal_state_raises_422():
    """Transition from terminal completed state should raise 422."""
    from src.testing.models.schemas import TEST_TRANSITIONS
    with pytest.raises(HTTPException) as exc_info:
        _validate_state_transition("completed", "planned", TEST_TRANSITIONS, "Test")
    assert exc_info.value.status_code == 422
    assert "terminal" in exc_info.value.detail.lower()


# ── TestSpecificationService ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_spec_publishes_event():
    """create_spec should publish exactly one ServiceTestSpecificationCreateEvent."""
    spec_orm = make_spec_orm()
    repo = MagicMock(spec=TestSpecificationRepository)
    repo.create = AsyncMock(return_value=spec_orm)
    catalog_repo = MagicMock(spec=ServiceSpecificationRepository)

    svc = TestSpecificationService(repo=repo, catalog_repo=catalog_repo)
    EventBus.clear()
    await svc.create_spec(ServiceTestSpecificationCreate(name="Latency Spec"))

    events = EventBus.get_events(10)
    assert any(e.event_type == "ServiceTestSpecificationCreateEvent" for e in events)


@pytest.mark.asyncio
async def test_create_spec_with_invalid_service_spec_id_raises_404():
    """create_spec with non-existent service_spec_id should raise 404."""
    repo = MagicMock(spec=TestSpecificationRepository)
    catalog_repo = MagicMock(spec=ServiceSpecificationRepository)
    catalog_repo.get_by_id = AsyncMock(return_value=None)

    svc = TestSpecificationService(repo=repo, catalog_repo=catalog_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.create_spec(
            ServiceTestSpecificationCreate(name="Spec", service_spec_id="no-such")
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_spec_not_found_raises_404():
    """get_spec with unknown ID should raise 404."""
    repo = MagicMock(spec=TestSpecificationRepository)
    repo.get_by_id = AsyncMock(return_value=None)
    catalog_repo = MagicMock(spec=ServiceSpecificationRepository)

    svc = TestSpecificationService(repo=repo, catalog_repo=catalog_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.get_spec("ghost-id")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_patch_spec_invalid_state_transition_raises_422():
    """patch_spec with invalid state transition should raise 422."""
    spec_orm = make_spec_orm(state="active")
    repo = MagicMock(spec=TestSpecificationRepository)
    repo.get_by_id = AsyncMock(return_value=spec_orm)
    catalog_repo = MagicMock(spec=ServiceSpecificationRepository)

    svc = TestSpecificationService(repo=repo, catalog_repo=catalog_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.patch_spec("spec-id", ServiceTestSpecificationPatch(state="obsolete"))
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_delete_spec_active_raises_422():
    """delete_spec in active state should raise 422."""
    spec_orm = make_spec_orm(state="active")
    repo = MagicMock(spec=TestSpecificationRepository)
    repo.get_by_id = AsyncMock(return_value=spec_orm)
    catalog_repo = MagicMock(spec=ServiceSpecificationRepository)

    svc = TestSpecificationService(repo=repo, catalog_repo=catalog_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.delete_spec("spec-id")
    assert exc_info.value.status_code == 422


# ── ServiceTestService ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_test_inactive_service_raises_422():
    """create_test with inactive service should raise 422."""
    repo = MagicMock(spec=ServiceTestRepository)
    service_repo = MagicMock(spec=ServiceRepository)
    service_repo.get_by_id = AsyncMock(return_value=make_service_orm(state="inactive"))
    spec_repo = MagicMock(spec=TestSpecificationRepository)

    svc = ServiceTestService(repo=repo, service_repo=service_repo, spec_repo=spec_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.create_test(ServiceTestCreate(name="Test", service_id="svc-id"))
    assert exc_info.value.status_code == 422
    assert "active" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_create_test_service_not_found_raises_404():
    """create_test with non-existent service_id should raise 404."""
    repo = MagicMock(spec=ServiceTestRepository)
    service_repo = MagicMock(spec=ServiceRepository)
    service_repo.get_by_id = AsyncMock(return_value=None)
    spec_repo = MagicMock(spec=TestSpecificationRepository)

    svc = ServiceTestService(repo=repo, service_repo=service_repo, spec_repo=spec_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.create_test(ServiceTestCreate(name="Test", service_id="ghost"))
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_test_with_obsolete_spec_raises_422():
    """create_test with an obsolete test spec should raise 422."""
    repo = MagicMock(spec=ServiceTestRepository)
    service_repo = MagicMock(spec=ServiceRepository)
    service_repo.get_by_id = AsyncMock(return_value=make_service_orm(state="active"))
    spec_repo = MagicMock(spec=TestSpecificationRepository)
    spec_repo.get_by_id = AsyncMock(return_value=make_spec_orm(state="obsolete"))

    svc = ServiceTestService(repo=repo, service_repo=service_repo, spec_repo=spec_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.create_test(
            ServiceTestCreate(name="Test", service_id="svc-id", test_spec_id="spec-id")
        )
    assert exc_info.value.status_code == 422
    assert "obsolete" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_create_test_publishes_create_event():
    """create_test should publish ServiceTestCreateEvent."""
    test_orm = make_test_orm()
    repo = MagicMock(spec=ServiceTestRepository)
    repo.create = AsyncMock(return_value=test_orm)
    repo.get_measures = AsyncMock(return_value=[])
    service_repo = MagicMock(spec=ServiceRepository)
    service_repo.get_by_id = AsyncMock(return_value=make_service_orm(state="active"))
    spec_repo = MagicMock(spec=TestSpecificationRepository)

    svc = ServiceTestService(repo=repo, service_repo=service_repo, spec_repo=spec_repo)
    EventBus.clear()
    await svc.create_test(ServiceTestCreate(name="Test", service_id="svc-id"))
    events = EventBus.get_events(10)
    assert any(e.event_type == "ServiceTestCreateEvent" for e in events)


@pytest.mark.asyncio
async def test_patch_test_to_completed_publishes_complete_event():
    """patch_test to completed should publish ServiceTestCompleteEvent."""
    test_orm = make_test_orm(state="inProgress")
    patched_orm = make_test_orm(state="completed")
    repo = MagicMock(spec=ServiceTestRepository)
    repo.get_by_id = AsyncMock(return_value=test_orm)
    repo.patch = AsyncMock(return_value=patched_orm)
    repo.get_measures = AsyncMock(return_value=[])
    service_repo = MagicMock(spec=ServiceRepository)
    spec_repo = MagicMock(spec=TestSpecificationRepository)

    svc = ServiceTestService(repo=repo, service_repo=service_repo, spec_repo=spec_repo)
    EventBus.clear()
    await svc.patch_test("test-id", ServiceTestPatch(state="completed"))
    events = EventBus.get_events(10)
    assert any(e.event_type == "ServiceTestCompleteEvent" for e in events)


@pytest.mark.asyncio
async def test_patch_test_to_failed_publishes_failed_event():
    """patch_test to failed should publish ServiceTestFailedEvent."""
    test_orm = make_test_orm(state="inProgress")
    patched_orm = make_test_orm(state="failed")
    repo = MagicMock(spec=ServiceTestRepository)
    repo.get_by_id = AsyncMock(return_value=test_orm)
    repo.patch = AsyncMock(return_value=patched_orm)
    repo.get_measures = AsyncMock(return_value=[])
    service_repo = MagicMock(spec=ServiceRepository)
    spec_repo = MagicMock(spec=TestSpecificationRepository)

    svc = ServiceTestService(repo=repo, service_repo=service_repo, spec_repo=spec_repo)
    EventBus.clear()
    await svc.patch_test("test-id", ServiceTestPatch(state="failed"))
    events = EventBus.get_events(10)
    assert any(e.event_type == "ServiceTestFailedEvent" for e in events)


@pytest.mark.asyncio
async def test_patch_test_invalid_transition_raises_422():
    """patch_test with invalid transition (planned→completed) should raise 422."""
    test_orm = make_test_orm(state="planned")
    repo = MagicMock(spec=ServiceTestRepository)
    repo.get_by_id = AsyncMock(return_value=test_orm)
    service_repo = MagicMock(spec=ServiceRepository)
    spec_repo = MagicMock(spec=TestSpecificationRepository)

    svc = ServiceTestService(repo=repo, service_repo=service_repo, spec_repo=spec_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.patch_test("test-id", ServiceTestPatch(state="completed"))
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_delete_test_planned_raises_422():
    """delete_test in planned state should raise 422."""
    test_orm = make_test_orm(state="planned")
    repo = MagicMock(spec=ServiceTestRepository)
    repo.get_by_id = AsyncMock(return_value=test_orm)
    service_repo = MagicMock(spec=ServiceRepository)
    spec_repo = MagicMock(spec=TestSpecificationRepository)

    svc = ServiceTestService(repo=repo, service_repo=service_repo, spec_repo=spec_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.delete_test("test-id")
    assert exc_info.value.status_code == 422


# ── TestMeasure guard ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_measure_not_inprogress_raises_422():
    """add_measure on a non-inProgress test should raise 422."""
    test_orm = make_test_orm(state="planned")
    repo = MagicMock(spec=ServiceTestRepository)
    repo.get_by_id = AsyncMock(return_value=test_orm)
    service_repo = MagicMock(spec=ServiceRepository)
    spec_repo = MagicMock(spec=TestSpecificationRepository)

    svc = ServiceTestService(repo=repo, service_repo=service_repo, spec_repo=spec_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.add_measure("test-id", TestMeasureCreate(metric_name="cpu_pct"))
    assert exc_info.value.status_code == 422
    assert "inProgress" in exc_info.value.detail


@pytest.mark.asyncio
async def test_add_measure_invalid_result_raises_422():
    """add_measure with invalid result value should raise 422."""
    test_orm = make_test_orm(state="inProgress")
    repo = MagicMock(spec=ServiceTestRepository)
    repo.get_by_id = AsyncMock(return_value=test_orm)
    service_repo = MagicMock(spec=ServiceRepository)
    spec_repo = MagicMock(spec=TestSpecificationRepository)

    svc = ServiceTestService(repo=repo, service_repo=service_repo, spec_repo=spec_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.add_measure(
            "test-id", TestMeasureCreate(metric_name="cpu_pct", result="unknown")
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_add_measure_test_not_found_raises_404():
    """add_measure with unknown test_id should raise 404."""
    repo = MagicMock(spec=ServiceTestRepository)
    repo.get_by_id = AsyncMock(return_value=None)
    service_repo = MagicMock(spec=ServiceRepository)
    spec_repo = MagicMock(spec=TestSpecificationRepository)

    svc = ServiceTestService(repo=repo, service_repo=service_repo, spec_repo=spec_repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.add_measure(
            "ghost-id", TestMeasureCreate(metric_name="latency_ms")
        )
    assert exc_info.value.status_code == 404
