"""Business logic and lifecycle state machine for TMF638 Service Inventory.

Lifecycle state transitions (TMF638 §7.1.3):

    feasibilityChecked ──► designed ──► reserved ──► inactive ──► active ──► terminated

Terminal state: ``terminated`` accepts no further transitions.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from src.inventory.models.orm import ServiceOrm
from src.inventory.models.schemas import (
    VALID_SERVICE_STATES,
    ServiceCreate,
    ServicePatch,
    ServiceResponse,
)
from src.inventory.repositories.service_repo import ServiceRepository
from src.shared.events.bus import EventBus
from src.shared.events.schemas import EventPayload, TMFEvent

# Allowed lifecycle transitions: {from_state: {allowed_to_states}}
# Pre-active states follow a strict design sequence.
# Post-active operations (activate, deactivate, terminate) are driven by
# TMF640 provisioning jobs, so both active↔inactive and active/inactive→terminated
# are valid transitions here.
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "feasibilityChecked": {"designed"},
    "designed": {"reserved"},
    "reserved": {"inactive"},
    "inactive": {"active", "terminated"},       # activate or terminate from inactive
    "active": {"terminated", "inactive"},       # terminate or deactivate from active
    "terminated": set(),
}

# States that cannot be used as the initial state when creating a service
_FORBIDDEN_INITIAL_STATES = {"terminated"}


def _validate_state_transition(current: str, requested: str) -> None:
    """Raise 422 if the state transition is not permitted.

    Args:
        current: Current lifecycle state of the service.
        requested: Requested target state.

    Raises:
        :class:`fastapi.HTTPException` (422) if the transition is invalid.
    """
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid state transition from '{current}' to '{requested}'. "
                f"Allowed targets: {sorted(allowed) if allowed else 'none (terminal state)'}"
            ),
        )


def _orm_to_response(orm: ServiceOrm) -> ServiceResponse:
    """Map an ORM instance to the API response schema.

    Args:
        orm: The SQLAlchemy ORM instance.

    Returns:
        A :class:`ServiceResponse` ready for serialisation.
    """
    return ServiceResponse.model_validate(orm)


class InventoryService:
    """Service layer for TMF638 Service inventory instances.

    Applies business rules (lifecycle state machine, auto-dating,
    event publishing) on top of the raw data-access operations from
    the repository.
    """

    def __init__(self, repo: ServiceRepository) -> None:
        self._repo = repo

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_services(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
    ) -> tuple[list[ServiceResponse], int]:
        """Return a paginated list of service instances.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional lifecycle state filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(offset=offset, limit=limit, state=state)
        return [_orm_to_response(item) for item in items], total

    async def get_service(self, service_id: str) -> ServiceResponse:
        """Retrieve a single service instance or raise 404.

        Args:
            service_id: The service UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.

        Returns:
            The service response.
        """
        orm = await self._repo.get_by_id(service_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found.",
            )
        return _orm_to_response(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_service(self, data: ServiceCreate) -> ServiceResponse:
        """Create a new Service instance.

        Validates the initial lifecycle state and publishes a
        ``ServiceCreateEvent``.

        Args:
            data: Validated create payload.

        Returns:
            The created service response.

        Raises:
            :class:`fastapi.HTTPException` (422) if the initial state is
            ``terminated`` (terminal state cannot be used on creation).
            :class:`fastapi.HTTPException` (422) if the state is not a valid
            TMF638 service state.
        """
        if data.state not in VALID_SERVICE_STATES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid service state '{data.state}'. "
                    f"Valid states: {sorted(VALID_SERVICE_STATES)}"
                ),
            )
        if data.state in _FORBIDDEN_INITIAL_STATES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"New service instances cannot be created in '{data.state}' state. "
                    "Use a non-terminal initial state."
                ),
            )

        orm = await self._repo.create(data)
        response = _orm_to_response(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceCreateEvent",
                domain="serviceInventory",
                title="Service Instance Created",
                description=f"Service '{orm.id}' created with state '{orm.state}'.",
                event=EventPayload(resource=response),
            )
        )

        return response

    async def patch_service(
        self, service_id: str, data: ServicePatch
    ) -> ServiceResponse:
        """Partial update of a Service instance.

        Validates lifecycle transition when ``state`` is provided.
        Publishes a ``ServiceStateChangeEvent`` when state changes.

        Args:
            service_id: ID of the service to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if state transition is invalid.

        Returns:
            The patched service response.
        """
        existing = await self._repo.get_by_id(service_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found.",
            )

        state_changed = False
        old_state = existing.state

        if data.state is not None and data.state != existing.state:
            _validate_state_transition(existing.state, data.state)
            state_changed = True

        orm = await self._repo.patch(service_id, data)
        response = _orm_to_response(orm)  # type: ignore[arg-type]

        if state_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ServiceStateChangeEvent",
                    domain="serviceInventory",
                    title="Service State Changed",
                    description=(
                        f"Service '{service_id}' transitioned "
                        f"from '{old_state}' to '{data.state}'."
                    ),
                    event=EventPayload(resource=response),
                )
            )

        return response

    async def delete_service(self, service_id: str) -> None:
        """Delete a Service instance.

        Only ``terminated`` or ``inactive`` services may be deleted.

        Args:
            service_id: ID of the service to delete.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if current state does not
                permit deletion.
            :class:`fastapi.HTTPException` (409) if the service is referenced
                by another entity (FK RESTRICT violation).
        """
        existing = await self._repo.get_by_id(service_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found.",
            )
        if existing.state not in {"terminated", "inactive"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot delete a service in '{existing.state}' state. "
                    "Terminate or revert the service to 'inactive' first."
                ),
            )
        try:
            await self._repo.delete(service_id)
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Service is referenced by another entity and cannot be deleted.",
            )
