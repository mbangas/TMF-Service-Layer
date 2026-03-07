"""Data-access layer for TMF633 ServiceCandidate."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models.orm import ServiceCandidateOrm, ServiceCategoryOrm
from src.catalog.models.schemas import (
    ServiceCandidateCreate,
    ServiceCandidatePatch,
    ServiceCandidateUpdate,
)


class ServiceCandidateRepository:
    """Async repository providing CRUD operations for ``ServiceCandidate``.

    All methods accept an ``AsyncSession`` injected by the FastAPI dependency.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 20,
        lifecycle_status: str | None = None,
    ) -> tuple[list[ServiceCandidateOrm], int]:
        """Return a paginated list of candidates and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            lifecycle_status: Optional filter by lifecycle status.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(ServiceCandidateOrm)
        count_query = select(func.count()).select_from(ServiceCandidateOrm)

        if lifecycle_status:
            base_query = base_query.where(
                ServiceCandidateOrm.lifecycle_status == lifecycle_status
            )
            count_query = count_query.where(
                ServiceCandidateOrm.lifecycle_status == lifecycle_status
            )

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query
            .offset(offset)
            .limit(limit)
            .order_by(ServiceCandidateOrm.created_at.desc())
        )
        items = list(result.scalars().unique().all())
        return items, total

    async def get_by_id(self, candidate_id: str) -> ServiceCandidateOrm | None:
        """Fetch a single candidate by its ID.

        Args:
            candidate_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceCandidateOrm).where(ServiceCandidateOrm.id == candidate_id)
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def _resolve_categories(
        self, category_ids: list[str]
    ) -> list[ServiceCategoryOrm]:
        """Resolve category IDs to ORM instances.

        Args:
            category_ids: List of ServiceCategory UUIDs to resolve.

        Returns:
            List of ``ServiceCategoryOrm`` instances (missing IDs are silently skipped).
        """
        if not category_ids:
            return []
        result = await self._db.execute(
            select(ServiceCategoryOrm).where(ServiceCategoryOrm.id.in_(category_ids))
        )
        return list(result.scalars().all())

    async def create(self, data: ServiceCandidateCreate) -> ServiceCandidateOrm:
        """Persist a new ServiceCandidate.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        candidate_id = str(uuid.uuid4())
        now_utc = datetime.now(tz=timezone.utc).isoformat()

        orm = ServiceCandidateOrm(
            id=candidate_id,
            href=f"/tmf-api/serviceCatalogManagement/v4/serviceCandidate/{candidate_id}",
            name=data.name,
            description=data.description,
            version=data.version,
            lifecycle_status=data.lifecycle_status,
            service_spec_id=data.service_spec_id,
            last_update=now_utc,
            type=data.type,
            base_type=data.base_type,
            schema_location=data.schema_location,
        )
        orm.categories = await self._resolve_categories(data.category_ids)

        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def update(
        self, candidate_id: str, data: ServiceCandidateUpdate
    ) -> ServiceCandidateOrm | None:
        """Full replacement of a ServiceCandidate (PUT semantics).

        Args:
            candidate_id: Identifier of the candidate to replace.
            data: Fully populated update schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(candidate_id)
        if orm is None:
            return None

        orm.name = data.name
        orm.description = data.description
        orm.version = data.version
        orm.lifecycle_status = data.lifecycle_status
        orm.service_spec_id = data.service_spec_id
        orm.last_update = datetime.now(tz=timezone.utc).isoformat()
        orm.type = data.type
        orm.base_type = data.base_type
        orm.schema_location = data.schema_location
        orm.categories = await self._resolve_categories(data.category_ids)

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(
        self, candidate_id: str, data: ServiceCandidatePatch
    ) -> ServiceCandidateOrm | None:
        """Partial update of a ServiceCandidate (PATCH semantics).

        Args:
            candidate_id: Identifier of the candidate to patch.
            data: Partial update schema with only the fields to change.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(candidate_id)
        if orm is None:
            return None

        patch_data = data.model_dump(exclude_none=True, by_alias=False)
        category_ids = patch_data.pop("category_ids", None)

        for field, value in patch_data.items():
            setattr(orm, field, value)

        if category_ids is not None:
            orm.categories = await self._resolve_categories(category_ids)

        orm.last_update = datetime.now(tz=timezone.utc).isoformat()
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, candidate_id: str) -> bool:
        """Delete a ServiceCandidate by ID.

        Args:
            candidate_id: Identifier of the candidate to delete.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(candidate_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
