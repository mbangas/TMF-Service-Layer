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

    def __init__(self, repo: ServiceOrderRepository) -> None:
        self._repo = repo

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
        if data.state is not None and data.state != existing.state:
            _validate_state_transition(existing.state, data.state)
            state_changed = True

            # Auto-set completion_date when entering terminal state
            if data.state in _TERMINAL_STATES:

                existing.completion_date = datetime.now(tz=timezone.utc)

        orm = await self._repo.patch(order_id, data)

        # After patch, re-apply completion_date if we set it on existing (dirty tracking)
        if state_changed and data.state in _TERMINAL_STATES:
            # Re-fetch to get the final state
            orm = await self._repo.get_by_id(order_id)

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
