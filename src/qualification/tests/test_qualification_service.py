"""Unit tests for QualificationService business logic.

These tests mock the repository and spec repository layers so no database
is required.
Run with: pytest src/qualification/tests/test_qualification_service.py -v
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.catalog.models.orm import ServiceSpecificationOrm
from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.qualification.models.orm import ServiceQualificationOrm
from src.qualification.models.schemas import (
    ServiceQualificationCreate,
    ServiceQualificationPatch,
)
from src.qualification.repositories.qualification_repo import QualificationRepository
from src.qualification.services.qualification_service import QualificationService
from src.shared.events.bus import EventBus


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_spec_orm(spec_id: str = "spec-id") -> ServiceSpecificationOrm:
    """Build a minimal ServiceSpecificationOrm for testing."""
    orm = ServiceSpecificationOrm(id=spec_id, name="Test Spec", lifecycle_status="active")
    orm.service_spec_characteristic = []
    orm.service_level_specifications = []
    return orm


def make_qualification_orm(
    qual_id: str = "qual-id",
    state: str = "acknowledged",
) -> ServiceQualificationOrm:
    """Build a minimal ServiceQualificationOrm for testing."""
    orm = ServiceQualificationOrm(
        id=qual_id,
        href=f"/tmf-api/serviceQualificationManagement/v4/checkServiceQualification/{qual_id}",
        name="Test Qualification",
        state=state,
    )
    orm.items = []
    return orm


def make_qualification_service(
    spec_repo_overrides: dict | None = None,
    qual_repo_overrides: dict | None = None,
) -> tuple[QualificationService, MagicMock, MagicMock]:
    """Build a QualificationService with mocked dependencies.

    Returns:
        Tuple of (QualificationService, mock_qual_repo, mock_spec_repo).
    """
    spec_repo = MagicMock(spec=ServiceSpecificationRepository)
    for attr, val in (spec_repo_overrides or {}).items():
        getattr(spec_repo, attr).return_value = val

    qual_repo = MagicMock(spec=QualificationRepository)
    for attr, val in (qual_repo_overrides or {}).items():
        getattr(qual_repo, attr).return_value = val

    svc = QualificationService(repo=qual_repo, spec_repo=spec_repo)
    return svc, qual_repo, spec_repo


# ── create_qualification ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_qualification_no_items_returns_response():
    """create_qualification with no items creates in acknowledged state."""
    qual_orm = make_qualification_orm(state="acknowledged")

    svc, qual_repo, _ = make_qualification_service()
    qual_repo.create = AsyncMock(return_value=qual_orm)

    EventBus.clear()
    data = ServiceQualificationCreate(name="Simple Check")
    result = await svc.create_qualification(data)

    assert result.state == "acknowledged"
    assert result.name == "Test Qualification"


@pytest.mark.asyncio
async def test_create_qualification_publishes_create_event():
    """create_qualification must publish exactly one ServiceQualificationCreateEvent."""
    qual_orm = make_qualification_orm(state="acknowledged")

    svc, qual_repo, _ = make_qualification_service()
    qual_repo.create = AsyncMock(return_value=qual_orm)

    EventBus.clear()
    data = ServiceQualificationCreate(name="Event Test")
    await svc.create_qualification(data)

    events = EventBus.get_events(10)
    create_events = [e for e in events if e.event_type == "ServiceQualificationCreateEvent"]
    assert len(create_events) == 1


@pytest.mark.asyncio
async def test_create_qualification_valid_spec_ref_resolves():
    """create_qualification with a valid spec ref should succeed."""
    spec_orm = make_spec_orm("spec-123")
    qual_orm = make_qualification_orm(state="acknowledged")

    svc, qual_repo, spec_repo = make_qualification_service()
    spec_repo.get_by_id = AsyncMock(return_value=spec_orm)
    qual_repo.create = AsyncMock(return_value=qual_orm)

    from src.qualification.models.schemas import ServiceQualificationItemCreate

    EventBus.clear()
    data = ServiceQualificationCreate(
        name="Spec Ref Check",
        items=[ServiceQualificationItemCreate(service_spec_id="spec-123")],
    )
    result = await svc.create_qualification(data)
    assert result.state == "acknowledged"
    spec_repo.get_by_id.assert_called_once_with("spec-123")


@pytest.mark.asyncio
async def test_create_qualification_invalid_spec_ref_raises_404():
    """create_qualification with non-existent spec ref must raise 404."""
    from fastapi import HTTPException

    svc, _, spec_repo = make_qualification_service()
    spec_repo.get_by_id = AsyncMock(return_value=None)

    from src.qualification.models.schemas import ServiceQualificationItemCreate

    data = ServiceQualificationCreate(
        name="Bad Spec",
        items=[ServiceQualificationItemCreate(service_spec_id="no-such-spec")],
    )
    with pytest.raises(HTTPException) as exc_info:
        await svc.create_qualification(data)
    assert exc_info.value.status_code == 404


# ── get_qualification ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_qualification_returns_response():
    """get_qualification should return the qualification response."""
    qual_orm = make_qualification_orm()

    svc, qual_repo, _ = make_qualification_service()
    qual_repo.get_by_id = AsyncMock(return_value=qual_orm)

    result = await svc.get_qualification("qual-id")
    assert result.id == "qual-id"


@pytest.mark.asyncio
async def test_get_qualification_not_found_raises_404():
    """get_qualification with unknown ID must raise 404."""
    from fastapi import HTTPException

    svc, qual_repo, _ = make_qualification_service()
    qual_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await svc.get_qualification("bad-id")
    assert exc_info.value.status_code == 404


# ── patch_qualification ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_qualification_valid_transition():
    """patch_qualification with valid transition should return updated response."""
    qual_orm_before = make_qualification_orm(state="acknowledged")
    qual_orm_after = make_qualification_orm(state="inProgress")

    svc, qual_repo, _ = make_qualification_service()
    qual_repo.get_by_id = AsyncMock(return_value=qual_orm_before)
    qual_repo.patch = AsyncMock(return_value=qual_orm_after)

    EventBus.clear()
    data = ServiceQualificationPatch(state="inProgress")
    result = await svc.patch_qualification("qual-id", data)

    assert result.state == "inProgress"
    events = EventBus.get_events(5)
    change_events = [e for e in events if e.event_type == "ServiceQualificationStateChangeEvent"]
    assert len(change_events) == 1


@pytest.mark.asyncio
async def test_patch_qualification_invalid_transition_raises_422():
    """patch_qualification with invalid transition must raise 422."""
    from fastapi import HTTPException

    qual_orm = make_qualification_orm(state="acknowledged")

    svc, qual_repo, _ = make_qualification_service()
    qual_repo.get_by_id = AsyncMock(return_value=qual_orm)

    data = ServiceQualificationPatch(state="accepted")  # acknowledged → accepted is invalid
    with pytest.raises(HTTPException) as exc_info:
        await svc.patch_qualification("qual-id", data)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_patch_qualification_terminal_state_raises_422():
    """patch_qualification from terminal state must raise 422."""
    from fastapi import HTTPException

    qual_orm = make_qualification_orm(state="accepted")

    svc, qual_repo, _ = make_qualification_service()
    qual_repo.get_by_id = AsyncMock(return_value=qual_orm)

    data = ServiceQualificationPatch(state="cancelled")
    with pytest.raises(HTTPException) as exc_info:
        await svc.patch_qualification("qual-id", data)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_patch_qualification_no_state_change_no_event():
    """patch_qualification updating only name must not publish a state-change event."""
    qual_orm = make_qualification_orm(state="acknowledged")

    svc, qual_repo, _ = make_qualification_service()
    qual_repo.get_by_id = AsyncMock(return_value=qual_orm)
    qual_repo.patch = AsyncMock(return_value=qual_orm)

    EventBus.clear()
    data = ServiceQualificationPatch(name="Updated")
    await svc.patch_qualification("qual-id", data)

    events = EventBus.get_events(5)
    change_events = [e for e in events if e.event_type == "ServiceQualificationStateChangeEvent"]
    assert len(change_events) == 0


# ── delete_qualification ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_qualification_accepted_succeeds():
    """delete_qualification on an accepted qualification should call repo.delete."""
    qual_orm = make_qualification_orm(state="accepted")

    svc, qual_repo, _ = make_qualification_service()
    qual_repo.get_by_id = AsyncMock(return_value=qual_orm)
    qual_repo.delete = AsyncMock(return_value=True)

    await svc.delete_qualification("qual-id")
    qual_repo.delete.assert_called_once_with("qual-id")


@pytest.mark.asyncio
async def test_delete_qualification_inprogress_raises_422():
    """delete_qualification on an inProgress qualification must raise 422."""
    from fastapi import HTTPException

    qual_orm = make_qualification_orm(state="inProgress")

    svc, qual_repo, _ = make_qualification_service()
    qual_repo.get_by_id = AsyncMock(return_value=qual_orm)

    with pytest.raises(HTTPException) as exc_info:
        await svc.delete_qualification("qual-id")
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_delete_qualification_not_found_raises_404():
    """delete_qualification with unknown ID must raise 404."""
    from fastapi import HTTPException

    svc, qual_repo, _ = make_qualification_service()
    qual_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await svc.delete_qualification("bad-id")
    assert exc_info.value.status_code == 404
