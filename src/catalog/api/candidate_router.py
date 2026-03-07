"""TMF633 Service Catalog Management — ServiceCandidate REST API router.

Base path: /tmf-api/serviceCatalogManagement/v4/serviceCandidate

Endpoints:
    GET    /              List all candidates (paginated)
    POST   /              Create a new candidate
    GET    /{id}          Retrieve a single candidate
    PUT    /{id}          Full replacement of a candidate
    PATCH  /{id}          Partial update of a candidate
    DELETE /{id}          Delete a candidate
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models.schemas import (
    ServiceCandidateCreate,
    ServiceCandidatePatch,
    ServiceCandidateResponse,
    ServiceCandidateUpdate,
)
from src.catalog.repositories.service_candidate_repo import ServiceCandidateRepository
from src.catalog.services.tmfc006_service import ServiceCandidateService
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix="/tmf-api/serviceCatalogManagement/v4/serviceCandidate",
    tags=["TMF633 - Service Catalog (TMFC006)"],
)


def _get_service(db: AsyncSession = Depends(get_db)) -> ServiceCandidateService:
    """Dependency factory — builds ServiceCandidateService with its repository."""
    return ServiceCandidateService(ServiceCandidateRepository(db))


@router.get(
    "",
    response_model=list[ServiceCandidateResponse],
    summary="List ServiceCandidates",
    status_code=status.HTTP_200_OK,
)
async def list_candidates(
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    lifecycle_status: str | None = Query(default=None),
    service: ServiceCandidateService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceCandidateResponse]:
    """Retrieve a paginated list of ``ServiceCandidate`` resources."""
    items, total = await service.list_candidates(
        offset=offset,
        limit=limit,
        lifecycle_status=lifecycle_status,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@router.post(
    "",
    response_model=ServiceCandidateResponse,
    summary="Create a ServiceCandidate",
    status_code=status.HTTP_201_CREATED,
)
async def create_candidate(
    data: ServiceCandidateCreate,
    service: ServiceCandidateService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCandidateResponse:
    """Create a new ``ServiceCandidate`` resource (TMF633)."""
    return await service.create_candidate(data)


@router.get(
    "/{candidate_id}",
    response_model=ServiceCandidateResponse,
    summary="Retrieve a ServiceCandidate",
    status_code=status.HTTP_200_OK,
)
async def get_candidate(
    candidate_id: str,
    service: ServiceCandidateService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCandidateResponse:
    """Retrieve a single ``ServiceCandidate`` by its UUID."""
    return await service.get_candidate(candidate_id)


@router.put(
    "/{candidate_id}",
    response_model=ServiceCandidateResponse,
    summary="Replace a ServiceCandidate",
    status_code=status.HTTP_200_OK,
)
async def update_candidate(
    candidate_id: str,
    data: ServiceCandidateUpdate,
    service: ServiceCandidateService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCandidateResponse:
    """Perform a full replacement of a ``ServiceCandidate`` (PUT semantics)."""
    return await service.update_candidate(candidate_id, data)


@router.patch(
    "/{candidate_id}",
    response_model=ServiceCandidateResponse,
    summary="Partially update a ServiceCandidate",
    status_code=status.HTTP_200_OK,
)
async def patch_candidate(
    candidate_id: str,
    data: ServiceCandidatePatch,
    service: ServiceCandidateService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCandidateResponse:
    """Apply a partial update to a ``ServiceCandidate`` (PATCH semantics)."""
    return await service.patch_candidate(candidate_id, data)


@router.delete(
    "/{candidate_id}",
    summary="Delete a ServiceCandidate",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_candidate(
    candidate_id: str,
    service: ServiceCandidateService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceCandidate``.

    Only candidates in ``draft`` or ``retired`` status may be deleted.
    """
    await service.delete_candidate(candidate_id)
