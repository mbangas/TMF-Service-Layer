"""Business logic for TMF621 Trouble Ticket Management and TMF656 Service Problem Management.

Trouble Ticket lifecycle state machine:
    submitted → inProgress → pending → inProgress → resolved → closed
    inProgress → resolved (shortcut)
    pending → resolved (shortcut)

Service Problem lifecycle state machine:
    submitted → confirmed | rejected
    confirmed → active | rejected
    active → resolved
    resolved → closed
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status

from src.problem.models.orm import ServiceProblemOrm, TroubleTicketOrm
from src.problem.models.schemas import (
    PROBLEM_TRANSITIONS,
    TICKET_TRANSITIONS,
    VALID_PROBLEM_IMPACTS,
    VALID_TICKET_SEVERITIES,
    ServiceProblemCreate,
    ServiceProblemPatch,
    ServiceProblemResponse,
    TroubleTicketCreate,
    TroubleTicketNoteCreate,
    TroubleTicketNoteResponse,
    TroubleTicketPatch,
    TroubleTicketResponse,
)
from src.problem.repositories.service_problem_repo import ServiceProblemRepository
from src.problem.repositories.trouble_ticket_repo import TroubleTicketRepository
from src.shared.events.bus import EventBus
from src.shared.events.schemas import EventPayload, TMFEvent


# ── Shared helper ─────────────────────────────────────────────────────────────

def _validate_state_transition(
    current: str,
    requested: str,
    transitions: dict[str, set[str]],
    entity_name: str,
) -> None:
    """Raise HTTP 422 if the requested state transition is not permitted.

    Args:
        current: Current lifecycle state.
        requested: Requested target state.
        transitions: Allowed transition map for the entity type.
        entity_name: Human-readable entity name for the error message.

    Raises:
        :class:`fastapi.HTTPException` (422) if the transition is invalid.
    """
    allowed = transitions.get(current, set())
    if requested not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid {entity_name} state transition from '{current}' to '{requested}'. "
                f"Allowed targets: {sorted(allowed) if allowed else 'none (terminal state)'}"
            ),
        )


# ── TroubleTicketService ──────────────────────────────────────────────────────

class TroubleTicketService:
    """Service layer for TMF621 Trouble Ticket Management.

    Validates FK references (service, alarm), enforces state machine transitions,
    auto-sets ``resolution_date`` on resolve, and publishes TMF events.
    """

    def __init__(
        self,
        repo: TroubleTicketRepository,
        service_repo,  # src.inventory.repositories.service_repo.ServiceRepository
        alarm_repo,    # src.assurance.repositories.alarm_repo.AlarmRepository
    ) -> None:
        self._repo = repo
        self._service_repo = service_repo
        self._alarm_repo = alarm_repo

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_tickets(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
        severity: str | None = None,
        related_service_id: str | None = None,
    ) -> tuple[list[TroubleTicketResponse], int]:
        """Return a paginated list of trouble tickets.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional lifecycle state filter.
            severity: Optional severity filter.
            related_service_id: Optional service instance filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(
            offset=offset, limit=limit,
            state=state, severity=severity,
            related_service_id=related_service_id,
        )
        return [TroubleTicketResponse.model_validate(i) for i in items], total

    async def get_ticket(self, ticket_id: str) -> TroubleTicketResponse:
        """Retrieve a single trouble ticket or raise 404.

        Args:
            ticket_id: The ticket UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(ticket_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"TroubleTicket '{ticket_id}' not found.",
            )
        return TroubleTicketResponse.model_validate(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_ticket(self, data: TroubleTicketCreate) -> TroubleTicketResponse:
        """Create a new TroubleTicket in ``submitted`` state.

        Validates that ``related_service_id`` exists if provided,
        that ``related_alarm_id`` exists if provided, and that the
        severity value is valid if provided.

        Args:
            data: Validated create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if the service/alarm FK does not exist.
            :class:`fastapi.HTTPException` (422) if the severity value is invalid.
        """
        if data.related_service_id is not None:
            svc = await self._service_repo.get_by_id(data.related_service_id)
            if svc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Service '{data.related_service_id}' not found.",
                )

        if data.related_alarm_id is not None:
            alarm = await self._alarm_repo.get_by_id(data.related_alarm_id)
            if alarm is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Alarm '{data.related_alarm_id}' not found.",
                )

        if data.severity is not None and data.severity not in VALID_TICKET_SEVERITIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid severity '{data.severity}'. "
                    f"Valid values: {sorted(VALID_TICKET_SEVERITIES)}"
                ),
            )

        orm = await self._repo.create(data)
        response = TroubleTicketResponse.model_validate(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="TroubleTicketCreateEvent",
                domain="troubleTicketManagement",
                title="Trouble Ticket Created",
                description=f"TroubleTicket '{orm.id}' created.",
                event=EventPayload(resource=response),
            )
        )
        return response

    async def patch_ticket(self, ticket_id: str, data: TroubleTicketPatch) -> TroubleTicketResponse:
        """Partial update of a TroubleTicket with state machine enforcement.

        Auto-sets ``resolution_date`` when transitioning to ``resolved``.

        Args:
            ticket_id: ID of the ticket to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if the state transition is invalid.
        """
        orm = await self._repo.get_by_id(ticket_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"TroubleTicket '{ticket_id}' not found.",
            )

        state_changed = False
        if data.state is not None and data.state != orm.state:
            _validate_state_transition(orm.state, data.state, TICKET_TRANSITIONS, "trouble ticket")
            state_changed = True
            if data.state == "resolved":
                orm.resolution_date = datetime.now(tz=timezone.utc)

        orm = await self._repo.patch(ticket_id, data)
        response = TroubleTicketResponse.model_validate(orm)

        if state_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="TroubleTicketStateChangeEvent",
                    domain="troubleTicketManagement",
                    title="Trouble Ticket State Changed",
                    description=f"TroubleTicket '{ticket_id}' transitioned to '{orm.state}'.",
                    event=EventPayload(resource=response),
                )
            )
        return response

    async def delete_ticket(self, ticket_id: str) -> None:
        """Delete a TroubleTicket.

        Args:
            ticket_id: The ticket UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(ticket_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"TroubleTicket '{ticket_id}' not found.",
            )
        await self._repo.delete(ticket_id)

    # ── Notes ─────────────────────────────────────────────────────────────────

    async def add_note(self, ticket_id: str, data: TroubleTicketNoteCreate) -> TroubleTicketNoteResponse:
        """Append a note to a TroubleTicket.

        Args:
            ticket_id: Parent ticket UUID.
            data: Note create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if the ticket does not exist.
        """
        orm = await self._repo.get_by_id(ticket_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"TroubleTicket '{ticket_id}' not found.",
            )
        note = await self._repo.add_note(ticket_id, data)
        return TroubleTicketNoteResponse.model_validate(note)

    async def delete_note(self, ticket_id: str, note_id: str) -> None:
        """Delete a note from a TroubleTicket.

        Args:
            ticket_id: Parent ticket UUID (used for 404 guard on the parent).
            note_id: Note UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if the ticket or note is not found.
        """
        orm = await self._repo.get_by_id(ticket_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"TroubleTicket '{ticket_id}' not found.",
            )
        deleted = await self._repo.delete_note(note_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Note '{note_id}' not found on TroubleTicket '{ticket_id}'.",
            )


# ── ServiceProblemService ─────────────────────────────────────────────────────

class ServiceProblemService:
    """Service layer for TMF656 Service Problem Management.

    Validates FK references (service, ticket), enforces state machine transitions,
    and auto-sets ``resolution_date`` on resolve.
    """

    def __init__(
        self,
        repo: ServiceProblemRepository,
        service_repo,  # src.inventory.repositories.service_repo.ServiceRepository
        ticket_repo: TroubleTicketRepository,
    ) -> None:
        self._repo = repo
        self._service_repo = service_repo
        self._ticket_repo = ticket_repo

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_problems(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
        impact: str | None = None,
        related_service_id: str | None = None,
    ) -> tuple[list[ServiceProblemResponse], int]:
        """Return a paginated list of service problems.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional lifecycle state filter.
            impact: Optional impact level filter.
            related_service_id: Optional service instance filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(
            offset=offset, limit=limit,
            state=state, impact=impact,
            related_service_id=related_service_id,
        )
        return [ServiceProblemResponse.model_validate(i) for i in items], total

    async def get_problem(self, problem_id: str) -> ServiceProblemResponse:
        """Retrieve a single service problem or raise 404.

        Args:
            problem_id: The problem UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(problem_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceProblem '{problem_id}' not found.",
            )
        return ServiceProblemResponse.model_validate(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_problem(self, data: ServiceProblemCreate) -> ServiceProblemResponse:
        """Create a new ServiceProblem in ``submitted`` state.

        Validates that ``related_service_id`` and ``related_ticket_id``
        exist if provided, and that the impact value is valid if provided.

        Args:
            data: Validated create payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if a referenced FK does not exist.
            :class:`fastapi.HTTPException` (422) if the impact value is invalid.
        """
        if data.related_service_id is not None:
            svc = await self._service_repo.get_by_id(data.related_service_id)
            if svc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Service '{data.related_service_id}' not found.",
                )

        if data.related_ticket_id is not None:
            ticket = await self._ticket_repo.get_by_id(data.related_ticket_id)
            if ticket is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"TroubleTicket '{data.related_ticket_id}' not found.",
                )

        if data.impact is not None and data.impact not in VALID_PROBLEM_IMPACTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid impact '{data.impact}'. "
                    f"Valid values: {sorted(VALID_PROBLEM_IMPACTS)}"
                ),
            )

        orm = await self._repo.create(data)
        response = ServiceProblemResponse.model_validate(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceProblemCreateEvent",
                domain="serviceProblemManagement",
                title="Service Problem Created",
                description=f"ServiceProblem '{orm.id}' created.",
                event=EventPayload(resource=response),
            )
        )
        return response

    async def patch_problem(self, problem_id: str, data: ServiceProblemPatch) -> ServiceProblemResponse:
        """Partial update of a ServiceProblem with state machine enforcement.

        Auto-sets ``resolution_date`` when transitioning to ``resolved``.

        Args:
            problem_id: ID of the problem to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if the state transition is invalid.
        """
        orm = await self._repo.get_by_id(problem_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceProblem '{problem_id}' not found.",
            )

        state_changed = False
        if data.state is not None and data.state != orm.state:
            _validate_state_transition(orm.state, data.state, PROBLEM_TRANSITIONS, "service problem")
            state_changed = True
            if data.state == "resolved":
                orm.resolution_date = datetime.now(tz=timezone.utc)

        orm = await self._repo.patch(problem_id, data)
        response = ServiceProblemResponse.model_validate(orm)

        if state_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ServiceProblemStateChangeEvent",
                    domain="serviceProblemManagement",
                    title="Service Problem State Changed",
                    description=f"ServiceProblem '{problem_id}' transitioned to '{orm.state}'.",
                    event=EventPayload(resource=response),
                )
            )
        return response

    async def delete_problem(self, problem_id: str) -> None:
        """Delete a ServiceProblem.

        Args:
            problem_id: The problem UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        orm = await self._repo.get_by_id(problem_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceProblem '{problem_id}' not found.",
            )
        await self._repo.delete(problem_id)
