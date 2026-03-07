"""Data-access layer for TMF628 Performance Management."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.assurance.models.orm import PerformanceMeasurementOrm
from src.assurance.models.schemas import PerformanceMeasurementCreate, PerformanceMeasurementPatch


class MeasurementRepository:
    """Async repository providing CRUD operations for ``PerformanceMeasurement``.

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
        service_id: str | None = None,
    ) -> tuple[list[PerformanceMeasurementOrm], int]:
        """Return a paginated list of measurements and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional filter by measurement lifecycle state.
            service_id: Optional filter by service instance.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(PerformanceMeasurementOrm)
        count_query = select(func.count()).select_from(PerformanceMeasurementOrm)

        if state:
            base_query = base_query.where(PerformanceMeasurementOrm.state == state)
            count_query = count_query.where(PerformanceMeasurementOrm.state == state)

        if service_id:
            base_query = base_query.where(PerformanceMeasurementOrm.service_id == service_id)
            count_query = count_query.where(PerformanceMeasurementOrm.service_id == service_id)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query
            .offset(offset)
            .limit(limit)
            .order_by(PerformanceMeasurementOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, measurement_id: str) -> PerformanceMeasurementOrm | None:
        """Fetch a single measurement by its ID.

        Args:
            measurement_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(PerformanceMeasurementOrm).where(PerformanceMeasurementOrm.id == measurement_id)
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: PerformanceMeasurementCreate) -> PerformanceMeasurementOrm:
        """Persist a new PerformanceMeasurement.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        measurement_id = str(uuid.uuid4())
        orm = PerformanceMeasurementOrm(
            id=measurement_id,
            href=f"/tmf-api/performanceManagement/v4/performanceMeasurement/{measurement_id}",
            name=data.name,
            description=data.description,
            state="scheduled",
            metric_name=data.metric_name,
            metric_value=data.metric_value,
            unit_of_measure=data.unit_of_measure,
            granularity=data.granularity,
            service_id=data.service_id,
            scheduled_at=data.scheduled_at or datetime.now(tz=timezone.utc),
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(
        self, measurement_id: str, data: PerformanceMeasurementPatch
    ) -> PerformanceMeasurementOrm | None:
        """Partial update of a PerformanceMeasurement.

        Args:
            measurement_id: Identifier of the measurement to patch.
            data: Partial patch schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(measurement_id)
        if orm is None:
            return None

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(orm, field, value)

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, measurement_id: str) -> bool:
        """Delete a PerformanceMeasurement by ID.

        Args:
            measurement_id: The UUID string identifier.

        Returns:
            ``True`` if the record was deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(measurement_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
