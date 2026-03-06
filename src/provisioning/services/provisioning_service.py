"""Business logic and state machine for TMF640 Service Activation & Configuration.

Job lifecycle state machine:

    accepted ──► running ──► succeeded
                         └──► failed
             └──► cancelled   (from accepted or running)

Terminal states: ``succeeded``, ``failed``, ``cancelled``

On job ``succeeded``, the target Service's state in TMF638 inventory is
updated based on the ``job_type``:

    provision / activate  →  active
    modify                →  active   (params updated but state stays active)
    deactivate            →  inactive
    terminate             →  terminated
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from src.inventory.models.schemas import ServicePatch
from src.inventory.repositories.service_repo import ServiceRepository
from src.inventory.services.inventory_service import InventoryService
from src.provisioning.models.orm import ServiceActivationJobOrm
from src.provisioning.models.schemas import (
    DELETABLE_JOB_STATES,
    JOB_TRANSITIONS,
    JOB_TYPE_VALID_SERVICE_STATES,
    SERVICE_STATE_ON_SUCCESS,
    VALID_JOB_TYPES,
    ServiceActivationJobCreate,
    ServiceActivationJobPatch,
    ServiceActivationJobResponse,
)
from src.provisioning.repositories.activation_job_repo import ActivationJobRepository
from src.shared.events.bus import EventBus
from src.shared.events.schemas import EventPayload, TMFEvent


def _validate_job_state_transition(current: str, requested: str) -> None:
    """Raise 422 if the job state transition is not permitted.

    Args:
        current: Current lifecycle state of the job.
        requested: Requested target state.

    Raises:
        :class:`fastapi.HTTPException` (422) if the transition is invalid.
    """
    allowed = JOB_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid job state transition from '{current}' to '{requested}'. "
                f"Allowed targets: {sorted(allowed) if allowed else 'none (terminal state)'}"
            ),
        )


def _orm_to_response(orm: ServiceActivationJobOrm) -> ServiceActivationJobResponse:
    """Map an ORM instance to the API response schema.

    Args:
        orm: The SQLAlchemy ORM instance.

    Returns:
        A :class:`ServiceActivationJobResponse` ready for serialisation.
    """
    return ServiceActivationJobResponse.model_validate(orm)


class ProvisioningService:
    """Service layer for TMF640 ServiceActivationJob.

    Applies business rules (job state machine, inventory integration,
    event publishing) on top of the raw data-access operations from
    the repository.
    """

    def __init__(
        self,
        repo: ActivationJobRepository,
        inventory_service: InventoryService,
    ) -> None:
        self._repo = repo
        self._inventory = inventory_service

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_jobs(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
        job_type: str | None = None,
        service_id: str | None = None,
    ) -> tuple[list[ServiceActivationJobResponse], int]:
        """Return a paginated list of activation jobs.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional lifecycle state filter.
            job_type: Optional job type filter.
            service_id: Optional target service filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(
            offset=offset,
            limit=limit,
            state=state,
            job_type=job_type,
            service_id=service_id,
        )
        return [_orm_to_response(item) for item in items], total

    async def get_job(self, job_id: str) -> ServiceActivationJobResponse:
        """Retrieve a single activation job or raise 404.

        Args:
            job_id: The job UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.

        Returns:
            The job response.
        """
        orm = await self._repo.get_by_id(job_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceActivationJob '{job_id}' not found.",
            )
        return _orm_to_response(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_job(self, data: ServiceActivationJobCreate) -> ServiceActivationJobResponse:
        """Create a new ServiceActivationJob.

        Validates the job type, resolves the target service, checks that the
        service state is compatible with the requested job type, and publishes
        a ``ServiceActivationJobCreateEvent``.

        Args:
            data: Validated create payload.

        Returns:
            The created job response.

        Raises:
            :class:`fastapi.HTTPException` (422) if ``job_type`` is not valid.
            :class:`fastapi.HTTPException` (404) if the target service does not exist.
            :class:`fastapi.HTTPException` (422) if the service state is incompatible
                with the requested ``job_type``.
        """
        # Validate job type
        if data.job_type not in VALID_JOB_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid job_type '{data.job_type}'. "
                    f"Valid types: {sorted(VALID_JOB_TYPES)}"
                ),
            )

        # Resolve target service (404 if not found)
        service_orm = await self._inventory._repo.get_by_id(data.service_id)
        if service_orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{data.service_id}' not found.",
            )

        # Check service state compatibility with the job type
        valid_states = JOB_TYPE_VALID_SERVICE_STATES[data.job_type]
        if service_orm.state not in valid_states:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Job type '{data.job_type}' requires the service to be in one of "
                    f"states {sorted(valid_states)}, but service is currently '{service_orm.state}'."
                ),
            )

        orm = await self._repo.create(data)
        response = _orm_to_response(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceActivationJobCreateEvent",
                domain="serviceActivationConfiguration",
                title="Service Activation Job Created",
                description=(
                    f"Job '{orm.id}' of type '{orm.job_type}' created for "
                    f"service '{orm.service_id}' in state 'accepted'."
                ),
                event=EventPayload(resource=response),
            )
        )

        return response

    async def patch_job(
        self, job_id: str, data: ServiceActivationJobPatch
    ) -> ServiceActivationJobResponse:
        """Partial update of a ServiceActivationJob.

        Validates the requested state transition.  On ``succeeded``, drives the
        target service's lifecycle state via the inventory service.
        Publishes a ``ServiceActivationJobStateChangeEvent`` on any state change.

        Args:
            job_id: ID of the job to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if state transition is invalid.

        Returns:
            The patched job response.
        """
        existing = await self._repo.get_by_id(job_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceActivationJob '{job_id}' not found.",
            )

        state_changed = False
        old_state = existing.state

        if data.state is not None and data.state != existing.state:
            _validate_job_state_transition(existing.state, data.state)
            state_changed = True

        # Build timestamp extra_fields based on transition
        extra_fields: dict[str, object] = {}
        now = datetime.now(tz=timezone.utc)
        if data.state == "running":
            extra_fields["actual_start_date"] = now
        elif data.state in {"succeeded", "failed", "cancelled"}:
            extra_fields["actual_completion_date"] = now

        orm = await self._repo.patch(job_id, data, extra_fields=extra_fields)
        if orm is None:  # should not happen after the get_by_id check above
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceActivationJob '{job_id}' not found.",
            )

        # On succeeded: drive the inventory service state machine
        if state_changed and data.state == "succeeded":
            new_service_state = SERVICE_STATE_ON_SUCCESS[orm.job_type]
            await self._inventory.patch_service(
                service_id=orm.service_id,
                data=ServicePatch(state=new_service_state),
            )

        response = _orm_to_response(orm)

        if state_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ServiceActivationJobStateChangeEvent",
                    domain="serviceActivationConfiguration",
                    title="Service Activation Job State Changed",
                    description=(
                        f"Job '{job_id}' transitioned from '{old_state}' to '{data.state}'. "
                        f"Target service: '{orm.service_id}'."
                    ),
                    event=EventPayload(resource=response),
                )
            )

        return response

    async def delete_job(self, job_id: str) -> None:
        """Delete a ServiceActivationJob.

        Only ``failed`` or ``cancelled`` jobs may be deleted.

        Args:
            job_id: ID of the job to delete.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if current state does not permit deletion.
            :class:`fastapi.HTTPException` (409) if a FK RESTRICT prevents deletion.
        """
        existing = await self._repo.get_by_id(job_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceActivationJob '{job_id}' not found.",
            )
        if existing.state not in DELETABLE_JOB_STATES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot delete a job in '{existing.state}' state. "
                    f"Only {sorted(DELETABLE_JOB_STATES)} jobs may be deleted."
                ),
            )
        try:
            await self._repo.delete(job_id)
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Job is referenced by another entity and cannot be deleted.",
            )
