"""TMF633 Service Catalog Management — ServiceCategory REST API router.

Base path: /tmf-api/serviceCatalogManagement/v4/serviceCategory

Endpoints:
    GET    /              List all categories (paginated)
    POST   /              Create a new category
    GET    /{id}          Retrieve a single category
    PUT    /{id}          Full replacement of a category
    PATCH  /{id}          Partial update of a category
    DELETE /{id}          Delete a category
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models.schemas import (
    ServiceCategoryCreate,
    ServiceCategoryPatch,
    ServiceCategoryResponse,
    ServiceCategoryUpdate,
)
from src.catalog.repositories.service_category_repo import ServiceCategoryRepository
from src.catalog.services.tmfc006_service import ServiceCategoryService
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix="/tmf-api/serviceCatalogManagement/v4/serviceCategory",
    tags=["TMF633 - Service Catalog (TMFC006)"],
)


def _get_service(db: AsyncSession = Depends(get_db)) -> ServiceCategoryService:
    """Dependency factory — builds ServiceCategoryService with its repository."""
    return ServiceCategoryService(ServiceCategoryRepository(db))


@router.get(
    "",
    response_model=list[ServiceCategoryResponse],
    summary="List ServiceCategories",
    status_code=status.HTTP_200_OK,
)
async def list_categories(
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    lifecycle_status: str | None = Query(default=None),
    is_root: bool | None = Query(default=None, description="Filter root categories only"),
    service: ServiceCategoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceCategoryResponse]:
    """Retrieve a paginated list of ``ServiceCategory`` resources."""
    items, total = await service.list_categories(
        offset=offset,
        limit=limit,
        lifecycle_status=lifecycle_status,
        is_root=is_root,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@router.post(
    "",
    response_model=ServiceCategoryResponse,
    summary="Create a ServiceCategory",
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    data: ServiceCategoryCreate,
    service: ServiceCategoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCategoryResponse:
    """Create a new ``ServiceCategory`` resource (TMF633)."""
    return await service.create_category(data)


@router.get(
    "/{category_id}",
    response_model=ServiceCategoryResponse,
    summary="Retrieve a ServiceCategory",
    status_code=status.HTTP_200_OK,
)
async def get_category(
    category_id: str,
    service: ServiceCategoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCategoryResponse:
    """Retrieve a single ``ServiceCategory`` by its UUID."""
    return await service.get_category(category_id)


@router.put(
    "/{category_id}",
    response_model=ServiceCategoryResponse,
    summary="Replace a ServiceCategory",
    status_code=status.HTTP_200_OK,
)
async def update_category(
    category_id: str,
    data: ServiceCategoryUpdate,
    service: ServiceCategoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCategoryResponse:
    """Perform a full replacement of a ``ServiceCategory`` (PUT semantics)."""
    return await service.update_category(category_id, data)


@router.patch(
    "/{category_id}",
    response_model=ServiceCategoryResponse,
    summary="Partially update a ServiceCategory",
    status_code=status.HTTP_200_OK,
)
async def patch_category(
    category_id: str,
    data: ServiceCategoryPatch,
    service: ServiceCategoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCategoryResponse:
    """Apply a partial update to a ``ServiceCategory`` (PATCH semantics)."""
    return await service.patch_category(category_id, data)


@router.delete(
    "/{category_id}",
    summary="Delete a ServiceCategory",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_category(
    category_id: str,
    service: ServiceCategoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceCategory``.

    Only categories in ``draft`` or ``retired`` status may be deleted.
    """
    await service.delete_category(category_id)
