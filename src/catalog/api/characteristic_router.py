"""TMF633 Service Catalog Management — ServiceSpecCharacteristic REST API router.

Base path:
    /tmf-api/serviceCatalogManagement/v4/serviceSpecification/{spec_id}/serviceSpecCharacteristic

Endpoints:
    GET    /                              List all characteristics for a specification
    POST   /                              Create a new characteristic
    GET    /{char_id}                     Retrieve a single characteristic
    PATCH  /{char_id}                     Partial update of a characteristic
    DELETE /{char_id}                     Delete a characteristic

    GET    /{char_id}/characteristicValueSpecification           List value specs
    POST   /{char_id}/characteristicValueSpecification           Create a value spec
    GET    /{char_id}/characteristicValueSpecification/{vs_id}   Retrieve a value spec
    DELETE /{char_id}/characteristicValueSpecification/{vs_id}   Delete a value spec
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models.schemas import (
    CharacteristicValueSpecCreate,
    CharacteristicValueSpecResponse,
    ServiceSpecCharacteristicCreate,
    ServiceSpecCharacteristicPatch,
    ServiceSpecCharacteristicResponse,
)
from src.catalog.repositories.characteristic_repo import (
    CharacteristicSpecRepository,
    CharacteristicValueSpecRepository,
)
from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.catalog.services.characteristic_service import (
    CharacteristicSpecService,
    CharacteristicValueSpecService,
)
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix=(
        "/tmf-api/serviceCatalogManagement/v4"
        "/serviceSpecification/{spec_id}/serviceSpecCharacteristic"
    ),
    tags=["TMF633 - Service Spec Characteristic"],
)


# ── Dependency factories ───────────────────────────────────────────────────────

def _get_char_service(db: AsyncSession = Depends(get_db)) -> CharacteristicSpecService:
    """Build CharacteristicSpecService with its repositories."""
    return CharacteristicSpecService(
        repo=CharacteristicSpecRepository(db),
        spec_repo=ServiceSpecificationRepository(db),
    )


def _get_vs_service(db: AsyncSession = Depends(get_db)) -> CharacteristicValueSpecService:
    """Build CharacteristicValueSpecService with its repositories."""
    return CharacteristicValueSpecService(
        repo=CharacteristicValueSpecRepository(db),
        char_repo=CharacteristicSpecRepository(db),
        spec_repo=ServiceSpecificationRepository(db),
    )


# ── ServiceSpecCharacteristic CRUD ────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ServiceSpecCharacteristicResponse],
    summary="List ServiceSpecCharacteristics",
    status_code=status.HTTP_200_OK,
)
async def list_characteristics(
    spec_id: str,
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: CharacteristicSpecService = Depends(_get_char_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceSpecCharacteristicResponse]:
    """List all ``ServiceSpecCharacteristic`` resources for a specification."""
    items, total = await service.list_characteristics(spec_id, offset, limit)
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@router.post(
    "",
    response_model=ServiceSpecCharacteristicResponse,
    summary="Create a ServiceSpecCharacteristic",
    status_code=status.HTTP_201_CREATED,
)
async def create_characteristic(
    spec_id: str,
    data: ServiceSpecCharacteristicCreate,
    service: CharacteristicSpecService = Depends(_get_char_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceSpecCharacteristicResponse:
    """Create a new ``ServiceSpecCharacteristic`` under the given specification."""
    return await service.create_characteristic(spec_id, data)


@router.get(
    "/{char_id}",
    response_model=ServiceSpecCharacteristicResponse,
    summary="Retrieve a ServiceSpecCharacteristic",
    status_code=status.HTTP_200_OK,
)
async def get_characteristic(
    spec_id: str,
    char_id: str,
    service: CharacteristicSpecService = Depends(_get_char_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceSpecCharacteristicResponse:
    """Retrieve a single ``ServiceSpecCharacteristic`` by its UUID."""
    return await service.get_characteristic(spec_id, char_id)


@router.patch(
    "/{char_id}",
    response_model=ServiceSpecCharacteristicResponse,
    summary="Partially update a ServiceSpecCharacteristic",
    status_code=status.HTTP_200_OK,
)
async def patch_characteristic(
    spec_id: str,
    char_id: str,
    data: ServiceSpecCharacteristicPatch,
    service: CharacteristicSpecService = Depends(_get_char_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceSpecCharacteristicResponse:
    """Apply a partial update to a ``ServiceSpecCharacteristic`` (PATCH semantics)."""
    return await service.patch_characteristic(spec_id, char_id, data)


@router.delete(
    "/{char_id}",
    summary="Delete a ServiceSpecCharacteristic",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_characteristic(
    spec_id: str,
    char_id: str,
    service: CharacteristicSpecService = Depends(_get_char_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceSpecCharacteristic`` and all its value specifications."""
    await service.delete_characteristic(spec_id, char_id)


# ── CharacteristicValueSpecification sub-resource ────────────────────────────

@router.get(
    "/{char_id}/characteristicValueSpecification",
    response_model=list[CharacteristicValueSpecResponse],
    summary="List CharacteristicValueSpecifications",
    status_code=status.HTTP_200_OK,
)
async def list_value_specs(
    spec_id: str,
    char_id: str,
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: CharacteristicValueSpecService = Depends(_get_vs_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[CharacteristicValueSpecResponse]:
    """List all allowed value specifications for a characteristic."""
    items, total = await service.list_value_specs(spec_id, char_id, offset, limit)
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@router.post(
    "/{char_id}/characteristicValueSpecification",
    response_model=CharacteristicValueSpecResponse,
    summary="Create a CharacteristicValueSpecification",
    status_code=status.HTTP_201_CREATED,
)
async def create_value_spec(
    spec_id: str,
    char_id: str,
    data: CharacteristicValueSpecCreate,
    service: CharacteristicValueSpecService = Depends(_get_vs_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> CharacteristicValueSpecResponse:
    """Create a new allowed value specification for the given characteristic."""
    return await service.create_value_spec(spec_id, char_id, data)


@router.get(
    "/{char_id}/characteristicValueSpecification/{vs_id}",
    response_model=CharacteristicValueSpecResponse,
    summary="Retrieve a CharacteristicValueSpecification",
    status_code=status.HTTP_200_OK,
)
async def get_value_spec(
    spec_id: str,
    char_id: str,
    vs_id: str,
    service: CharacteristicValueSpecService = Depends(_get_vs_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> CharacteristicValueSpecResponse:
    """Retrieve a single ``CharacteristicValueSpecification`` by its UUID."""
    return await service.get_value_spec(spec_id, char_id, vs_id)


@router.delete(
    "/{char_id}/characteristicValueSpecification/{vs_id}",
    summary="Delete a CharacteristicValueSpecification",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_value_spec(
    spec_id: str,
    char_id: str,
    vs_id: str,
    service: CharacteristicValueSpecService = Depends(_get_vs_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``CharacteristicValueSpecification``."""
    await service.delete_value_spec(spec_id, char_id, vs_id)
