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
    ServiceRelationshipCreate,
    ServiceRelationshipResponse,
    ServiceResponse,
)
from src.inventory.repositories.service_repo import ServiceRepository
from src.inventory.repositories.service_relationship_repo import ServiceRelationshipRepository
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
        self._rel_repo: ServiceRelationshipRepository | None = None

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

    # ── Service Relationships (TMF638 ServiceRelationship / SID GB922) ───────

    def _rel_repo_instance(self) -> ServiceRelationshipRepository:
        """Return the injected service relationship repository."""
        if self._rel_repo is None:
            raise RuntimeError("ServiceRelationshipRepository not injected.")
        return self._rel_repo

    async def list_service_relationships(
        self,
        service_id: str,
    ) -> list[ServiceRelationshipResponse]:
        """List all ServiceRelationship entries for a service instance.

        Args:
            service_id: The parent Service UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if the service does not exist.

        Returns:
            List of relationship responses.
        """
        existing = await self._repo.get_by_id(service_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found.",
            )
        items = await self._rel_repo_instance().get_all_by_service_id(service_id)
        return [ServiceRelationshipResponse.model_validate(i) for i in items]

    async def add_service_relationship(
        self,
        service_id: str,
        data: ServiceRelationshipCreate,
    ) -> ServiceRelationshipResponse:
        """Create a ServiceRelationship between two Service instances.

        Validates:
        - The owning service exists.
        - The related service exists.
        - No self-reference.
        - The relationship type is valid.
        - The triple is not a duplicate.

        Args:
            service_id: UUID of the owning Service instance.
            data: Validated create payload.

        Returns:
            The created relationship response.
        """
        from src.catalog.models.schemas import VALID_RELATIONSHIP_TYPES  # noqa: PLC0415

        existing = await self._repo.get_by_id(service_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found.",
            )

        if data.related_service_id == service_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A Service cannot be related to itself.",
            )

        if data.relationship_type not in VALID_RELATIONSHIP_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid relationship_type '{data.relationship_type}'. "
                    f"Allowed: {sorted(VALID_RELATIONSHIP_TYPES)}"
                ),
            )

        related = await self._repo.get_by_id(data.related_service_id)
        if related is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Related Service '{data.related_service_id}' not found.",
            )
        if data.related_service_name is None:
            data = data.model_copy(update={"related_service_name": related.name})
        if data.related_service_href is None:
            data = data.model_copy(update={"related_service_href": related.href})

        rel_repo = self._rel_repo_instance()
        if await rel_repo.exists(service_id, data.related_service_id, data.relationship_type):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A '{data.relationship_type}' relationship from '{service_id}' "
                    f"to '{data.related_service_id}' already exists."
                ),
            )

        orm = await rel_repo.create(service_id, data)
        return ServiceRelationshipResponse.model_validate(orm)

    async def delete_service_relationship(self, service_id: str, rel_id: str) -> None:
        """Delete a ServiceRelationship.

        Args:
            service_id: UUID of the owning Service instance.
            rel_id: UUID of the relationship record.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found or wrong parent.
            :class:`fastapi.HTTPException` (409) if FK RESTRICT prevents deletion.
        """
        rel_repo = self._rel_repo_instance()
        orm = await rel_repo.get_by_id(rel_id)
        if orm is None or orm.service_id != service_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceRelationship '{rel_id}' not found for service '{service_id}'.",
            )
        try:
            await rel_repo.delete(orm)
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot delete this relationship because another service depends on it. "
                    "Remove the referencing relationship first."
                ),
            )

    async def propagate_spec_relationships(
        self,
        spec_id_to_service_id: dict[str, str],
    ) -> None:
        """Auto-populate ServiceRelationship entries from ServiceSpecRelationship data.

        Called at order completion.  For each (spec_id → service_id) mapping
        produced by the order items, reads the spec's outgoing relationships and
        creates matching ServiceRelationship entries when the related spec also
        has a newly created service in the same batch.

        Args:
            spec_id_to_service_id: Mapping of spec UUID → newly created service UUID.
        """
        from src.catalog.repositories.spec_relationship_repo import SpecRelationshipRepository  # noqa: PLC0415

        rel_repo = self._rel_repo_instance()
        # We need a spec relationship repo — share the same DB session
        spec_rel_repo = SpecRelationshipRepository(self._repo._db)

        for spec_id, service_id in spec_id_to_service_id.items():
            spec_rels = await spec_rel_repo.get_all_by_spec_id(spec_id)
            for spec_rel in spec_rels:
                related_service_id = spec_id_to_service_id.get(spec_rel.related_spec_id)
                if related_service_id is None:
                    continue  # Related spec not in this batch — skip

                # Skip if already present (idempotent)
                if await rel_repo.exists(service_id, related_service_id, spec_rel.relationship_type):
                    continue

                related_service = await self._repo.get_by_id(related_service_id)
                await rel_repo.create(
                    service_id,
                    ServiceRelationshipCreate(
                        relationship_type=spec_rel.relationship_type,
                        related_service_id=related_service_id,
                        related_service_name=related_service.name if related_service else None,
                        related_service_href=related_service.href if related_service else None,
                    ),
                )
