"""Data-access layer for TMF656 Service Problem Management."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.problem.models.orm import ServiceProblemOrm
from src.problem.models.schemas import ServiceProblemCreate, ServiceProblemPatch


class ServiceProblemRepository:
    """Async repository providing CRUD operations for ``ServiceProblem``.

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
        impact: str | None = None,
        related_service_id: str | None = None,
    ) -> tuple[list[ServiceProblemOrm], int]:
        """Return a paginated list of service problems and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional lifecycle state filter.
            impact: Optional impact level filter.
            related_service_id: Optional service instance filter.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(ServiceProblemOrm)
        count_query = select(func.count()).select_from(ServiceProblemOrm)

        if state:
            base_query = base_query.where(ServiceProblemOrm.state == state)
            count_query = count_query.where(ServiceProblemOrm.state == state)
        if impact:
            base_query = base_query.where(ServiceProblemOrm.impact == impact)
            count_query = count_query.where(ServiceProblemOrm.impact == impact)
        if related_service_id:
            base_query = base_query.where(ServiceProblemOrm.related_service_id == related_service_id)
            count_query = count_query.where(ServiceProblemOrm.related_service_id == related_service_id)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query.offset(offset).limit(limit).order_by(ServiceProblemOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, problem_id: str) -> ServiceProblemOrm | None:
        """Fetch a single service problem by its ID.

        Args:
            problem_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceProblemOrm).where(ServiceProblemOrm.id == problem_id)
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: ServiceProblemCreate) -> ServiceProblemOrm:
        """Persist a new ServiceProblem.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        problem_id = str(uuid.uuid4())
        orm = ServiceProblemOrm(
            id=problem_id,
            href=f"/tmf-api/serviceProblemManagement/v4/problem/{problem_id}",
            name=data.name,
            description=data.description,
            state="submitted",
            category=data.category,
            impact=data.impact,
            priority=data.priority,
            root_cause=data.root_cause,
            expected_resolution_date=data.expected_resolution_date,
            related_service_id=data.related_service_id,
            related_ticket_id=data.related_ticket_id,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(self, problem_id: str, data: ServiceProblemPatch) -> ServiceProblemOrm | None:
        """Partial update of a ServiceProblem.

        Args:
            problem_id: Identifier of the problem to patch.
            data: Partial patch schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(problem_id)
        if orm is None:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(orm, field, value)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, problem_id: str) -> bool:
        """Delete a ServiceProblem by ID.

        Args:
            problem_id: The UUID string identifier.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(problem_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
