"""Data-access layer for TMF648 Quote Management."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.commercial.models.orm import QuoteItemOrm, QuoteOrm
from src.commercial.models.schemas import QuoteCreate, QuoteItemCreate, QuotePatch


class QuoteRepository:
    """Async repository providing CRUD operations for ``Quote`` and its items.

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
        category: str | None = None,
        related_service_spec_id: str | None = None,
    ) -> tuple[list[QuoteOrm], int]:
        """Return a paginated list of quotes and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional lifecycle state filter.
            category: Optional category filter.
            related_service_spec_id: Optional service spec filter.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(QuoteOrm)
        count_query = select(func.count()).select_from(QuoteOrm)

        if state:
            base_query = base_query.where(QuoteOrm.state == state)
            count_query = count_query.where(QuoteOrm.state == state)
        if category:
            base_query = base_query.where(QuoteOrm.category == category)
            count_query = count_query.where(QuoteOrm.category == category)
        if related_service_spec_id:
            base_query = base_query.where(QuoteOrm.related_service_spec_id == related_service_spec_id)
            count_query = count_query.where(QuoteOrm.related_service_spec_id == related_service_spec_id)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query.offset(offset).limit(limit).order_by(QuoteOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, quote_id: str) -> QuoteOrm | None:
        """Fetch a single quote by its ID.

        Args:
            quote_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(QuoteOrm).where(QuoteOrm.id == quote_id)
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: QuoteCreate) -> QuoteOrm:
        """Persist a new Quote (and any initial items).

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        quote_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc)
        orm = QuoteOrm(
            id=quote_id,
            href=f"/tmf-api/quoteManagement/v4/quote/{quote_id}",
            name=data.name,
            description=data.description,
            category=data.category,
            state="inProgress",
            quote_date=now,
            requested_completion_date=data.requested_completion_date,
            expected_fulfillment_start_date=data.expected_fulfillment_start_date,
            related_service_spec_id=data.related_service_spec_id,
        )
        for item_data in data.items:
            orm.items.append(
                QuoteItemOrm(
                    id=str(uuid.uuid4()),
                    action=item_data.action,
                    state="inProgress",
                    quantity=item_data.quantity,
                    item_price=item_data.item_price,
                    price_type=item_data.price_type,
                    description=item_data.description,
                    quote_id=quote_id,
                    related_service_spec_id=item_data.related_service_spec_id,
                )
            )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(self, quote_id: str, data: QuotePatch) -> QuoteOrm | None:
        """Partial update of a Quote.

        Args:
            quote_id: Identifier of the quote to patch.
            data: Partial patch schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(quote_id)
        if orm is None:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(orm, field, value)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, quote_id: str) -> bool:
        """Delete a Quote and its cascade-linked items.

        Args:
            quote_id: The UUID string identifier.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(quote_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True

    # ── Items ─────────────────────────────────────────────────────────────────

    async def add_item(self, quote_id: str, data: QuoteItemCreate) -> QuoteItemOrm:
        """Append a new item to a Quote.

        Args:
            quote_id: The parent quote UUID.
            data: Item create schema.

        Returns:
            The newly created item ORM instance.
        """
        item = QuoteItemOrm(
            id=str(uuid.uuid4()),
            action=data.action,
            state="inProgress",
            quantity=data.quantity,
            item_price=data.item_price,
            price_type=data.price_type,
            description=data.description,
            quote_id=quote_id,
            related_service_spec_id=data.related_service_spec_id,
        )
        self._db.add(item)
        await self._db.flush()
        await self._db.refresh(item)
        return item

    async def get_item_by_id(self, item_id: str) -> QuoteItemOrm | None:
        """Fetch a single quote item by its ID.

        Args:
            item_id: The item UUID string.

        Returns:
            The ORM instance or ``None``.
        """
        result = await self._db.execute(
            select(QuoteItemOrm).where(QuoteItemOrm.id == item_id)
        )
        return result.scalar_one_or_none()

    async def delete_item(self, item_id: str) -> bool:
        """Delete a single quote item by its ID.

        Args:
            item_id: The item UUID string.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        item = await self.get_item_by_id(item_id)
        if item is None:
            return False
        await self._db.delete(item)
        await self._db.flush()
        return True
