"""TMF633 Service Catalog Management — REST API router.

Base path: /tmf-api/serviceCatalogManagement/v4/serviceSpecification

Endpoints:
    GET    /              List all specifications (paginated)
    POST   /              Create a new specification
    GET    /{id}          Retrieve a single specification
    PUT    /{id}          Full replacement of a specification
    PATCH  /{id}          Partial update of a specification
    DELETE /{id}          Delete a specification
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models.schemas import (
    ServiceSpecificationCreate,
    ServiceSpecificationPatch,
    ServiceSpecificationResponse,
    ServiceSpecificationUpdate,
)
from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.catalog.services.catalog_service import CatalogService
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix="/tmf-api/serviceCatalogManagement/v4/serviceSpecification",
    tags=["TMF633 - Service Catalog"],
)

_BASE_PATH = "/tmf-api/serviceCatalogManagement/v4/serviceSpecification"


def _get_service(db: AsyncSession = Depends(get_db)) -> CatalogService:
    """Dependency factory — builds the service with its repository."""
    repo = ServiceSpecificationRepository(db)
    return CatalogService(repo)


# ── GET / ─────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ServiceSpecificationResponse],
    summary="List ServiceSpecifications",
    status_code=status.HTTP_200_OK,
)
async def list_specifications(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    lifecycle_status: str | None = Query(default=None, description="Filter by lifecycle status"),
    service: CatalogService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceSpecificationResponse]:
    """Retrieve a paginated list of ``ServiceSpecification`` resources.

    TMF-style pagination: ``offset`` / ``limit`` query params +
    ``X-Total-Count`` response header.
    """
    items, total = await service.list_specifications(
        offset=offset,
        limit=limit,
        lifecycle_status=lifecycle_status,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


# ── POST / ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ServiceSpecificationResponse,
    summary="Create a ServiceSpecification",
    status_code=status.HTTP_201_CREATED,
)
async def create_specification(
    data: ServiceSpecificationCreate,
    service: CatalogService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceSpecificationResponse:
    """Create a new ``ServiceSpecification`` resource (TMF633 §6.2.1)."""
    return await service.create_specification(data)


# ── GET /{id} ─────────────────────────────────────────────────────────────────

@router.get(
    "/{spec_id}",
    response_model=ServiceSpecificationResponse,
    summary="Retrieve a ServiceSpecification",
    status_code=status.HTTP_200_OK,
)
async def get_specification(
    spec_id: str,
    service: CatalogService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceSpecificationResponse:
    """Retrieve a single ``ServiceSpecification`` by its UUID."""
    return await service.get_specification(spec_id)


# ── PUT /{id} ─────────────────────────────────────────────────────────────────

@router.put(
    "/{spec_id}",
    response_model=ServiceSpecificationResponse,
    summary="Replace a ServiceSpecification",
    status_code=status.HTTP_200_OK,
)
async def update_specification(
    spec_id: str,
    data: ServiceSpecificationUpdate,
    service: CatalogService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceSpecificationResponse:
    """Perform a full replacement of a ``ServiceSpecification`` (PUT semantics)."""
    return await service.update_specification(spec_id, data)


# ── PATCH /{id} ───────────────────────────────────────────────────────────────

@router.patch(
    "/{spec_id}",
    response_model=ServiceSpecificationResponse,
    summary="Partially update a ServiceSpecification",
    status_code=status.HTTP_200_OK,
)
async def patch_specification(
    spec_id: str,
    data: ServiceSpecificationPatch,
    service: CatalogService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceSpecificationResponse:
    """Apply a partial update to a ``ServiceSpecification`` (PATCH semantics)."""
    return await service.patch_specification(spec_id, data)


# ── DELETE /{id} ──────────────────────────────────────────────────────────────

@router.delete(
    "/{spec_id}",
    summary="Delete a ServiceSpecification",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_specification(
    spec_id: str,
    service: CatalogService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceSpecification``.

    Only specifications in ``draft`` or ``retired`` status may be deleted.
    """
    await service.delete_specification(spec_id)
