"""Data-access layer for TMF653 ServiceTestSpecification."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.testing.models.orm import ServiceTestSpecificationOrm
from src.testing.models.schemas import (
    ServiceTestSpecificationCreate,
    ServiceTestSpecificationPatch,
)


class TestSpecificationRepository:
    """Async repository providing CRUD operations for ``ServiceTestSpecification``.

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
    ) -> tuple[list[ServiceTestSpecificationOrm], int]:
        """Return a paginated list of test specifications and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional filter by lifecycle state.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(ServiceTestSpecificationOrm)
        count_query = select(func.count()).select_from(ServiceTestSpecificationOrm)

        if state:
            base_query = base_query.where(ServiceTestSpecificationOrm.state == state)
            count_query = count_query.where(ServiceTestSpecificationOrm.state == state)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query
            .offset(offset)
            .limit(limit)
            .order_by(ServiceTestSpecificationOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, spec_id: str) -> ServiceTestSpecificationOrm | None:
        """Fetch a single test specification by its ID.

        Args:
            spec_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceTestSpecificationOrm).where(
                ServiceTestSpecificationOrm.id == spec_id
            )
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(
        self, data: ServiceTestSpecificationCreate
    ) -> ServiceTestSpecificationOrm:
        """Persist a new ServiceTestSpecification.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        spec_id = str(uuid.uuid4())
        orm = ServiceTestSpecificationOrm(
            id=spec_id,
            href=f"/tmf-api/serviceTest/v4/serviceTestSpecification/{spec_id}",
            name=data.name,
            description=data.description,
            state="active",
            test_type=data.test_type,
            version=data.version,
            valid_for_start=data.valid_for_start,
            valid_for_end=data.valid_for_end,
            service_spec_id=data.service_spec_id,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(
        self, spec_id: str, data: ServiceTestSpecificationPatch
    ) -> ServiceTestSpecificationOrm | None:
        """Partial update of a ServiceTestSpecification.

        Args:
            spec_id: Identifier of the specification to patch.
            data: Partial patch schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(spec_id)
        if orm is None:
            return None

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(orm, field, value)

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, spec_id: str) -> bool:
        """Delete a ServiceTestSpecification by ID.

        Args:
            spec_id: The UUID string identifier.

        Returns:
            ``True`` if the record was deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(spec_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
