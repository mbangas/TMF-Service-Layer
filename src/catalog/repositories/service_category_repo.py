"""Data-access layer for TMF633 ServiceCategory."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.catalog.models.orm import ServiceCategoryOrm
from src.catalog.models.schemas import (
    ServiceCategoryCreate,
    ServiceCategoryPatch,
    ServiceCategoryUpdate,
)


def _category_query_options():
    """Return SQLAlchemy load options for ServiceCategoryOrm.

    Eagerly loads sub_categories and service_candidates one level deep
    using selectinload (explicit, avoids recursive async cascade).
    """
    return [
        selectinload(ServiceCategoryOrm.sub_categories),
        selectinload(ServiceCategoryOrm.service_candidates),
    ]


class ServiceCategoryRepository:
    """Async repository providing CRUD operations for ``ServiceCategory``.

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
        is_root: bool | None = None,
    ) -> tuple[list[ServiceCategoryOrm], int]:
        """Return a paginated list of categories and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            lifecycle_status: Optional filter by lifecycle status.
            is_root: When True, restrict to root categories only.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(ServiceCategoryOrm)
        count_query = select(func.count()).select_from(ServiceCategoryOrm)

        if lifecycle_status:
            base_query = base_query.where(
                ServiceCategoryOrm.lifecycle_status == lifecycle_status
            )
            count_query = count_query.where(
                ServiceCategoryOrm.lifecycle_status == lifecycle_status
            )
        if is_root is not None:
            base_query = base_query.where(ServiceCategoryOrm.is_root == is_root)
            count_query = count_query.where(ServiceCategoryOrm.is_root == is_root)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query
            .options(*_category_query_options())
            .offset(offset)
            .limit(limit)
            .order_by(ServiceCategoryOrm.created_at.desc())
        )
        items = list(result.scalars().unique().all())
        return items, total

    async def get_by_id(self, category_id: str) -> ServiceCategoryOrm | None:
        """Fetch a single category by its ID.

        Args:
            category_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceCategoryOrm)
            .where(ServiceCategoryOrm.id == category_id)
            .options(*_category_query_options())
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: ServiceCategoryCreate) -> ServiceCategoryOrm:
        """Persist a new ServiceCategory.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        category_id = str(uuid.uuid4())
        now_utc = datetime.now(tz=timezone.utc).isoformat()

        orm = ServiceCategoryOrm(
            id=category_id,
            href=f"/tmf-api/serviceCatalogManagement/v4/serviceCategory/{category_id}",
            name=data.name,
            description=data.description,
            version=data.version,
            lifecycle_status=data.lifecycle_status,
            is_root=data.is_root,
            parent_id=data.parent_id,
            last_update=now_utc,
            type=data.type,
            base_type=data.base_type,
            schema_location=data.schema_location,
        )

        self._db.add(orm)
        await self._db.flush()
        # Re-fetch with selectinload so relationships are populated in response
        return await self.get_by_id(category_id)  # type: ignore[return-value]

    async def update(
        self, category_id: str, data: ServiceCategoryUpdate
    ) -> ServiceCategoryOrm | None:
        """Full replacement of a ServiceCategory (PUT semantics).

        Args:
            category_id: Identifier of the category to replace.
            data: Fully populated update schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(category_id)
        if orm is None:
            return None

        orm.name = data.name
        orm.description = data.description
        orm.version = data.version
        orm.lifecycle_status = data.lifecycle_status
        orm.is_root = data.is_root
        orm.parent_id = data.parent_id
        orm.last_update = datetime.now(tz=timezone.utc).isoformat()
        orm.type = data.type
        orm.base_type = data.base_type
        orm.schema_location = data.schema_location

        await self._db.flush()
        return await self.get_by_id(category_id)

    async def patch(
        self, category_id: str, data: ServiceCategoryPatch
    ) -> ServiceCategoryOrm | None:
        """Partial update of a ServiceCategory (PATCH semantics).

        Only fields present (non-None) in ``data`` are applied.

        Args:
            category_id: Identifier of the category to patch.
            data: Partial update schema with only the fields to change.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(category_id)
        if orm is None:
            return None

        patch_data = data.model_dump(exclude_none=True, by_alias=False)
        for field, value in patch_data.items():
            setattr(orm, field, value)
        orm.last_update = datetime.now(tz=timezone.utc).isoformat()

        await self._db.flush()
        return await self.get_by_id(category_id)

    async def delete(self, category_id: str) -> bool:
        """Delete a ServiceCategory by ID.

        Args:
            category_id: Identifier of the category to delete.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(category_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
