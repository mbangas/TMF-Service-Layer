"""TMF633 Service Catalog Management — ServiceCatalog REST API router.

Base path: /tmf-api/serviceCatalogManagement/v4/serviceCatalog

Endpoints:
    GET    /              List all catalogs (paginated)
    POST   /              Create a new catalog
    GET    /{id}          Retrieve a single catalog
    PUT    /{id}          Full replacement of a catalog
    PATCH  /{id}          Partial update of a catalog
    DELETE /{id}          Delete a catalog
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models.schemas import (
    ServiceCatalogCreate,
    ServiceCatalogPatch,
    ServiceCatalogResponse,
    ServiceCatalogUpdate,
)
from src.catalog.repositories.service_catalog_repo import ServiceCatalogRepository
from src.catalog.services.tmfc006_service import ServiceCatalogContainerService
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix="/tmf-api/serviceCatalogManagement/v4/serviceCatalog",
    tags=["TMF633 - Service Catalog (TMFC006)"],
)


def _get_service(db: AsyncSession = Depends(get_db)) -> ServiceCatalogContainerService:
    """Dependency factory — builds ServiceCatalogContainerService."""
    return ServiceCatalogContainerService(ServiceCatalogRepository(db))


@router.get(
    "",
    response_model=list[ServiceCatalogResponse],
    summary="List ServiceCatalogs",
    status_code=status.HTTP_200_OK,
)
async def list_catalogs(
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    lifecycle_status: str | None = Query(default=None),
    service: ServiceCatalogContainerService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceCatalogResponse]:
    """Retrieve a paginated list of ``ServiceCatalog`` resources."""
    items, total = await service.list_catalogs(
        offset=offset,
        limit=limit,
        lifecycle_status=lifecycle_status,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@router.post(
    "",
    response_model=ServiceCatalogResponse,
    summary="Create a ServiceCatalog",
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog(
    data: ServiceCatalogCreate,
    service: ServiceCatalogContainerService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCatalogResponse:
    """Create a new ``ServiceCatalog`` resource (TMF633)."""
    return await service.create_catalog(data)


@router.get(
    "/{catalog_id}",
    response_model=ServiceCatalogResponse,
    summary="Retrieve a ServiceCatalog",
    status_code=status.HTTP_200_OK,
)
async def get_catalog(
    catalog_id: str,
    service: ServiceCatalogContainerService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCatalogResponse:
    """Retrieve a single ``ServiceCatalog`` by its UUID."""
    return await service.get_catalog(catalog_id)


@router.put(
    "/{catalog_id}",
    response_model=ServiceCatalogResponse,
    summary="Replace a ServiceCatalog",
    status_code=status.HTTP_200_OK,
)
async def update_catalog(
    catalog_id: str,
    data: ServiceCatalogUpdate,
    service: ServiceCatalogContainerService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCatalogResponse:
    """Perform a full replacement of a ``ServiceCatalog`` (PUT semantics)."""
    return await service.update_catalog(catalog_id, data)


@router.patch(
    "/{catalog_id}",
    response_model=ServiceCatalogResponse,
    summary="Partially update a ServiceCatalog",
    status_code=status.HTTP_200_OK,
)
async def patch_catalog(
    catalog_id: str,
    data: ServiceCatalogPatch,
    service: ServiceCatalogContainerService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCatalogResponse:
    """Apply a partial update to a ``ServiceCatalog`` (PATCH semantics)."""
    return await service.patch_catalog(catalog_id, data)


@router.delete(
    "/{catalog_id}",
    summary="Delete a ServiceCatalog",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_catalog(
    catalog_id: str,
    service: ServiceCatalogContainerService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceCatalog``.

    Only catalogs in ``draft`` or ``retired`` status may be deleted.
    """
    await service.delete_catalog(catalog_id)
