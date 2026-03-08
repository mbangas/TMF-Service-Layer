"""Problem management REST API router — TMF621 and TMF656.

Two sub-routers are aggregated into a single ``router`` exported from this module:

    TMF621 - Trouble Ticket Management
        GET    /tmf-api/troubleTicketManagement/v4/troubleTicket
        POST   /tmf-api/troubleTicketManagement/v4/troubleTicket
        GET    /tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}
        PATCH  /tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}
        DELETE /tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}

        GET    /tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}/note
        POST   /tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}/note
        DELETE /tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}/note/{note_id}

    TMF656 - Service Problem Management
        GET    /tmf-api/serviceProblemManagement/v4/problem
        POST   /tmf-api/serviceProblemManagement/v4/problem
        GET    /tmf-api/serviceProblemManagement/v4/problem/{problem_id}
        PATCH  /tmf-api/serviceProblemManagement/v4/problem/{problem_id}
        DELETE /tmf-api/serviceProblemManagement/v4/problem/{problem_id}
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.assurance.repositories.alarm_repo import AlarmRepository
from src.inventory.repositories.service_repo import ServiceRepository
from src.problem.models.schemas import (
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
from src.problem.services.problem_service import ServiceProblemService, TroubleTicketService
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

# ── Dependency factories ───────────────────────────────────────────────────────


def _get_ticket_service(db: AsyncSession = Depends(get_db)) -> TroubleTicketService:
    """Dependency factory — builds TroubleTicketService with its dependencies."""
    return TroubleTicketService(
        repo=TroubleTicketRepository(db),
        service_repo=ServiceRepository(db),
        alarm_repo=AlarmRepository(db),
    )


def _get_problem_service(db: AsyncSession = Depends(get_db)) -> ServiceProblemService:
    """Dependency factory — builds ServiceProblemService with its dependencies."""
    return ServiceProblemService(
        repo=ServiceProblemRepository(db),
        service_repo=ServiceRepository(db),
        ticket_repo=TroubleTicketRepository(db),
    )


# ── TMF621 - Trouble Ticket Management ────────────────────────────────────────

ticket_router = APIRouter(
    prefix="/tmf-api/troubleTicketManagement/v4/troubleTicket",
    tags=["TMF621 - Trouble Ticket Management"],
)


@ticket_router.get(
    "",
    response_model=list[TroubleTicketResponse],
    summary="List TroubleTickets",
    status_code=status.HTTP_200_OK,
)
async def list_tickets(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by ticket state"),
    severity: str | None = Query(default=None, description="Filter by severity"),
    related_service_id: str | None = Query(default=None, description="Filter by service instance UUID"),
    svc: TroubleTicketService = Depends(_get_ticket_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[TroubleTicketResponse]:
    """Retrieve a paginated list of ``TroubleTicket`` instances (TMF621 §6.1.1)."""
    items, total = await svc.list_tickets(
        offset=offset, limit=limit, state=state,
        severity=severity, related_service_id=related_service_id,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@ticket_router.post(
    "",
    response_model=TroubleTicketResponse,
    summary="Create a TroubleTicket",
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    data: TroubleTicketCreate,
    svc: TroubleTicketService = Depends(_get_ticket_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> TroubleTicketResponse:
    """Create a new ``TroubleTicket`` in ``submitted`` state (TMF621 §6.1.1)."""
    return await svc.create_ticket(data)


@ticket_router.get(
    "/{ticket_id}",
    response_model=TroubleTicketResponse,
    summary="Retrieve a TroubleTicket",
    status_code=status.HTTP_200_OK,
)
async def get_ticket(
    ticket_id: str,
    svc: TroubleTicketService = Depends(_get_ticket_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> TroubleTicketResponse:
    """Retrieve a single ``TroubleTicket`` by its ID (TMF621 §6.1.2)."""
    return await svc.get_ticket(ticket_id)


@ticket_router.patch(
    "/{ticket_id}",
    response_model=TroubleTicketResponse,
    summary="Update a TroubleTicket",
    status_code=status.HTTP_200_OK,
)
async def patch_ticket(
    ticket_id: str,
    data: TroubleTicketPatch,
    svc: TroubleTicketService = Depends(_get_ticket_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> TroubleTicketResponse:
    """Partial update / state transition of a ``TroubleTicket`` (TMF621 §6.1.2)."""
    return await svc.patch_ticket(ticket_id, data)


@ticket_router.delete(
    "/{ticket_id}",
    response_class=Response,
    summary="Delete a TroubleTicket",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_ticket(
    ticket_id: str,
    svc: TroubleTicketService = Depends(_get_ticket_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``TroubleTicket`` (TMF621 §6.1.2)."""
    await svc.delete_ticket(ticket_id)


# ── TMF621 - Notes sub-resource ────────────────────────────────────────────────

note_router = APIRouter(
    prefix="/tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}/note",
    tags=["TMF621 - Trouble Ticket Management"],
)


@note_router.get(
    "",
    response_model=list[TroubleTicketNoteResponse],
    summary="List Notes on a TroubleTicket",
    status_code=status.HTTP_200_OK,
)
async def list_notes(
    ticket_id: str,
    svc: TroubleTicketService = Depends(_get_ticket_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[TroubleTicketNoteResponse]:
    """Retrieve all notes attached to a ``TroubleTicket``."""
    ticket = await svc.get_ticket(ticket_id)
    return ticket.notes


@note_router.post(
    "",
    response_model=TroubleTicketNoteResponse,
    summary="Add a Note to a TroubleTicket",
    status_code=status.HTTP_201_CREATED,
)
async def add_note(
    ticket_id: str,
    data: TroubleTicketNoteCreate,
    svc: TroubleTicketService = Depends(_get_ticket_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> TroubleTicketNoteResponse:
    """Append a new note to a ``TroubleTicket``."""
    return await svc.add_note(ticket_id, data)


@note_router.delete(
    "/{note_id}",
    response_class=Response,
    summary="Delete a Note from a TroubleTicket",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_note(
    ticket_id: str,
    note_id: str,
    svc: TroubleTicketService = Depends(_get_ticket_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a single note from a ``TroubleTicket``."""
    await svc.delete_note(ticket_id, note_id)


# ── TMF656 - Service Problem Management ───────────────────────────────────────

problem_router = APIRouter(
    prefix="/tmf-api/serviceProblemManagement/v4/problem",
    tags=["TMF656 - Service Problem Management"],
)


@problem_router.get(
    "",
    response_model=list[ServiceProblemResponse],
    summary="List ServiceProblems",
    status_code=status.HTTP_200_OK,
)
async def list_problems(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by problem state"),
    impact: str | None = Query(default=None, description="Filter by impact level"),
    related_service_id: str | None = Query(default=None, description="Filter by service instance UUID"),
    svc: ServiceProblemService = Depends(_get_problem_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceProblemResponse]:
    """Retrieve a paginated list of ``ServiceProblem`` instances (TMF656 §6.1.1)."""
    items, total = await svc.list_problems(
        offset=offset, limit=limit, state=state,
        impact=impact, related_service_id=related_service_id,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@problem_router.post(
    "",
    response_model=ServiceProblemResponse,
    summary="Create a ServiceProblem",
    status_code=status.HTTP_201_CREATED,
)
async def create_problem(
    data: ServiceProblemCreate,
    svc: ServiceProblemService = Depends(_get_problem_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceProblemResponse:
    """Create a new ``ServiceProblem`` in ``submitted`` state (TMF656 §6.1.1)."""
    return await svc.create_problem(data)


@problem_router.get(
    "/{problem_id}",
    response_model=ServiceProblemResponse,
    summary="Retrieve a ServiceProblem",
    status_code=status.HTTP_200_OK,
)
async def get_problem(
    problem_id: str,
    svc: ServiceProblemService = Depends(_get_problem_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceProblemResponse:
    """Retrieve a single ``ServiceProblem`` by its ID (TMF656 §6.1.2)."""
    return await svc.get_problem(problem_id)


@problem_router.patch(
    "/{problem_id}",
    response_model=ServiceProblemResponse,
    summary="Update a ServiceProblem",
    status_code=status.HTTP_200_OK,
)
async def patch_problem(
    problem_id: str,
    data: ServiceProblemPatch,
    svc: ServiceProblemService = Depends(_get_problem_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceProblemResponse:
    """Partial update / state transition of a ``ServiceProblem`` (TMF656 §6.1.2)."""
    return await svc.patch_problem(problem_id, data)


@problem_router.delete(
    "/{problem_id}",
    response_class=Response,
    summary="Delete a ServiceProblem",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_problem(
    problem_id: str,
    svc: ServiceProblemService = Depends(_get_problem_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceProblem`` (TMF656 §6.1.2)."""
    await svc.delete_problem(problem_id)


# ── Aggregate router ───────────────────────────────────────────────────────────

router = APIRouter()
router.include_router(ticket_router)
router.include_router(note_router)
router.include_router(problem_router)
