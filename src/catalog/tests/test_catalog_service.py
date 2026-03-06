"""Unit tests for CatalogService — business logic and lifecycle state machine.

Uses ``unittest.mock`` to replace the repository so tests are fast and
database-independent.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.catalog.models.orm import ServiceSpecificationOrm
from src.catalog.models.schemas import (
    ServiceSpecificationCreate,
    ServiceSpecificationPatch,
    ServiceSpecificationUpdate,
)
from src.catalog.services.catalog_service import CatalogService


# ── Fixtures ───────────────────────────────────────────────────────────────────

def make_orm(
    *,
    id: str = "spec-001",
    name: str = "Test Spec",
    lifecycle_status: str = "draft",
    version: str = "1.0",
    is_bundle: bool = False,
    description: str | None = None,
) -> ServiceSpecificationOrm:
    """Return a minimal ORM mock that mimics a ServiceSpecificationOrm row."""
    orm = MagicMock(spec=ServiceSpecificationOrm)
    orm.id = id
    orm.href = f"/tmf-api/serviceCatalogManagement/v4/serviceSpecification/{id}"
    orm.name = name
    orm.lifecycle_status = lifecycle_status
    orm.version = version
    orm.is_bundle = is_bundle
    orm.description = description
    orm.last_update = None
    orm.type = None
    orm.base_type = None
    orm.schema_location = None
    orm.created_at = None
    orm.updated_at = None
    orm.service_spec_characteristic = []
    orm.service_level_specification = []
    return orm


@pytest.fixture
def mock_repo():
    """Return an AsyncMock repository."""
    return AsyncMock()


@pytest.fixture
def service(mock_repo):
    """Return a CatalogService wired to the mock repository."""
    return CatalogService(repo=mock_repo)


# ── list_specifications ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_specifications_delegates_to_repo(service, mock_repo):
    """list_specifications should return mapped responses from the repo."""
    orm = make_orm(name="Spec A")
    mock_repo.get_all.return_value = ([orm], 1)
    items, total = await service.list_specifications(offset=0, limit=10)
    mock_repo.get_all.assert_awaited_once_with(offset=0, limit=10, lifecycle_status=None)
    assert total == 1
    assert items[0].name == "Spec A"


@pytest.mark.asyncio
async def test_list_specifications_passes_status_filter(service, mock_repo):
    """list_specifications should forward the lifecycle_status filter."""
    mock_repo.get_all.return_value = ([], 0)
    await service.list_specifications(lifecycle_status="active")
    mock_repo.get_all.assert_awaited_once_with(
        offset=0, limit=20, lifecycle_status="active"
    )


# ── get_specification ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_specification_returns_response(service, mock_repo):
    """get_specification should return the mapped response for a valid ID."""
    orm = make_orm(id="abc-123", name="Found It")
    mock_repo.get_by_id.return_value = orm
    result = await service.get_specification("abc-123")
    assert result.id == "abc-123"
    assert result.name == "Found It"


@pytest.mark.asyncio
async def test_get_specification_not_found_raises_404(service, mock_repo):
    """get_specification should raise 404 when the repo returns None."""
    mock_repo.get_by_id.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.get_specification("missing")
    assert exc_info.value.status_code == 404


# ── create_specification ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_specification_draft_succeeds(service, mock_repo):
    """create_specification should succeed when status is 'draft'."""
    orm = make_orm(name="New Spec", lifecycle_status="draft")
    mock_repo.create.return_value = orm
    data = ServiceSpecificationCreate(name="New Spec", lifecycle_status="draft")
    result = await service.create_specification(data)
    mock_repo.create.assert_awaited_once()
    assert result.lifecycle_status == "draft"


@pytest.mark.asyncio
async def test_create_specification_active_succeeds(service, mock_repo):
    """create_specification should succeed when status is 'active'."""
    orm = make_orm(name="Active Spec", lifecycle_status="active")
    mock_repo.create.return_value = orm
    data = ServiceSpecificationCreate(name="Active Spec", lifecycle_status="active")
    result = await service.create_specification(data)
    assert result.lifecycle_status == "active"


@pytest.mark.asyncio
async def test_create_specification_obsolete_raises_422(service, mock_repo):
    """create_specification should reject obsolete as an initial status."""
    data = ServiceSpecificationCreate(name="Bad Status", lifecycle_status="obsolete")
    with pytest.raises(HTTPException) as exc_info:
        await service.create_specification(data)
    assert exc_info.value.status_code == 422
    mock_repo.create.assert_not_awaited()


# ── update_specification ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_specification_valid_transition(service, mock_repo):
    """update_specification should allow draft → active."""
    existing = make_orm(lifecycle_status="draft")
    updated_orm = make_orm(lifecycle_status="active")
    mock_repo.get_by_id.return_value = existing
    mock_repo.update.return_value = updated_orm
    data = ServiceSpecificationUpdate(
        name="Updated", lifecycle_status="active"
    )
    result = await service.update_specification("spec-001", data)
    assert result.lifecycle_status == "active"


@pytest.mark.asyncio
async def test_update_specification_invalid_transition_raises_422(service, mock_repo):
    """update_specification should block retired → active."""
    existing = make_orm(lifecycle_status="retired")
    mock_repo.get_by_id.return_value = existing
    data = ServiceSpecificationUpdate(name="Bad Move", lifecycle_status="active")
    with pytest.raises(HTTPException) as exc_info:
        await service.update_specification("spec-001", data)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_update_specification_not_found_raises_404(service, mock_repo):
    """update_specification should raise 404 when spec not found."""
    mock_repo.get_by_id.return_value = None
    data = ServiceSpecificationUpdate(name="Ghost", lifecycle_status="draft")
    with pytest.raises(HTTPException) as exc_info:
        await service.update_specification("ghost", data)
    assert exc_info.value.status_code == 404


# ── patch_specification ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_specification_no_status_change(service, mock_repo):
    """patch_specification should apply name change without validating lifecycle."""
    existing = make_orm(lifecycle_status="active")
    patched_orm = make_orm(name="Patched Name", lifecycle_status="active")
    mock_repo.get_by_id.return_value = existing
    mock_repo.patch.return_value = patched_orm
    data = ServiceSpecificationPatch(name="Patched Name")
    result = await service.patch_specification("spec-001", data)
    assert result.name == "Patched Name"


@pytest.mark.asyncio
async def test_patch_specification_invalid_transition_raises_422(service, mock_repo):
    """patch_specification should reject invalid lifecycle transition."""
    existing = make_orm(lifecycle_status="draft")
    mock_repo.get_by_id.return_value = existing
    data = ServiceSpecificationPatch(lifecycle_status="retired")
    with pytest.raises(HTTPException) as exc_info:
        await service.patch_specification("spec-001", data)
    assert exc_info.value.status_code == 422


# ── delete_specification ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_draft_spec_succeeds(service, mock_repo):
    """delete_specification should delete a draft spec without error."""
    existing = make_orm(lifecycle_status="draft")
    mock_repo.get_by_id.return_value = existing
    mock_repo.delete.return_value = True
    await service.delete_specification("spec-001")
    mock_repo.delete.assert_awaited_once_with("spec-001")


@pytest.mark.asyncio
async def test_delete_retired_spec_succeeds(service, mock_repo):
    """delete_specification should delete a retired spec."""
    existing = make_orm(lifecycle_status="retired")
    mock_repo.get_by_id.return_value = existing
    mock_repo.delete.return_value = True
    await service.delete_specification("spec-001")
    mock_repo.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_active_spec_raises_422(service, mock_repo):
    """delete_specification should reject active specifications."""
    existing = make_orm(lifecycle_status="active")
    mock_repo.get_by_id.return_value = existing
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_specification("spec-001")
    assert exc_info.value.status_code == 422
    mock_repo.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_obsolete_spec_raises_422(service, mock_repo):
    """delete_specification should reject obsolete specifications."""
    existing = make_orm(lifecycle_status="obsolete")
    mock_repo.get_by_id.return_value = existing
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_specification("spec-001")
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_delete_nonexistent_raises_404(service, mock_repo):
    """delete_specification should raise 404 for unknown IDs."""
    mock_repo.get_by_id.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_specification("no-id")
    assert exc_info.value.status_code == 404


# ── Lifecycle state machine edge cases ────────────────────────────────────────

@pytest.mark.parametrize("from_status,to_status,expected_code", [
    ("draft",    "active",   200),
    ("draft",    "draft",    200),
    ("active",   "obsolete", 200),
    ("active",   "retired",  200),
    ("obsolete", "retired",  200),
    ("retired",  "retired",  200),
    # Invalid
    ("draft",    "retired",  422),
    ("draft",    "obsolete", 422),
    ("active",   "draft",    422),
    ("obsolete", "active",   422),
    ("obsolete", "draft",    422),
    ("retired",  "active",   422),
    ("retired",  "draft",    422),
    ("retired",  "obsolete", 422),
])
@pytest.mark.asyncio
async def test_lifecycle_transition_matrix(
    service, mock_repo, from_status, to_status, expected_code
):
    """Verify all lifecycle transitions against the allowed matrix."""
    existing = make_orm(lifecycle_status=from_status)
    patched_orm = make_orm(lifecycle_status=to_status)
    mock_repo.get_by_id.return_value = existing
    mock_repo.patch.return_value = patched_orm

    data = ServiceSpecificationPatch(lifecycle_status=to_status)

    if expected_code == 422:
        with pytest.raises(HTTPException) as exc_info:
            await service.patch_specification("spec-001", data)
        assert exc_info.value.status_code == 422
    else:
        result = await service.patch_specification("spec-001", data)
        assert result.lifecycle_status == to_status
