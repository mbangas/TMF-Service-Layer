"""TMF641 Service Order Management — ServiceOrderItemRelationship REST API router.

Base path:
    /tmf-api/serviceOrdering/v4/serviceOrder/{order_id}/serviceOrderItem/{item_id}/serviceOrderItemRelationship

Endpoints:
    GET    /              List all ServiceOrderItemRelationship entries for an order item
    POST   /              Create a new ServiceOrderItemRelationship
    DELETE /{rel_id}      Delete a ServiceOrderItemRelationship
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.order.models.schemas import (
    ServiceOrderItemRelationshipCreate,
    ServiceOrderItemRelationshipResponse,
)
from src.order.repositories.order_item_relationship_repo import OrderItemRelationshipRepository
from src.order.repositories.service_order_repo import ServiceOrderRepository
from src.order.services.order_service import OrderService
from src.shared.auth.dependencies import CurrentUser, get_current_user
from src.shared.db.session import get_db

router = APIRouter(
    prefix=(
        "/tmf-api/serviceOrdering/v4"
        "/serviceOrder/{order_id}/serviceOrderItem/{item_id}/serviceOrderItemRelationship"
    ),
    tags=["TMF641 - Service Order Item Relationship"],
)


def _get_service(db: AsyncSession = Depends(get_db)) -> OrderService:
    """Build OrderService with order + item relationship repositories."""
    svc = OrderService(repo=ServiceOrderRepository(db))
    svc._item_rel_repo = OrderItemRelationshipRepository(db)
    return svc


# ── GET / ─────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[ServiceOrderItemRelationshipResponse],
    summary="List ServiceOrderItemRelationships",
    status_code=status.HTTP_200_OK,
)
async def list_item_relationships(
    order_id: str,
    item_id: str,
    response: Response,
    service: OrderService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> list[ServiceOrderItemRelationshipResponse]:
    """List all ``ServiceOrderItemRelationship`` entries for a ServiceOrderItem.

    Use ``relationship_type: dependency`` to model precedence constraints
    between items (item B depends on item A completing first).
    """
    items = await service.list_order_item_relationships(order_id, item_id)
    response.headers["X-Total-Count"] = str(len(items))
    response.headers["X-Result-Count"] = str(len(items))
    return items


# ── POST / ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ServiceOrderItemRelationshipResponse,
    summary="Create a ServiceOrderItemRelationship",
    status_code=status.HTTP_201_CREATED,
)
async def create_item_relationship(
    order_id: str,
    item_id: str,
    data: ServiceOrderItemRelationshipCreate,
    service: OrderService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> ServiceOrderItemRelationshipResponse:
    """Create a new ``ServiceOrderItemRelationship``.

    The ``related_item_label`` must reference the client-assigned ``order_item_id``
    of another item within the same order.  Self-reference is rejected (422).
    """
    return await service.add_order_item_relationship(order_id, item_id, data)


# ── DELETE /{rel_id} ──────────────────────────────────────────────────────────

@router.delete(
    "/{rel_id}",
    summary="Delete a ServiceOrderItemRelationship",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_item_relationship(
    order_id: str,
    item_id: str,
    rel_id: str,
    service: OrderService = Depends(_get_service),
    _current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a ``ServiceOrderItemRelationship`` by its UUID."""
    await service.delete_order_item_relationship(order_id, item_id, rel_id)
