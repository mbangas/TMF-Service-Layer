"""Business logic and lifecycle state machine for TMF633 ServiceCategory,
ServiceCandidate, and ServiceCatalog resources (TMFC006).

Lifecycle state transitions (same for all three entities):

    draft ──► active ──► obsolete ──► retired
                │                        ▲
                └────────────────────────┘  (active → retired is allowed)
"""

import uuid

from fastapi import HTTPException, status

from src.catalog.models.orm import (
    ServiceCandidateOrm,
    ServiceCatalogOrm,
    ServiceCategoryOrm,
)
from src.catalog.models.schemas import (
    ServiceCandidateCreate,
    ServiceCandidatePatch,
    ServiceCandidateResponse,
    ServiceCandidateUpdate,
    ServiceCatalogCreate,
    ServiceCatalogPatch,
    ServiceCatalogResponse,
    ServiceCatalogUpdate,
    ServiceCategoryCreate,
    ServiceCategoryPatch,
    ServiceCategoryResponse,
    ServiceCategoryRef,
    ServiceCategoryUpdate,
    ServiceCandidateRef,
    ServiceSpecificationRef,
)
from src.catalog.repositories.service_candidate_repo import ServiceCandidateRepository
from src.catalog.repositories.service_catalog_repo import ServiceCatalogRepository
from src.catalog.repositories.service_category_repo import ServiceCategoryRepository
from src.shared.events.bus import EventBus
from src.shared.events.schemas import EventPayload, TMFEvent

# Allowed lifecycle transitions (shared across category, candidate, catalog)
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"draft", "active"},
    "active": {"active", "obsolete", "retired"},
    "obsolete": {"obsolete", "retired"},
    "retired": {"retired"},
}


def _validate_lifecycle_transition(current: str, requested: str) -> None:
    """Raise 422 if the lifecycle transition is not permitted.

    Args:
        current: Current lifecycle status.
        requested: Requested new lifecycle status.

    Raises:
        :class:`fastapi.HTTPException` (422) if the transition is invalid.
    """
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid lifecycle transition from '{current}' to '{requested}'. "
                f"Allowed targets: {sorted(allowed)}"
            ),
        )


# ── ORM → Response mappers ────────────────────────────────────────────────────


def _category_orm_to_response(orm: ServiceCategoryOrm) -> ServiceCategoryResponse:
    """Map a ServiceCategoryOrm to ServiceCategoryResponse."""
    return ServiceCategoryResponse(
        id=orm.id,
        href=orm.href,
        name=orm.name,
        description=orm.description,
        version=orm.version,
        lifecycle_status=orm.lifecycle_status,
        is_root=orm.is_root,
        parent_id=orm.parent_id,
        last_update=orm.last_update,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        type=orm.type,
        base_type=orm.base_type,
        schema_location=orm.schema_location,
        sub_categories=[
            ServiceCategoryRef(id=s.id, href=s.href, name=s.name)
            for s in orm.sub_categories
        ],
        service_candidates=[
            ServiceCandidateRef(id=c.id, href=c.href, name=c.name)
            for c in orm.service_candidates
        ],
    )


def _candidate_orm_to_response(orm: ServiceCandidateOrm) -> ServiceCandidateResponse:
    """Map a ServiceCandidateOrm to ServiceCandidateResponse."""
    spec_ref = None
    if orm.service_specification is not None:
        spec_ref = ServiceSpecificationRef(
            id=orm.service_specification.id,
            href=orm.service_specification.href,
            name=orm.service_specification.name,
            version=orm.service_specification.version,
        )
    return ServiceCandidateResponse(
        id=orm.id,
        href=orm.href,
        name=orm.name,
        description=orm.description,
        version=orm.version,
        lifecycle_status=orm.lifecycle_status,
        last_update=orm.last_update,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        type=orm.type,
        base_type=orm.base_type,
        schema_location=orm.schema_location,
        service_specification=spec_ref,
        categories=[
            ServiceCategoryRef(id=c.id, href=c.href, name=c.name)
            for c in orm.categories
        ],
    )


def _catalog_orm_to_response(orm: ServiceCatalogOrm) -> ServiceCatalogResponse:
    """Map a ServiceCatalogOrm to ServiceCatalogResponse."""
    return ServiceCatalogResponse(
        id=orm.id,
        href=orm.href,
        name=orm.name,
        description=orm.description,
        version=orm.version,
        lifecycle_status=orm.lifecycle_status,
        last_update=orm.last_update,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        type=orm.type,
        base_type=orm.base_type,
        schema_location=orm.schema_location,
        categories=[
            ServiceCategoryRef(id=c.id, href=c.href, name=c.name)
            for c in orm.categories
        ],
    )


# ── ServiceCategoryService ────────────────────────────────────────────────────


class ServiceCategoryService:
    """Service layer for TMF633 ServiceCategory."""

    def __init__(self, repo: ServiceCategoryRepository) -> None:
        self._repo = repo

    async def list_categories(
        self,
        offset: int = 0,
        limit: int = 20,
        lifecycle_status: str | None = None,
        is_root: bool | None = None,
    ) -> tuple[list[ServiceCategoryResponse], int]:
        """Return a paginated list of categories.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            lifecycle_status: Optional lifecycle filter.
            is_root: When True, restrict to root categories.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(
            offset=offset,
            limit=limit,
            lifecycle_status=lifecycle_status,
            is_root=is_root,
        )
        return [_category_orm_to_response(i) for i in items], total

    async def get_category(self, category_id: str) -> ServiceCategoryResponse:
        """Retrieve a single category or raise 404.

        Args:
            category_id: The category UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(category_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCategory '{category_id}' not found.",
            )
        return _category_orm_to_response(orm)

    async def create_category(
        self, data: ServiceCategoryCreate
    ) -> ServiceCategoryResponse:
        """Create a new ServiceCategory.

        Args:
            data: Validated create payload.

        Returns:
            The created category response.
        """
        if data.lifecycle_status not in {"draft", "active"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"New categories must start in 'draft' or 'active' status. "
                    f"Got: '{data.lifecycle_status}'"
                ),
            )
        orm = await self._repo.create(data)
        response = _category_orm_to_response(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceCategoryCreateEvent",
                domain="serviceCatalog",
                title="Service Category Created",
                description=f"ServiceCategory '{orm.id}' created.",
                event=EventPayload(resource=response),
            )
        )
        return response

    async def update_category(
        self, category_id: str, data: ServiceCategoryUpdate
    ) -> ServiceCategoryResponse:
        """Full replacement of a ServiceCategory (PUT).

        Args:
            category_id: ID of the category to replace.
            data: Fully-populated update payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if lifecycle transition invalid.
        """
        existing = await self._repo.get_by_id(category_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCategory '{category_id}' not found.",
            )
        _validate_lifecycle_transition(existing.lifecycle_status, data.lifecycle_status)
        orm = await self._repo.update(category_id, data)
        return _category_orm_to_response(orm)  # type: ignore[arg-type]

    async def patch_category(
        self, category_id: str, data: ServiceCategoryPatch
    ) -> ServiceCategoryResponse:
        """Partial update of a ServiceCategory (PATCH).

        Args:
            category_id: ID of the category to update.
            data: Partial update payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if lifecycle transition invalid.
        """
        existing = await self._repo.get_by_id(category_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCategory '{category_id}' not found.",
            )
        if data.lifecycle_status is not None:
            _validate_lifecycle_transition(existing.lifecycle_status, data.lifecycle_status)
        orm = await self._repo.patch(category_id, data)
        return _category_orm_to_response(orm)  # type: ignore[arg-type]

    async def delete_category(self, category_id: str) -> None:
        """Delete a ServiceCategory.

        Only categories in ``draft`` or ``retired`` status may be deleted.

        Args:
            category_id: ID of the category to delete.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if status prevents deletion.
        """
        existing = await self._repo.get_by_id(category_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCategory '{category_id}' not found.",
            )
        if existing.lifecycle_status not in {"draft", "retired"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"ServiceCategory '{category_id}' cannot be deleted in "
                    f"'{existing.lifecycle_status}' status. "
                    "Move it to 'draft' or 'retired' first."
                ),
            )
        await self._repo.delete(category_id)


# ── ServiceCandidateService ───────────────────────────────────────────────────


class ServiceCandidateService:
    """Service layer for TMF633 ServiceCandidate."""

    def __init__(self, repo: ServiceCandidateRepository) -> None:
        self._repo = repo

    async def list_candidates(
        self,
        offset: int = 0,
        limit: int = 20,
        lifecycle_status: str | None = None,
    ) -> tuple[list[ServiceCandidateResponse], int]:
        """Return a paginated list of candidates.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            lifecycle_status: Optional lifecycle filter.
        """
        items, total = await self._repo.get_all(
            offset=offset,
            limit=limit,
            lifecycle_status=lifecycle_status,
        )
        return [_candidate_orm_to_response(i) for i in items], total

    async def get_candidate(self, candidate_id: str) -> ServiceCandidateResponse:
        """Retrieve a single candidate or raise 404.

        Args:
            candidate_id: The candidate UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(candidate_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCandidate '{candidate_id}' not found.",
            )
        return _candidate_orm_to_response(orm)

    async def create_candidate(
        self, data: ServiceCandidateCreate
    ) -> ServiceCandidateResponse:
        """Create a new ServiceCandidate.

        Args:
            data: Validated create payload.

        Returns:
            The created candidate response.
        """
        if data.lifecycle_status not in {"draft", "active"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"New candidates must start in 'draft' or 'active' status. "
                    f"Got: '{data.lifecycle_status}'"
                ),
            )
        orm = await self._repo.create(data)
        response = _candidate_orm_to_response(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceCandidateCreateEvent",
                domain="serviceCatalog",
                title="Service Candidate Created",
                description=f"ServiceCandidate '{orm.id}' created.",
                event=EventPayload(resource=response),
            )
        )
        return response

    async def update_candidate(
        self, candidate_id: str, data: ServiceCandidateUpdate
    ) -> ServiceCandidateResponse:
        """Full replacement of a ServiceCandidate (PUT).

        Args:
            candidate_id: ID of the candidate to replace.
            data: Fully-populated update payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if lifecycle transition invalid.
        """
        existing = await self._repo.get_by_id(candidate_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCandidate '{candidate_id}' not found.",
            )
        _validate_lifecycle_transition(existing.lifecycle_status, data.lifecycle_status)
        orm = await self._repo.update(candidate_id, data)
        return _candidate_orm_to_response(orm)  # type: ignore[arg-type]

    async def patch_candidate(
        self, candidate_id: str, data: ServiceCandidatePatch
    ) -> ServiceCandidateResponse:
        """Partial update of a ServiceCandidate (PATCH).

        Args:
            candidate_id: ID of the candidate to update.
            data: Partial update payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if lifecycle transition invalid.
        """
        existing = await self._repo.get_by_id(candidate_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCandidate '{candidate_id}' not found.",
            )
        if data.lifecycle_status is not None:
            _validate_lifecycle_transition(existing.lifecycle_status, data.lifecycle_status)
        orm = await self._repo.patch(candidate_id, data)
        return _candidate_orm_to_response(orm)  # type: ignore[arg-type]

    async def delete_candidate(self, candidate_id: str) -> None:
        """Delete a ServiceCandidate.

        Only candidates in ``draft`` or ``retired`` status may be deleted.

        Args:
            candidate_id: ID of the candidate to delete.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if status prevents deletion.
        """
        existing = await self._repo.get_by_id(candidate_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCandidate '{candidate_id}' not found.",
            )
        if existing.lifecycle_status not in {"draft", "retired"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"ServiceCandidate '{candidate_id}' cannot be deleted in "
                    f"'{existing.lifecycle_status}' status. "
                    "Move it to 'draft' or 'retired' first."
                ),
            )
        await self._repo.delete(candidate_id)


# ── ServiceCatalogContainerService ───────────────────────────────────────────


class ServiceCatalogContainerService:
    """Service layer for TMF633 ServiceCatalog (the catalog container resource)."""

    def __init__(self, repo: ServiceCatalogRepository) -> None:
        self._repo = repo

    async def list_catalogs(
        self,
        offset: int = 0,
        limit: int = 20,
        lifecycle_status: str | None = None,
    ) -> tuple[list[ServiceCatalogResponse], int]:
        """Return a paginated list of catalogs.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            lifecycle_status: Optional lifecycle filter.
        """
        items, total = await self._repo.get_all(
            offset=offset,
            limit=limit,
            lifecycle_status=lifecycle_status,
        )
        return [_catalog_orm_to_response(i) for i in items], total

    async def get_catalog(self, catalog_id: str) -> ServiceCatalogResponse:
        """Retrieve a single catalog or raise 404.

        Args:
            catalog_id: The catalog UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(catalog_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCatalog '{catalog_id}' not found.",
            )
        return _catalog_orm_to_response(orm)

    async def create_catalog(
        self, data: ServiceCatalogCreate
    ) -> ServiceCatalogResponse:
        """Create a new ServiceCatalog.

        Args:
            data: Validated create payload.

        Returns:
            The created catalog response.
        """
        if data.lifecycle_status not in {"draft", "active"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"New catalogs must start in 'draft' or 'active' status. "
                    f"Got: '{data.lifecycle_status}'"
                ),
            )
        orm = await self._repo.create(data)
        response = _catalog_orm_to_response(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceCatalogCreateEvent",
                domain="serviceCatalog",
                title="Service Catalog Created",
                description=f"ServiceCatalog '{orm.id}' created.",
                event=EventPayload(resource=response),
            )
        )
        return response

    async def update_catalog(
        self, catalog_id: str, data: ServiceCatalogUpdate
    ) -> ServiceCatalogResponse:
        """Full replacement of a ServiceCatalog (PUT).

        Args:
            catalog_id: ID of the catalog to replace.
            data: Fully-populated update payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if lifecycle transition invalid.
        """
        existing = await self._repo.get_by_id(catalog_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCatalog '{catalog_id}' not found.",
            )
        _validate_lifecycle_transition(existing.lifecycle_status, data.lifecycle_status)
        orm = await self._repo.update(catalog_id, data)
        return _catalog_orm_to_response(orm)  # type: ignore[arg-type]

    async def patch_catalog(
        self, catalog_id: str, data: ServiceCatalogPatch
    ) -> ServiceCatalogResponse:
        """Partial update of a ServiceCatalog (PATCH).

        Args:
            catalog_id: ID of the catalog to update.
            data: Partial update payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if lifecycle transition invalid.
        """
        existing = await self._repo.get_by_id(catalog_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCatalog '{catalog_id}' not found.",
            )
        if data.lifecycle_status is not None:
            _validate_lifecycle_transition(existing.lifecycle_status, data.lifecycle_status)
        orm = await self._repo.patch(catalog_id, data)
        return _catalog_orm_to_response(orm)  # type: ignore[arg-type]

    async def delete_catalog(self, catalog_id: str) -> None:
        """Delete a ServiceCatalog.

        Only catalogs in ``draft`` or ``retired`` status may be deleted.

        Args:
            catalog_id: ID of the catalog to delete.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if status prevents deletion.
        """
        existing = await self._repo.get_by_id(catalog_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCatalog '{catalog_id}' not found.",
            )
        if existing.lifecycle_status not in {"draft", "retired"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"ServiceCatalog '{catalog_id}' cannot be deleted in "
                    f"'{existing.lifecycle_status}' status. "
                    "Move it to 'draft' or 'retired' first."
                ),
            )
        await self._repo.delete(catalog_id)
