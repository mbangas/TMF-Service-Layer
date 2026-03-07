"""Data-access layer for TMF641 ServiceOrderItemRelationship."""

import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.order.models.orm import ServiceOrderItemOrm, ServiceOrderItemRelationshipOrm
from src.order.models.schemas import ServiceOrderItemRelationshipCreate


class OrderItemRelationshipRepository:
    """Async repository for CRUD operations on ``ServiceOrderItemRelationship``.

    All methods accept an ``AsyncSession`` injected by the FastAPI dependency.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_all_by_item_id(
        self,
        order_item_orm_id: str,
    ) -> list[ServiceOrderItemRelationshipOrm]:
        """Return all ServiceOrderItemRelationship entries for a given order item.

        Args:
            order_item_orm_id: The parent ServiceOrderItem DB UUID.

        Returns:
            List of ORM instances.
        """
        result = await self._db.execute(
            select(ServiceOrderItemRelationshipOrm)
            .where(ServiceOrderItemRelationshipOrm.order_item_orm_id == order_item_orm_id)
            .order_by(ServiceOrderItemRelationshipOrm.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, rel_id: str) -> ServiceOrderItemRelationshipOrm | None:
        """Fetch a single ServiceOrderItemRelationship by its ID.

        Args:
            rel_id: The UUID of the relationship record.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceOrderItemRelationshipOrm).where(
                ServiceOrderItemRelationshipOrm.id == rel_id
            )
        )
        return result.scalar_one_or_none()

    async def get_item_by_label(
        self,
        order_id: str,
        label: str,
    ) -> ServiceOrderItemOrm | None:
        """Resolve a client-assigned order_item_id label to an ORM record.

        TMF641: items reference each other by their client-assigned label string,
        not the internal DB UUID.

        Args:
            order_id: The parent ServiceOrder UUID.
            label: The ``order_item_id`` label string (e.g. ``"1"``).

        Returns:
            The matching ``ServiceOrderItemOrm`` or ``None``.
        """
        result = await self._db.execute(
            select(ServiceOrderItemOrm).where(
                and_(
                    ServiceOrderItemOrm.service_order_id == order_id,
                    ServiceOrderItemOrm.order_item_id == label,
                )
            )
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(
        self,
        order_item_orm_id: str,
        data: ServiceOrderItemRelationshipCreate,
    ) -> ServiceOrderItemRelationshipOrm:
        """Persist a new ServiceOrderItemRelationship.

        Args:
            order_item_orm_id: DB UUID of the owning ServiceOrderItem.
            data: Validated create payload.

        Returns:
            The newly created ORM instance.
        """
        orm = ServiceOrderItemRelationshipOrm(
            id=str(uuid.uuid4()),
            order_item_orm_id=order_item_orm_id,
            relationship_type=data.relationship_type,
            related_item_label=data.related_item_label,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, orm: ServiceOrderItemRelationshipOrm) -> None:
        """Delete a ServiceOrderItemRelationship.

        Args:
            orm: The ORM instance to delete.
        """
        await self._db.delete(orm)
        await self._db.flush()
