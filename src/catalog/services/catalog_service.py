"""Business logic and lifecycle state machine for TMF633 Service Catalog.

Lifecycle state transitions (TMF633 §7.1.5):

    draft ──► active ──► obsolete ──► retired
                 │                        ▲
                 └────────────────────────┘  (active → retired is allowed)

Any other transition is rejected with a 422 Unprocessable Entity.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from src.catalog.models.orm import ServiceSpecificationOrm
from src.catalog.models.schemas import (
    ServiceSpecificationCreate,
    ServiceSpecificationPatch,
    ServiceSpecificationResponse,
    ServiceSpecificationUpdate,
)
from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.shared.events.bus import EventBus
from src.shared.events.schemas import EventPayload, TMFEvent

# Allowed lifecycle transitions: {from_state: {allowed_to_states}}
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"draft", "active"},
    "active": {"active", "obsolete", "retired"},
    "obsolete": {"obsolete", "retired"},
    "retired": {"retired"},
}


def _validate_lifecycle_transition(current: str, requested: str) -> None:
    """Raise 422 if the lifecycle transition is not permitted.

    Args:
        current: The current lifecycle status of the specification.
        requested: The requested new lifecycle status.

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


def _orm_to_response(orm: ServiceSpecificationOrm) -> ServiceSpecificationResponse:
    """Map an ORM instance to the API response schema.

    Args:
        orm: The SQLAlchemy ORM instance.

    Returns:
        A :class:`ServiceSpecificationResponse` ready for serialisation.
    """
    return ServiceSpecificationResponse.model_validate(orm)


class CatalogService:
    """Service layer for TMF633 ServiceSpecification.

    Applies business rules (lifecycle state machine, validations) on top
    of the raw data-access operations exposed by the repository.
    """

    def __init__(self, repo: ServiceSpecificationRepository) -> None:
        self._repo = repo

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_specifications(
        self,
        offset: int = 0,
        limit: int = 20,
        lifecycle_status: str | None = None,
    ) -> tuple[list[ServiceSpecificationResponse], int]:
        """Return a paginated list of specifications.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            lifecycle_status: Optional lifecycle filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(
            offset=offset,
            limit=limit,
            lifecycle_status=lifecycle_status,
        )
        return [_orm_to_response(item) for item in items], total

    async def get_specification(self, spec_id: str) -> ServiceSpecificationResponse:
        """Retrieve a single specification or raise 404.

        Args:
            spec_id: The specification UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.

        Returns:
            The specification response.
        """
        orm = await self._repo.get_by_id(spec_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceSpecification '{spec_id}' not found.",
            )
        return _orm_to_response(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_specification(
        self, data: ServiceSpecificationCreate
    ) -> ServiceSpecificationResponse:
        """Create a new ServiceSpecification.

        Validates the initial lifecycle status is one of the allowed entry states.

        Args:
            data: Validated create payload.

        Returns:
            The created specification.
        """
        if data.lifecycle_status not in {"draft", "active"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"New specifications must start in 'draft' or 'active' status. "
                    f"Got: '{data.lifecycle_status}'"
                ),
            )
        orm = await self._repo.create(data)
        response = _orm_to_response(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceSpecificationCreateEvent",
                domain="serviceCatalog",
                title="Service Specification Created",
                description=f"ServiceSpecification '{orm.id}' created with status '{orm.lifecycle_status}'.",
                event=EventPayload(resource=response),
            )
        )

        return response

    async def update_specification(
        self, spec_id: str, data: ServiceSpecificationUpdate
    ) -> ServiceSpecificationResponse:
        """Full replacement of a ServiceSpecification (PUT).

        Validates lifecycle transition before updating.

        Args:
            spec_id: ID of the specification to replace.
            data: Fully-populated update payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if lifecycle transition invalid.

        Returns:
            The updated specification.
        """
        existing = await self._repo.get_by_id(spec_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceSpecification '{spec_id}' not found.",
            )
        _validate_lifecycle_transition(existing.lifecycle_status, data.lifecycle_status)
        status_changed = existing.lifecycle_status != data.lifecycle_status
        old_status = existing.lifecycle_status
        orm = await self._repo.update(spec_id, data)
        response = _orm_to_response(orm)  # type: ignore[arg-type]

        if status_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ServiceSpecificationStateChangeEvent",
                    domain="serviceCatalog",
                    title="Service Specification State Changed",
                    description=(
                        f"ServiceSpecification '{spec_id}' transitioned "
                        f"from '{old_status}' to '{data.lifecycle_status}'."
                    ),
                    event=EventPayload(resource=response),
                )
            )

        return response

    async def patch_specification(
        self, spec_id: str, data: ServiceSpecificationPatch
    ) -> ServiceSpecificationResponse:
        """Partial update of a ServiceSpecification (PATCH).

        Validates lifecycle transition when ``lifecycle_status`` is provided.

        Args:
            spec_id: ID of the specification to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if lifecycle transition invalid.

        Returns:
            The patched specification.
        """
        existing = await self._repo.get_by_id(spec_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceSpecification '{spec_id}' not found.",
            )
        if data.lifecycle_status is not None:
            _validate_lifecycle_transition(existing.lifecycle_status, data.lifecycle_status)
        status_changed = (
            data.lifecycle_status is not None
            and data.lifecycle_status != existing.lifecycle_status
        )
        old_status = existing.lifecycle_status
        orm = await self._repo.patch(spec_id, data)
        response = _orm_to_response(orm)  # type: ignore[arg-type]

        if status_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ServiceSpecificationStateChangeEvent",
                    domain="serviceCatalog",
                    title="Service Specification State Changed",
                    description=(
                        f"ServiceSpecification '{spec_id}' transitioned "
                        f"from '{old_status}' to '{data.lifecycle_status}'."
                    ),
                    event=EventPayload(resource=response),
                )
            )

        return response

    async def delete_specification(self, spec_id: str) -> None:
        """Delete a ServiceSpecification.

        Only ``draft`` or ``retired`` specifications may be deleted.

        Args:
            spec_id: ID of the specification to delete.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if the status does not permit deletion.
        """
        existing = await self._repo.get_by_id(spec_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceSpecification '{spec_id}' not found.",
            )
        if existing.lifecycle_status not in {"draft", "retired"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot delete a specification in '{existing.lifecycle_status}' status. "
                    "Retire the specification first."
                ),
            )
        try:
            await self._repo.delete(spec_id)
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Specification is referenced by existing service orders and cannot be deleted.",
            )
