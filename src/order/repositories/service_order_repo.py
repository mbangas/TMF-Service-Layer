"""Data-access layer for TMF641 ServiceOrder."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.order.models.orm import ServiceOrderItemOrm, ServiceOrderOrm
from src.order.models.schemas import ServiceOrderCreate, ServiceOrderPatch


class ServiceOrderRepository:
    """Async repository providing CRUD operations for ``ServiceOrder``.

    All methods accept an ``AsyncSession`` injected by the FastAPI dependency.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
    ) -> tuple[list[ServiceOrderOrm], int]:
        """Return a paginated list of service orders and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional filter by order state.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(ServiceOrderOrm)
        count_query = select(func.count()).select_from(ServiceOrderOrm)

        if state:
            base_query = base_query.where(ServiceOrderOrm.state == state)
            count_query = count_query.where(ServiceOrderOrm.state == state)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query.offset(offset).limit(limit).order_by(ServiceOrderOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, order_id: str) -> ServiceOrderOrm | None:
        """Fetch a single service order by its ID.

        Args:
            order_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceOrderOrm).where(ServiceOrderOrm.id == order_id)
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: ServiceOrderCreate, state: str, order_date) -> ServiceOrderOrm:
        """Persist a new ServiceOrder.

        Args:
            data: Validated create schema.
            state: Forced initial state (always "acknowledged").
            order_date: Server-assigned order date.

        Returns:
            The newly created ORM instance.
        """
        order_id = str(uuid.uuid4())

        orm = ServiceOrderOrm(
            id=order_id,
            href=f"/tmf-api/serviceOrdering/v4/serviceOrder/{order_id}",
            name=data.name,
            description=data.description,
            category=data.category,
            priority=data.priority,
            external_id=data.external_id,
            state=state,
            order_date=order_date,
            requested_start_date=data.requested_start_date,
            requested_completion_date=data.requested_completion_date,
            type=data.type,
            base_type=data.base_type,
            schema_location=data.schema_location,
        )

        for item in data.order_item:
            orm.order_item.append(
                ServiceOrderItemOrm(
                    id=str(uuid.uuid4()),
                    service_order_id=order_id,
                    order_item_id=item.order_item_id,
                    action=item.action,
                    state=item.state,
                    quantity=item.quantity,
                    service_spec_id=item.service_spec_id,
                    service_spec_href=item.service_spec_href,
                    service_spec_name=item.service_spec_name,
                    service_name=item.service_name,
                    service_description=item.service_description,
                    note=item.note,
                )
            )

        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(
        self,
        order_id: str,
        data: ServiceOrderPatch,
        extra_fields: dict[str, object] | None = None,
    ) -> ServiceOrderOrm | None:
        """Partial update of a ServiceOrder (PATCH semantics).

        Only non-None fields in ``data`` overwrite existing values.
        Additional server-side fields (e.g. ``completion_date``) can be
        supplied via ``extra_fields`` and are applied after the schema fields.

        Args:
            order_id: Identifier of the order to patch.
            data: Partial patch schema.
            extra_fields: Optional dict of extra column name → value pairs
                applied directly to the ORM (not exposed in the API schema).

        Returns:
            Patched ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(order_id)
        if orm is None:
            return None

        patch_data = data.model_dump(exclude_none=True, by_alias=False)

        for field, value in patch_data.items():
            if hasattr(orm, field):
                setattr(orm, field, value)

        if extra_fields:
            for field, value in extra_fields.items():
                if hasattr(orm, field):
                    setattr(orm, field, value)

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, order_id: str) -> bool:
        """Delete a ServiceOrder by ID.

        Args:
            order_id: Identifier of the order to delete.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(order_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
