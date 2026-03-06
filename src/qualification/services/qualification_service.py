"""Business logic and state machine for TMF645 Service Qualification Management.

Qualification lifecycle state machine:

    acknowledged ──► inProgress ──► accepted
                                └──► rejected
                 └──► cancelled   (from acknowledged or inProgress)

Terminal states: ``accepted``, ``rejected``, ``cancelled``

On creation the qualification is placed in ``acknowledged`` state.
Each nested ``ServiceQualificationItem`` is validated against the
TMF633 Service Catalog if a ``service_spec_id`` is provided.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.qualification.models.orm import ServiceQualificationOrm
from src.qualification.models.schemas import (
    DELETABLE_QUALIFICATION_STATES,
    QUALIFICATION_TRANSITIONS,
    VALID_ITEM_STATES,
    ServiceQualificationCreate,
    ServiceQualificationPatch,
    ServiceQualificationResponse,
)
from src.qualification.repositories.qualification_repo import QualificationRepository
from src.shared.events.bus import EventBus
from src.shared.events.schemas import EventPayload, TMFEvent


def _validate_qualification_state_transition(current: str, requested: str) -> None:
    """Raise 422 if the qualification state transition is not permitted.

    Args:
        current: Current lifecycle state of the qualification.
        requested: Requested target state.

    Raises:
        :class:`fastapi.HTTPException` (422) if the transition is invalid.
    """
    allowed = QUALIFICATION_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid qualification state transition from '{current}' to '{requested}'. "
                f"Allowed targets: {sorted(allowed) if allowed else 'none (terminal state)'}"
            ),
        )


def _orm_to_response(orm: ServiceQualificationOrm) -> ServiceQualificationResponse:
    """Map an ORM instance to the API response schema.

    Args:
        orm: The SQLAlchemy ORM instance.

    Returns:
        A :class:`ServiceQualificationResponse` ready for serialisation.
    """
    return ServiceQualificationResponse.model_validate(orm)


class QualificationService:
    """Service layer for TMF645 ServiceQualification.

    Applies business rules (state machine, catalog validation, event publishing)
    on top of the raw data-access operations from the repository.
    """

    def __init__(
        self,
        repo: QualificationRepository,
        spec_repo: ServiceSpecificationRepository,
    ) -> None:
        self._repo = repo
        self._spec_repo = spec_repo

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_qualifications(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
    ) -> tuple[list[ServiceQualificationResponse], int]:
        """Return a paginated list of qualifications.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional lifecycle state filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(offset=offset, limit=limit, state=state)
        return [_orm_to_response(item) for item in items], total

    async def get_qualification(self, qualification_id: str) -> ServiceQualificationResponse:
        """Retrieve a single qualification or raise 404.

        Args:
            qualification_id: The qualification UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.

        Returns:
            The qualification response.
        """
        orm = await self._repo.get_by_id(qualification_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceQualification '{qualification_id}' not found.",
            )
        return _orm_to_response(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_qualification(
        self, data: ServiceQualificationCreate
    ) -> ServiceQualificationResponse:
        """Create a new ServiceQualification.

        Validates that any referenced ``service_spec_id`` values exist in the
        TMF633 catalog.  Creates the parent qualification in ``acknowledged``
        state with all nested items.  Publishes a
        ``ServiceQualificationCreateEvent`` on success.

        Args:
            data: Validated create payload.

        Returns:
            The created qualification response.

        Raises:
            :class:`fastapi.HTTPException` (404) if a referenced spec does not exist.
            :class:`fastapi.HTTPException` (422) if an item state is invalid.
        """
        # Validate all referenced service specifications exist
        for item in data.items:
            if item.service_spec_id is not None:
                spec = await self._spec_repo.get_by_id(item.service_spec_id)
                if spec is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=(
                            f"ServiceSpecification '{item.service_spec_id}' not found. "
                            "Each qualification item must reference an existing specification."
                        ),
                    )
            # Validate item state if explicitly provided
            if item.state is not None and item.state not in VALID_ITEM_STATES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Invalid item state '{item.state}'. "
                        f"Valid values: {sorted(VALID_ITEM_STATES)}"
                    ),
                )

        orm = await self._repo.create(data)
        response = _orm_to_response(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceQualificationCreateEvent",
                domain="serviceQualificationManagement",
                title="Service Qualification Created",
                description=(
                    f"ServiceQualification '{orm.id}' created in 'acknowledged' state "
                    f"with {len(orm.items)} item(s)."
                ),
                event=EventPayload(resource=response),
            )
        )

        return response

    async def patch_qualification(
        self, qualification_id: str, data: ServiceQualificationPatch
    ) -> ServiceQualificationResponse:
        """Partial update of a ServiceQualification.

        Validates the requested state transition and publishes a
        ``ServiceQualificationStateChangeEvent`` on any state change.

        Args:
            qualification_id: ID of the qualification to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if state transition is invalid.

        Returns:
            The patched qualification response.
        """
        existing = await self._repo.get_by_id(qualification_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceQualification '{qualification_id}' not found.",
            )

        state_changed = False
        old_state = existing.state

        if data.state is not None and data.state != existing.state:
            _validate_qualification_state_transition(existing.state, data.state)
            state_changed = True

        orm = await self._repo.patch(qualification_id, data)
        if orm is None:  # should not happen after the get_by_id check above
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceQualification '{qualification_id}' not found.",
            )

        response = _orm_to_response(orm)

        if state_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ServiceQualificationStateChangeEvent",
                    domain="serviceQualificationManagement",
                    title="Service Qualification State Changed",
                    description=(
                        f"ServiceQualification '{qualification_id}' transitioned "
                        f"from '{old_state}' to '{data.state}'."
                    ),
                    event=EventPayload(resource=response),
                )
            )

        return response

    async def delete_qualification(self, qualification_id: str) -> None:
        """Delete a ServiceQualification.

        Only terminal or ``acknowledged`` qualifications may be deleted.

        Args:
            qualification_id: ID of the qualification to delete.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if current state does not permit deletion.
            :class:`fastapi.HTTPException` (409) if a FK constraint prevents deletion.
        """
        existing = await self._repo.get_by_id(qualification_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceQualification '{qualification_id}' not found.",
            )
        if existing.state not in DELETABLE_QUALIFICATION_STATES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot delete a qualification in '{existing.state}' state. "
                    f"Only {sorted(DELETABLE_QUALIFICATION_STATES)} qualifications may be deleted."
                ),
            )
        try:
            await self._repo.delete(qualification_id)
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Qualification is referenced by another entity and cannot be deleted.",
            )
