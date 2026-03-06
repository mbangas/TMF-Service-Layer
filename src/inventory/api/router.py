"""TMF638 Service Inventory Management — REST API router.

Base path: /tmf-api/serviceInventory/v4/service

Endpoints:
    GET    /              List all service instances (paginated, filterable)
    POST   /              Create a new service instance
    GET    /{id}          Retrieve a single service instance
    PATCH  /{id}          Partial update / lifecycle transition
    DELETE /{id}          Delete a service instance (only if terminated or inactive)
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.inventory.models.schemas import ServiceCreate, ServicePatch, ServiceResponse
from src.inventory.repositories.service_repo import ServiceRepository
from src.inventory.services.inventory_service import InventoryService
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix="/tmf-api/serviceInventory/v4/service",
    tags=["TMF638 - Service Inventory"],
)


def _get_service(db: AsyncSession = Depends(get_db)) -> InventoryService:
    """Dependency factory — builds the InventoryService with its repository."""
    repo = ServiceRepository(db)
    return InventoryService(repo)


# ── GET / ─────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ServiceResponse],
    summary="List Service instances",
    status_code=status.HTTP_200_OK,
)
async def list_services(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by lifecycle state"),
    service: InventoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceResponse]:
    """Retrieve a paginated list of ``Service`` instances (TMF638 §6.1.1).

    TMF-style pagination: ``offset`` / ``limit`` query params +
    ``X-Total-Count`` and ``X-Result-Count`` response headers.
    """
    items, total = await service.list_services(offset=offset, limit=limit, state=state)
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


# ── POST / ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ServiceResponse,
    summary="Create a Service instance",
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    data: ServiceCreate,
    service: InventoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceResponse:
    """Create a new ``Service`` inventory record (TMF638 §6.1.1).

    The initial state must be a non-terminal state.
    ``state`` defaults to ``inactive`` if not supplied.
    """
    return await service.create_service(data)


# ── GET /{id} ─────────────────────────────────────────────────────────────────

@router.get(
    "/{service_id}",
    response_model=ServiceResponse,
    summary="Retrieve a Service instance",
    status_code=status.HTTP_200_OK,
)
async def get_service(
    service_id: str,
    service: InventoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceResponse:
    """Retrieve a single ``Service`` by its ID (TMF638 §6.1.2).

    Raises 404 if no service with the given ID exists.
    """
    return await service.get_service(service_id)


# ── PATCH /{id} ───────────────────────────────────────────────────────────────

@router.patch(
    "/{service_id}",
    response_model=ServiceResponse,
    summary="Update a Service instance",
    status_code=status.HTTP_200_OK,
)
async def patch_service(
    service_id: str,
    data: ServicePatch,
    service: InventoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceResponse:
    """Partially update a ``Service`` instance (TMF638 §6.1.4).

    Use this endpoint to drive lifecycle transitions by updating the ``state``
    field.  Invalid transitions are rejected with 422.
    """
    return await service.patch_service(service_id, data)


# ── DELETE /{id} ──────────────────────────────────────────────────────────────

@router.delete(
    "/{service_id}",
    summary="Delete a Service instance",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        409: {"description": "Service is referenced by another entity"},
        422: {"description": "Service state does not permit deletion"},
    },
)
async def delete_service(
    service_id: str,
    service: InventoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``Service`` instance (TMF638 §6.1.5).

    Only ``terminated`` or ``inactive`` services may be deleted.
    Returns 422 if the service is in an active state.
    Returns 409 if the service is referenced by another entity.
    """
    await service.delete_service(service_id)
