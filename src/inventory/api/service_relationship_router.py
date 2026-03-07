"""TMF638 Service Inventory Management — ServiceRelationship REST API router.

Base path:
    /tmf-api/serviceInventory/v4/service/{service_id}/serviceRelationship

Endpoints:
    GET    /              List all ServiceRelationship entries for a service
    POST   /              Create a new ServiceRelationship
    DELETE /{rel_id}      Delete a ServiceRelationship
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.inventory.models.schemas import ServiceRelationshipCreate, ServiceRelationshipResponse
from src.inventory.repositories.service_relationship_repo import ServiceRelationshipRepository
from src.inventory.repositories.service_repo import ServiceRepository
from src.inventory.services.inventory_service import InventoryService
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix="/tmf-api/serviceInventory/v4/service/{service_id}/serviceRelationship",
    tags=["TMF638 - Service Relationship"],
)


def _get_service(db: AsyncSession = Depends(get_db)) -> InventoryService:
    """Dependency factory — builds ``InventoryService`` with its relationship repository."""
    svc = InventoryService(ServiceRepository(db))
    svc._rel_repo = ServiceRelationshipRepository(db)
    return svc


# ── GET / ─────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ServiceRelationshipResponse],
    summary="List ServiceRelationships",
    status_code=status.HTTP_200_OK,
)
async def list_service_relationships(
    service_id: str,
    response: Response,
    service: InventoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceRelationshipResponse]:
    """List all ``ServiceRelationship`` entries for a Service instance.

    These are created automatically when an order item with spec-level
    ``ServiceSpecRelationship`` entries completes (SID GB922 propagation).
    Additional ad-hoc relationships can be created manually via POST.
    """
    items = await service.list_service_relationships(service_id)
    response.headers["X-Total-Count"] = str(len(items))
    response.headers["X-Result-Count"] = str(len(items))
    return items


# ── POST / ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ServiceRelationshipResponse,
    summary="Create a ServiceRelationship",
    status_code=status.HTTP_201_CREATED,
)
async def create_service_relationship(
    service_id: str,
    data: ServiceRelationshipCreate,
    service: InventoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceRelationshipResponse:
    """Create a new ``ServiceRelationship`` between two Service instances.

    The ``related_service_id`` must reference an existing service.  Self-reference
    and duplicate (service_id, related_service_id, relationship_type) triples are
    rejected with 409/422 respectively.
    """
    return await service.add_service_relationship(service_id, data)


# ── DELETE /{rel_id} ──────────────────────────────────────────────────────────

@router.delete(
    "/{rel_id}",
    summary="Delete a ServiceRelationship",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_service_relationship(
    service_id: str,
    rel_id: str,
    service: InventoryService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceRelationship`` by its UUID."""
    await service.delete_service_relationship(service_id, rel_id)
