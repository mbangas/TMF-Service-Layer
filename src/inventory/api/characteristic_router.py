"""TMF638 Service Inventory — ServiceCharacteristic REST API router.

Base path:
    /tmf-api/serviceInventory/v4/service/{service_id}/serviceCharacteristic

Endpoints:
    GET    /                              List all characteristics for a service
    POST   /                              Create a new characteristic
    GET    /{char_id}                     Retrieve a single characteristic
    PATCH  /{char_id}                     Partial update of a characteristic
    DELETE /{char_id}                     Delete a characteristic

    GET    /{char_id}/characteristicValue           List values
    POST   /{char_id}/characteristicValue           Create a value
    GET    /{char_id}/characteristicValue/{val_id}  Retrieve a value
    DELETE /{char_id}/characteristicValue/{val_id}  Delete a value
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.inventory.models.schemas import (
    CharacteristicValueCreate,
    CharacteristicValueResponse,
    ServiceCharacteristicCreate,
    ServiceCharacteristicPatch,
    ServiceCharacteristicResponse,
)
from src.inventory.repositories.characteristic_repo import (
    CharacteristicValueRepository,
    ServiceCharacteristicRepository,
)
from src.inventory.repositories.service_repo import ServiceRepository
from src.inventory.services.characteristic_service import (
    CharacteristicValueService,
    ServiceCharacteristicService,
)
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix="/tmf-api/serviceInventory/v4/service/{service_id}/serviceCharacteristic",
    tags=["TMF638 - Service Characteristic"],
)


# ── Dependency factories ───────────────────────────────────────────────────────

def _get_char_service(db: AsyncSession = Depends(get_db)) -> ServiceCharacteristicService:
    """Build ServiceCharacteristicService with its repositories."""
    return ServiceCharacteristicService(
        repo=ServiceCharacteristicRepository(db),
        service_repo=ServiceRepository(db),
    )


def _get_val_service(db: AsyncSession = Depends(get_db)) -> CharacteristicValueService:
    """Build CharacteristicValueService with its repositories."""
    return CharacteristicValueService(
        repo=CharacteristicValueRepository(db),
        char_repo=ServiceCharacteristicRepository(db),
        service_repo=ServiceRepository(db),
    )


# ── ServiceCharacteristic CRUD ────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ServiceCharacteristicResponse],
    summary="List ServiceCharacteristics",
    status_code=status.HTTP_200_OK,
)
async def list_characteristics(
    service_id: str,
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: ServiceCharacteristicService = Depends(_get_char_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceCharacteristicResponse]:
    """List all ``ServiceCharacteristic`` resources for a service instance."""
    items, total = await service.list_characteristics(service_id, offset, limit)
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@router.post(
    "",
    response_model=ServiceCharacteristicResponse,
    summary="Create a ServiceCharacteristic",
    status_code=status.HTTP_201_CREATED,
)
async def create_characteristic(
    service_id: str,
    data: ServiceCharacteristicCreate,
    service: ServiceCharacteristicService = Depends(_get_char_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCharacteristicResponse:
    """Create a new ``ServiceCharacteristic`` under the given service instance."""
    return await service.create_characteristic(service_id, data)


@router.get(
    "/{char_id}",
    response_model=ServiceCharacteristicResponse,
    summary="Retrieve a ServiceCharacteristic",
    status_code=status.HTTP_200_OK,
)
async def get_characteristic(
    service_id: str,
    char_id: str,
    service: ServiceCharacteristicService = Depends(_get_char_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCharacteristicResponse:
    """Retrieve a single ``ServiceCharacteristic`` by its UUID."""
    return await service.get_characteristic(service_id, char_id)


@router.patch(
    "/{char_id}",
    response_model=ServiceCharacteristicResponse,
    summary="Partially update a ServiceCharacteristic",
    status_code=status.HTTP_200_OK,
)
async def patch_characteristic(
    service_id: str,
    char_id: str,
    data: ServiceCharacteristicPatch,
    service: ServiceCharacteristicService = Depends(_get_char_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceCharacteristicResponse:
    """Apply a partial update to a ``ServiceCharacteristic`` (PATCH semantics)."""
    return await service.patch_characteristic(service_id, char_id, data)


@router.delete(
    "/{char_id}",
    summary="Delete a ServiceCharacteristic",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_characteristic(
    service_id: str,
    char_id: str,
    service: ServiceCharacteristicService = Depends(_get_char_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceCharacteristic`` and all its values."""
    await service.delete_characteristic(service_id, char_id)


# ── CharacteristicValue sub-resource ─────────────────────────────────────────

@router.get(
    "/{char_id}/characteristicValue",
    response_model=list[CharacteristicValueResponse],
    summary="List CharacteristicValues",
    status_code=status.HTTP_200_OK,
)
async def list_values(
    service_id: str,
    char_id: str,
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: CharacteristicValueService = Depends(_get_val_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[CharacteristicValueResponse]:
    """List all runtime values for a service characteristic."""
    items, total = await service.list_values(service_id, char_id, offset, limit)
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


@router.post(
    "/{char_id}/characteristicValue",
    response_model=CharacteristicValueResponse,
    summary="Create a CharacteristicValue",
    status_code=status.HTTP_201_CREATED,
)
async def create_value(
    service_id: str,
    char_id: str,
    data: CharacteristicValueCreate,
    service: CharacteristicValueService = Depends(_get_val_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> CharacteristicValueResponse:
    """Create a new runtime value for the given characteristic."""
    return await service.create_value(service_id, char_id, data)


@router.get(
    "/{char_id}/characteristicValue/{val_id}",
    response_model=CharacteristicValueResponse,
    summary="Retrieve a CharacteristicValue",
    status_code=status.HTTP_200_OK,
)
async def get_value(
    service_id: str,
    char_id: str,
    val_id: str,
    service: CharacteristicValueService = Depends(_get_val_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> CharacteristicValueResponse:
    """Retrieve a single ``CharacteristicValue`` by its UUID."""
    return await service.get_value(service_id, char_id, val_id)


@router.delete(
    "/{char_id}/characteristicValue/{val_id}",
    summary="Delete a CharacteristicValue",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_value(
    service_id: str,
    char_id: str,
    val_id: str,
    service: CharacteristicValueService = Depends(_get_val_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``CharacteristicValue``."""
    await service.delete_value(service_id, char_id, val_id)
