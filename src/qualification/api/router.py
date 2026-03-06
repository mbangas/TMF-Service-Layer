"""TMF645 Service Qualification Management — REST API router.

Base path: /tmf-api/serviceQualificationManagement/v4/checkServiceQualification

Endpoints:
    GET    /              List all qualifications (paginated, filterable)
    POST   /              Create a new qualification request
    GET    /{id}          Retrieve a single qualification
    PATCH  /{id}          Partial update / state transition
    DELETE /{id}          Delete a qualification (terminal or acknowledged states only)
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.qualification.models.schemas import (
    ServiceQualificationCreate,
    ServiceQualificationPatch,
    ServiceQualificationResponse,
)
from src.qualification.repositories.qualification_repo import QualificationRepository
from src.qualification.services.qualification_service import QualificationService
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix="/tmf-api/serviceQualificationManagement/v4/checkServiceQualification",
    tags=["TMF645 - Service Qualification Management"],
)


def _get_qualification_service(db: AsyncSession = Depends(get_db)) -> QualificationService:
    """Dependency factory — builds the QualificationService with its dependencies."""
    spec_repo = ServiceSpecificationRepository(db)
    qual_repo = QualificationRepository(db)
    return QualificationService(repo=qual_repo, spec_repo=spec_repo)


# ── GET / ─────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ServiceQualificationResponse],
    summary="List ServiceQualification instances",
    status_code=status.HTTP_200_OK,
)
async def list_qualifications(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by qualification lifecycle state"),
    svc: QualificationService = Depends(_get_qualification_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceQualificationResponse]:
    """Retrieve a paginated list of ``ServiceQualification`` instances (TMF645 §6.1.1).

    TMF-style pagination: ``offset`` / ``limit`` query params +
    ``X-Total-Count`` and ``X-Result-Count`` response headers.
    """
    items, total = await svc.list_qualifications(offset=offset, limit=limit, state=state)
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


# ── POST / ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ServiceQualificationResponse,
    summary="Create a ServiceQualification",
    status_code=status.HTTP_201_CREATED,
)
async def create_qualification(
    data: ServiceQualificationCreate,
    svc: QualificationService = Depends(_get_qualification_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceQualificationResponse:
    """Create a new ``ServiceQualification`` request (TMF645 §6.1.1).

    The qualification is created in ``acknowledged`` state.  Transition to
    ``inProgress`` when evaluation begins, then to ``accepted`` or ``rejected``.
    """
    return await svc.create_qualification(data)


# ── GET /{id} ─────────────────────────────────────────────────────────────────

@router.get(
    "/{qualification_id}",
    response_model=ServiceQualificationResponse,
    summary="Retrieve a ServiceQualification",
    status_code=status.HTTP_200_OK,
)
async def get_qualification(
    qualification_id: str,
    svc: QualificationService = Depends(_get_qualification_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceQualificationResponse:
    """Retrieve a single ``ServiceQualification`` by its ID (TMF645 §6.1.2).

    Raises 404 if no qualification with the given ID exists.
    """
    return await svc.get_qualification(qualification_id)


# ── PATCH /{id} ───────────────────────────────────────────────────────────────

@router.patch(
    "/{qualification_id}",
    response_model=ServiceQualificationResponse,
    summary="Update a ServiceQualification",
    status_code=status.HTTP_200_OK,
)
async def patch_qualification(
    qualification_id: str,
    data: ServiceQualificationPatch,
    svc: QualificationService = Depends(_get_qualification_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceQualificationResponse:
    """Partial update of a ``ServiceQualification`` (TMF645 §6.1.2).

    Use this endpoint to drive lifecycle state transitions or update
    mutable fields such as ``name``, ``description``, or scheduling dates.
    Invalid state transitions return 422.
    """
    return await svc.patch_qualification(qualification_id, data)


# ── DELETE /{id} ──────────────────────────────────────────────────────────────

@router.delete(
    "/{qualification_id}",
    summary="Delete a ServiceQualification",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_qualification(
    qualification_id: str,
    svc: QualificationService = Depends(_get_qualification_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceQualification`` (TMF645 §6.1.2).

    Only qualifications in terminal or ``acknowledged`` states
    (``accepted``, ``rejected``, ``cancelled``) may be deleted.
    Returns 204 No Content on success.
    """
    await svc.delete_qualification(qualification_id)
