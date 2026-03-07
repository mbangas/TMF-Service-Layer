"""Data-access layer for TMF657 Service Level Management."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.assurance.models.orm import ServiceLevelObjectiveOrm
from src.assurance.models.schemas import ServiceLevelObjectiveCreate, ServiceLevelObjectivePatch


class SLORepository:
    """Async repository providing CRUD operations for ``ServiceLevelObjective``.

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
    ) -> tuple[list[ServiceLevelObjectiveOrm], int]:
        """Return a paginated list of SLOs and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional filter by SLO lifecycle state.
            service_id: Optional filter by service instance.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(ServiceLevelObjectiveOrm)
        count_query = select(func.count()).select_from(ServiceLevelObjectiveOrm)

        if state:
            base_query = base_query.where(ServiceLevelObjectiveOrm.state == state)
            count_query = count_query.where(ServiceLevelObjectiveOrm.state == state)

        if service_id:
            base_query = base_query.where(ServiceLevelObjectiveOrm.service_id == service_id)
            count_query = count_query.where(ServiceLevelObjectiveOrm.service_id == service_id)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query
            .offset(offset)
            .limit(limit)
            .order_by(ServiceLevelObjectiveOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, slo_id: str) -> ServiceLevelObjectiveOrm | None:
        """Fetch a single SLO by its ID.

        Args:
            slo_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceLevelObjectiveOrm).where(ServiceLevelObjectiveOrm.id == slo_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_service_and_metric(
        self, service_id: str, metric_name: str
    ) -> list[ServiceLevelObjectiveOrm]:
        """Fetch all active SLOs for a given service and metric combination.

        Used by ``check_violations`` to evaluate threshold breaches when a
        measurement completes.

        Args:
            service_id: The service instance UUID.
            metric_name: The metric identifier to match.

        Returns:
            List of active SLO ORM instances.
        """
        result = await self._db.execute(
            select(ServiceLevelObjectiveOrm).where(
                ServiceLevelObjectiveOrm.service_id == service_id,
                ServiceLevelObjectiveOrm.metric_name == metric_name,
                ServiceLevelObjectiveOrm.state == "active",
            )
        )
        return list(result.scalars().all())

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: ServiceLevelObjectiveCreate) -> ServiceLevelObjectiveOrm:
        """Persist a new ServiceLevelObjective.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        slo_id = str(uuid.uuid4())
        orm = ServiceLevelObjectiveOrm(
            id=slo_id,
            href=f"/tmf-api/serviceLevelManagement/v4/serviceLevel/{slo_id}",
            name=data.name,
            description=data.description,
            state="active",
            metric_name=data.metric_name,
            threshold_value=data.threshold_value,
            direction=data.direction,
            tolerance=data.tolerance,
            service_id=data.service_id,
            sls_id=data.sls_id,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(self, slo_id: str, data: ServiceLevelObjectivePatch) -> ServiceLevelObjectiveOrm | None:
        """Partial update of a ServiceLevelObjective.

        Args:
            slo_id: Identifier of the SLO to patch.
            data: Partial patch schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(slo_id)
        if orm is None:
            return None

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(orm, field, value)

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, slo_id: str) -> bool:
        """Delete a ServiceLevelObjective by ID.

        Args:
            slo_id: The UUID string identifier.

        Returns:
            ``True`` if the record was deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(slo_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
