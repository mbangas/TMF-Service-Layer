"""Data-access layer for TMF653 ServiceTest and TestMeasure."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.testing.models.orm import ServiceTestOrm, TestMeasureOrm
from src.testing.models.schemas import (
    ServiceTestCreate,
    ServiceTestPatch,
    TestMeasureCreate,
)


class ServiceTestRepository:
    """Async repository providing CRUD operations for ``ServiceTest`` and ``TestMeasure``.

    All methods accept an ``AsyncSession`` injected by the FastAPI dependency.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── ServiceTest — Read ────────────────────────────────────────────────────

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 20,
        state: str | None = None,
        service_id: str | None = None,
        test_spec_id: str | None = None,
    ) -> tuple[list[ServiceTestOrm], int]:
        """Return a paginated list of service tests and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional filter by lifecycle state.
            service_id: Optional filter by service instance.
            test_spec_id: Optional filter by test specification.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(ServiceTestOrm)
        count_query = select(func.count()).select_from(ServiceTestOrm)

        if state:
            base_query = base_query.where(ServiceTestOrm.state == state)
            count_query = count_query.where(ServiceTestOrm.state == state)
        if service_id:
            base_query = base_query.where(ServiceTestOrm.service_id == service_id)
            count_query = count_query.where(ServiceTestOrm.service_id == service_id)
        if test_spec_id:
            base_query = base_query.where(ServiceTestOrm.test_spec_id == test_spec_id)
            count_query = count_query.where(ServiceTestOrm.test_spec_id == test_spec_id)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query
            .offset(offset)
            .limit(limit)
            .order_by(ServiceTestOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, test_id: str) -> ServiceTestOrm | None:
        """Fetch a single service test by its ID.

        Args:
            test_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceTestOrm).where(ServiceTestOrm.id == test_id)
        )
        return result.scalar_one_or_none()

    # ── ServiceTest — Write ───────────────────────────────────────────────────

    async def create(self, data: ServiceTestCreate) -> ServiceTestOrm:
        """Persist a new ServiceTest in ``planned`` state.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        test_id = str(uuid.uuid4())
        orm = ServiceTestOrm(
            id=test_id,
            href=f"/tmf-api/serviceTest/v4/serviceTest/{test_id}",
            name=data.name,
            description=data.description,
            state="planned",
            mode=data.mode,
            service_id=data.service_id,
            test_spec_id=data.test_spec_id,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(
        self, test_id: str, data: ServiceTestPatch
    ) -> ServiceTestOrm | None:
        """Partial update of a ServiceTest.

        Args:
            test_id: Identifier of the test to patch.
            data: Partial patch schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(test_id)
        if orm is None:
            return None

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(orm, field, value)

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, test_id: str) -> bool:
        """Delete a ServiceTest (and its TestMeasures via CASCADE) by ID.

        Args:
            test_id: The UUID string identifier.

        Returns:
            ``True`` if the record was deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(test_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True

    # ── TestMeasure ───────────────────────────────────────────────────────────

    async def add_measure(
        self, service_test_id: str, data: TestMeasureCreate
    ) -> TestMeasureOrm:
        """Persist a new TestMeasure under the given ServiceTest.

        Args:
            service_test_id: Parent service test UUID.
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        measure_id = str(uuid.uuid4())
        orm = TestMeasureOrm(
            id=measure_id,
            service_test_id=service_test_id,
            metric_name=data.metric_name,
            metric_value=data.metric_value,
            unit_of_measure=data.unit_of_measure,
            result=data.result,
            captured_at=data.captured_at or datetime.now(tz=timezone.utc),
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def get_measures(self, service_test_id: str) -> list[TestMeasureOrm]:
        """Return all TestMeasure records for a given service test.

        Args:
            service_test_id: Parent service test UUID.

        Returns:
            List of TestMeasure ORM instances ordered by capture time ascending.
        """
        result = await self._db.execute(
            select(TestMeasureOrm)
            .where(TestMeasureOrm.service_test_id == service_test_id)
            .order_by(TestMeasureOrm.captured_at.asc())
        )
        return list(result.scalars().all())
