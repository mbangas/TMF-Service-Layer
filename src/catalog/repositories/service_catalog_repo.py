"""Data-access layer for TMF633 ServiceCatalog."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models.orm import ServiceCatalogOrm, ServiceCategoryOrm
from src.catalog.models.schemas import (
    ServiceCatalogCreate,
    ServiceCatalogPatch,
    ServiceCatalogUpdate,
)


class ServiceCatalogRepository:
    """Async repository providing CRUD operations for ``ServiceCatalog``.

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
    ) -> tuple[list[ServiceCatalogOrm], int]:
        """Return a paginated list of catalogs and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            lifecycle_status: Optional filter by lifecycle status.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(ServiceCatalogOrm)
        count_query = select(func.count()).select_from(ServiceCatalogOrm)

        if lifecycle_status:
            base_query = base_query.where(
                ServiceCatalogOrm.lifecycle_status == lifecycle_status
            )
            count_query = count_query.where(
                ServiceCatalogOrm.lifecycle_status == lifecycle_status
            )

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query
            .offset(offset)
            .limit(limit)
            .order_by(ServiceCatalogOrm.created_at.desc())
        )
        items = list(result.scalars().unique().all())
        return items, total

    async def get_by_id(self, catalog_id: str) -> ServiceCatalogOrm | None:
        """Fetch a single catalog by its ID.

        Args:
            catalog_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceCatalogOrm).where(ServiceCatalogOrm.id == catalog_id)
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def _resolve_categories(
        self, category_ids: list[str]
    ) -> list[ServiceCategoryOrm]:
        """Resolve category IDs to ORM instances.

        Args:
            category_ids: List of ServiceCategory UUIDs.

        Returns:
            List of ``ServiceCategoryOrm`` instances (missing IDs are silently skipped).
        """
        if not category_ids:
            return []
        result = await self._db.execute(
            select(ServiceCategoryOrm).where(ServiceCategoryOrm.id.in_(category_ids))
        )
        return list(result.scalars().all())

    async def create(self, data: ServiceCatalogCreate) -> ServiceCatalogOrm:
        """Persist a new ServiceCatalog.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        catalog_id = str(uuid.uuid4())
        now_utc = datetime.now(tz=timezone.utc).isoformat()

        orm = ServiceCatalogOrm(
            id=catalog_id,
            href=f"/tmf-api/serviceCatalogManagement/v4/serviceCatalog/{catalog_id}",
            name=data.name,
            description=data.description,
            version=data.version,
            lifecycle_status=data.lifecycle_status,
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
        self, catalog_id: str, data: ServiceCatalogUpdate
    ) -> ServiceCatalogOrm | None:
        """Full replacement of a ServiceCatalog (PUT semantics).

        Args:
            catalog_id: Identifier of the catalog to replace.
            data: Fully populated update schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(catalog_id)
        if orm is None:
            return None

        orm.name = data.name
        orm.description = data.description
        orm.version = data.version
        orm.lifecycle_status = data.lifecycle_status
        orm.last_update = datetime.now(tz=timezone.utc).isoformat()
        orm.type = data.type
        orm.base_type = data.base_type
        orm.schema_location = data.schema_location
        orm.categories = await self._resolve_categories(data.category_ids)

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(
        self, catalog_id: str, data: ServiceCatalogPatch
    ) -> ServiceCatalogOrm | None:
        """Partial update of a ServiceCatalog (PATCH semantics).

        Args:
            catalog_id: Identifier of the catalog to patch.
            data: Partial update schema with only the fields to change.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(catalog_id)
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

    async def delete(self, catalog_id: str) -> bool:
        """Delete a ServiceCatalog by ID.

        Args:
            catalog_id: Identifier of the catalog to delete.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(catalog_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
