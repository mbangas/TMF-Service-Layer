"""Business logic and lifecycle state machine for TMF641 Service Order Management.

Lifecycle state transitions (TMF641):

    acknowledged ──► inProgress ──► completed
                  │               └──► failed
                  └──► cancelled

Terminal states (completed, failed, cancelled) accept no further transitions.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status

from src.order.models.orm import ServiceOrderOrm
from src.order.models.schemas import (
    ServiceOrderCreate,
    ServiceOrderItemRelationshipCreate,
    ServiceOrderItemRelationshipResponse,
    ServiceOrderPatch,
    ServiceOrderResponse,
)
from src.order.repositories.service_order_repo import ServiceOrderRepository
from src.shared.events.bus import EventBus
from src.shared.events.schemas import EventPayload, TMFEvent

# Allowed lifecycle transitions: {from_state: {allowed_to_states}}
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "acknowledged": {"inProgress", "cancelled"},
    "inProgress": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}

_TERMINAL_STATES = {"completed", "failed", "cancelled"}


def _validate_state_transition(current: str, requested: str) -> None:
    """Raise 422 if the state transition is not permitted.

    Args:
        current: Current state of the service order.
        requested: Requested target state.

    Raises:
        :class:`fastapi.HTTPException` (422) if the transition is invalid.
    """
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid state transition from '{current}' to '{requested}'. "
                f"Allowed targets: {sorted(allowed) if allowed else 'none (terminal state)'}"
            ),
        )


def _orm_to_response(orm: ServiceOrderOrm) -> ServiceOrderResponse:
    """Map an ORM instance to the API response schema.

    Args:
        orm: The SQLAlchemy ORM instance.

    Returns:
        A :class:`ServiceOrderResponse` ready for serialisation.
    """
    return ServiceOrderResponse.model_validate(orm)


class OrderService:
    """Service layer for TMF641 ServiceOrder.

    Applies business rules (lifecycle state machine, date auto-assignment,
    event publishing) on top of the raw data-access operations from the repository.
    """

    def __init__(
        self,
        repo: ServiceOrderRepository,
        inventory_service: object | None = None,
    ) -> None:
        self._repo = repo
        self._inventory_service = inventory_service
        self._item_rel_repo: object | None = None

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_orders(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
    ) -> tuple[list[ServiceOrderResponse], int]:
        """Return a paginated list of service orders.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to include.
            state: Optional state filter.

        Returns:
            Tuple of (response items, total count).
        """
        items, total = await self._repo.get_all(offset=offset, limit=limit, state=state)
        return [_orm_to_response(item) for item in items], total

    async def get_order(self, order_id: str) -> ServiceOrderResponse:
        """Retrieve a single service order or raise 404.

        Args:
            order_id: The order UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.

        Returns:
            The order response.
        """
        orm = await self._repo.get_by_id(order_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceOrder '{order_id}' not found.",
            )
        return _orm_to_response(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_order(self, data: ServiceOrderCreate) -> ServiceOrderResponse:
        """Create a new ServiceOrder.

        Forces the initial state to ``acknowledged`` and sets ``order_date``
        to the current UTC time.  Publishes a ``ServiceOrderCreateEvent``.

        Args:
            data: Validated create payload.

        Returns:
            The created order response.
        """
        state = "acknowledged"
        order_date = datetime.now(tz=timezone.utc)

        orm = await self._repo.create(data, state=state, order_date=order_date)
        response = _orm_to_response(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceOrderCreateEvent",
                domain="serviceOrdering",
                title="Service Order Created",
                description=f"ServiceOrder '{orm.id}' created with state '{state}'.",
                event=EventPayload(resource=response),
            )
        )

        return response

    async def patch_order(self, order_id: str, data: ServiceOrderPatch) -> ServiceOrderResponse:
        """Partial update of a ServiceOrder.

        Validates lifecycle transition when ``state`` is provided.  Sets
        ``completion_date`` automatically when entering a terminal state.
        Publishes a ``ServiceOrderStateChangeEvent`` if state changes.

        Args:
            order_id: ID of the order to patch.
            data: Partial patch payload.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if state transition is invalid.

        Returns:
            The patched order response.
        """
        existing = await self._repo.get_by_id(order_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceOrder '{order_id}' not found.",
            )

        state_changed = False
        extra_fields: dict[str, object] | None = None

        if data.state is not None and data.state != existing.state:
            _validate_state_transition(existing.state, data.state)
            state_changed = True

            # Auto-set completion_date when entering a terminal state.
            # Pass it via extra_fields so the repo writes it to the DB column.
            if data.state in _TERMINAL_STATES:
                extra_fields = {"completion_date": datetime.now(tz=timezone.utc)}

        orm = await self._repo.patch(order_id, data, extra_fields=extra_fields)

        response = _orm_to_response(orm)  # type: ignore[arg-type]

        if state_changed:
            EventBus.publish(
                TMFEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="ServiceOrderStateChangeEvent",
                    domain="serviceOrdering",
                    title="Service Order State Changed",
                    description=(
                        f"ServiceOrder '{order_id}' transitioned "
                        f"from '{existing.state}' to '{data.state}'."
                    ),
                    event=EventPayload(resource=response),
                )
            )

        # Auto-provision inventory when an order reaches 'completed'.
        # For each order item with action 'add' or 'modify', create an active
        # Service record in the inventory module.
        if data.state == "completed" and self._inventory_service is not None:
            from src.inventory.models.schemas import ServiceCreate  # noqa: PLC0415

            spec_id_to_service_id: dict[str, str] = {}
            for item in orm.order_item:  # type: ignore[union-attr]
                if item.action in {"add", "modify"}:
                    new_svc = await self._inventory_service.create_service(  # type: ignore[union-attr]
                        ServiceCreate(
                            name=item.service_name or item.service_spec_name or "Unnamed Service",
                            description=item.service_description,
                            state="active",
                            service_spec_id=item.service_spec_id,
                            service_order_id=order_id,
                        )
                    )
                    if item.service_spec_id:
                        spec_id_to_service_id[item.service_spec_id] = new_svc.id

            # Propagate spec-level dependency topology into inventory relationships
            if spec_id_to_service_id:
                await self._inventory_service.propagate_spec_relationships(  # type: ignore[union-attr]
                    spec_id_to_service_id
                )

        return response

    async def delete_order(self, order_id: str) -> None:
        """Delete a ServiceOrder.

        Only ``cancelled`` orders may be deleted.

        Args:
            order_id: ID of the order to delete.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
            :class:`fastapi.HTTPException` (422) if the order is not cancelled.
        """
        existing = await self._repo.get_by_id(order_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceOrder '{order_id}' not found.",
            )
        if existing.state != "cancelled":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot delete a service order in '{existing.state}' state. "
                    "Cancel the order first."
                ),
            )
        await self._repo.delete(order_id)

    # ── Order Item Relationships (TMF641 ServiceOrderItemRelationship) ───────

    def _item_rel_repo_instance(self):
        """Return the injected order item relationship repository."""
        if self._item_rel_repo is None:
            raise RuntimeError("OrderItemRelationshipRepository not injected.")
        return self._item_rel_repo

    async def list_order_item_relationships(
        self,
        order_id: str,
        item_id: str,
    ) -> list[ServiceOrderItemRelationshipResponse]:
        """List all ServiceOrderItemRelationship entries for a given order item.

        Args:
            order_id: The parent ServiceOrder UUID.
            item_id: The ServiceOrderItem DB UUID.

        Returns:
            List of relationship responses.
        """
        item = await self._resolve_item(order_id, item_id)
        items = await self._item_rel_repo_instance().get_all_by_item_id(item.id)
        return [
            ServiceOrderItemRelationshipResponse.model_validate(i) for i in items
        ]

    async def add_order_item_relationship(
        self,
        order_id: str,
        item_id: str,
        data: ServiceOrderItemRelationshipCreate,
    ) -> ServiceOrderItemRelationshipResponse:
        """Create a ServiceOrderItemRelationship between two items in the same order.

        Validates:
        - Both the owning and the referenced items belong to the same order.
        - No self-reference by label.
        - The ``related_item_label`` resolves to an existing order item.

        Args:
            order_id: The parent ServiceOrder UUID.
            item_id: DB UUID of the owning ServiceOrderItem.
            data: Validated create payload.

        Returns:
            The created relationship response.
        """
        item = await self._resolve_item(order_id, item_id)

        # Self-reference guard
        if data.related_item_label == item.order_item_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="An order item cannot reference itself as a dependency.",
            )

        # Validate related label exists in same order
        repo = self._item_rel_repo_instance()
        related_item = await repo.get_item_by_label(order_id, data.related_item_label)
        if related_item is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Order item with label '{data.related_item_label}' not found "
                    f"in order '{order_id}'."
                ),
            )

        orm = await repo.create(item.id, data)
        return ServiceOrderItemRelationshipResponse.model_validate(orm)

    async def delete_order_item_relationship(
        self,
        order_id: str,
        item_id: str,
        rel_id: str,
    ) -> None:
        """Delete a ServiceOrderItemRelationship.

        Args:
            order_id: UUID of the parent ServiceOrder.
            item_id: DB UUID of the owning ServiceOrderItem.
            rel_id: UUID of the relationship record.
        """
        item = await self._resolve_item(order_id, item_id)
        repo = self._item_rel_repo_instance()
        orm = await repo.get_by_id(rel_id)
        if orm is None or orm.order_item_orm_id != item.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceOrderItemRelationship '{rel_id}' not found for item '{item_id}'.",
            )
        await repo.delete(orm)

    async def _resolve_item(self, order_id: str, item_id: str):
        """Resolve and validate an order item belongs to the given order."""
        order = await self._repo.get_by_id(order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceOrder '{order_id}' not found.",
            )
        for item in order.order_item:
            if item.id == item_id:
                return item
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ServiceOrderItem '{item_id}' not found in order '{order_id}'.",
        )
