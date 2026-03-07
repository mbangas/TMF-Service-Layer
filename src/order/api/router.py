"""TMF641 Service Order Management — REST API router.

Base path: /tmf-api/serviceOrdering/v4/serviceOrder

Endpoints:
    GET    /              List all service orders (paginated, filterable by state)
    POST   /              Create a new service order
    GET    /{id}          Retrieve a single service order
    PATCH  /{id}          Partial update / lifecycle transition
    DELETE /{id}          Delete a service order (only if cancelled)
"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.order.models.schemas import (
    ServiceOrderCreate,
    ServiceOrderPatch,
    ServiceOrderResponse,
)
from src.inventory.repositories.service_repo import ServiceRepository as InventoryRepository
from src.inventory.repositories.service_relationship_repo import ServiceRelationshipRepository
from src.inventory.services.inventory_service import InventoryService
from src.order.repositories.service_order_repo import ServiceOrderRepository
from src.order.services.order_service import OrderService
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix="/tmf-api/serviceOrdering/v4/serviceOrder",
    tags=["TMF641 - Service Order"],
)

_BASE_PATH = "/tmf-api/serviceOrdering/v4/serviceOrder"


def _get_service(db: AsyncSession = Depends(get_db)) -> OrderService:
    """Dependency factory — builds the OrderService with its repository.

    Also injects an ``InventoryService`` so that completed orders
    automatically provision ``Service`` records in TMF638 inventory.
    """
    order_repo = ServiceOrderRepository(db)
    inventory_repo = InventoryRepository(db)
    inventory_service = InventoryService(inventory_repo)
    inventory_service._rel_repo = ServiceRelationshipRepository(db)
    return OrderService(order_repo, inventory_service=inventory_service)


# ── GET / ─────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ServiceOrderResponse],
    summary="List ServiceOrders",
    status_code=status.HTTP_200_OK,
)
async def list_orders(
    response: Response,
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    state: str | None = Query(default=None, description="Filter by order state"),
    service: OrderService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceOrderResponse]:
    """Retrieve a paginated list of ``ServiceOrder`` resources.

    TMF-style pagination: ``offset`` / ``limit`` query params +
    ``X-Total-Count`` and ``X-Result-Count`` response headers.
    """
    items, total = await service.list_orders(offset=offset, limit=limit, state=state)
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Result-Count"] = str(len(items))
    return items


# ── POST / ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ServiceOrderResponse,
    summary="Create a ServiceOrder",
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    data: ServiceOrderCreate,
    service: OrderService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceOrderResponse:
    """Create a new ``ServiceOrder`` resource (TMF641 §6.2.1).

    The initial state is always forced to ``acknowledged``; ``order_date`` is
    set server-side to the current UTC timestamp.
    """
    return await service.create_order(data)


# ── GET /{id} ─────────────────────────────────────────────────────────────────

@router.get(
    "/{order_id}",
    response_model=ServiceOrderResponse,
    summary="Retrieve a ServiceOrder",
    status_code=status.HTTP_200_OK,
)
async def get_order(
    order_id: str,
    service: OrderService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceOrderResponse:
    """Retrieve a single ``ServiceOrder`` by its UUID."""
    return await service.get_order(order_id)


# ── PATCH /{id} ───────────────────────────────────────────────────────────────

@router.patch(
    "/{order_id}",
    response_model=ServiceOrderResponse,
    summary="Partially update a ServiceOrder",
    status_code=status.HTTP_200_OK,
)
async def patch_order(
    order_id: str,
    data: ServiceOrderPatch,
    service: OrderService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceOrderResponse:
    """Apply a partial update to a ``ServiceOrder``.

    Pass ``state`` to trigger a lifecycle transition.  Invalid transitions
    return 422.  Entering a terminal state auto-sets ``completion_date``.
    """
    return await service.patch_order(order_id, data)


# ── DELETE /{id} ──────────────────────────────────────────────────────────────

@router.delete(
    "/{order_id}",
    summary="Delete a ServiceOrder",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_order(
    order_id: str,
    service: OrderService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceOrder``.

    Only orders in ``cancelled`` state may be deleted.
    """
    await service.delete_order(order_id)
