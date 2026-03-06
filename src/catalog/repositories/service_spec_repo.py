"""Data-access layer for TMF633 ServiceSpecification."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models.orm import (
    ServiceLevelSpecificationOrm,
    ServiceSpecCharacteristicOrm,
    ServiceSpecificationOrm,
)
from src.catalog.models.schemas import (
    ServiceSpecificationCreate,
    ServiceSpecificationPatch,
    ServiceSpecificationUpdate,
)


class ServiceSpecificationRepository:
    """Async repository providing CRUD operations for ``ServiceSpecification``.

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
    ) -> tuple[list[ServiceSpecificationOrm], int]:
        """Return a paginated list of specifications and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            lifecycle_status: Optional filter by lifecycle status.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(ServiceSpecificationOrm)
        count_query = select(func.count()).select_from(ServiceSpecificationOrm)

        if lifecycle_status:
            base_query = base_query.where(
                ServiceSpecificationOrm.lifecycle_status == lifecycle_status
            )
            count_query = count_query.where(
                ServiceSpecificationOrm.lifecycle_status == lifecycle_status
            )

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query.offset(offset).limit(limit).order_by(ServiceSpecificationOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, spec_id: str) -> ServiceSpecificationOrm | None:
        """Fetch a single specification by its ID.

        Args:
            spec_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceSpecificationOrm).where(ServiceSpecificationOrm.id == spec_id)
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: ServiceSpecificationCreate) -> ServiceSpecificationOrm:
        """Persist a new ServiceSpecification.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        spec_id = str(uuid.uuid4())
        now_utc = datetime.now(tz=timezone.utc).isoformat()

        orm = ServiceSpecificationOrm(
            id=spec_id,
            href=f"/tmf-api/serviceCatalogManagement/v4/serviceSpecification/{spec_id}",
            name=data.name,
            description=data.description,
            version=data.version,
            is_bundle=data.is_bundle,
            lifecycle_status=data.lifecycle_status,
            last_update=now_utc,
            type=data.type,
            base_type=data.base_type,
            schema_location=data.schema_location,
        )

        # Attach nested characteristics
        for char in data.service_spec_characteristic:
            orm.service_spec_characteristic.append(
                ServiceSpecCharacteristicOrm(
                    id=str(uuid.uuid4()),
                    service_spec_id=spec_id,
                    **char.model_dump(),
                )
            )

        # Attach nested SLS
        for sls in data.service_level_specification:
            orm.service_level_specification.append(
                ServiceLevelSpecificationOrm(
                    id=str(uuid.uuid4()),
                    service_spec_id=spec_id,
                    **sls.model_dump(),
                )
            )

        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def update(self, spec_id: str, data: ServiceSpecificationUpdate) -> ServiceSpecificationOrm | None:
        """Full replacement of a ServiceSpecification (PUT semantics).

        Args:
            spec_id: Identifier of the specification to replace.
            data: Fully populated update schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(spec_id)
        if orm is None:
            return None

        orm.name = data.name
        orm.description = data.description
        orm.version = data.version
        orm.is_bundle = data.is_bundle
        orm.lifecycle_status = data.lifecycle_status
        orm.last_update = datetime.now(tz=timezone.utc).isoformat()
        orm.type = data.type
        orm.base_type = data.base_type
        orm.schema_location = data.schema_location

        # Replace nested collections
        orm.service_spec_characteristic.clear()
        for char in data.service_spec_characteristic:
            orm.service_spec_characteristic.append(
                ServiceSpecCharacteristicOrm(
                    id=str(uuid.uuid4()),
                    service_spec_id=spec_id,
                    **char.model_dump(),
                )
            )

        orm.service_level_specification.clear()
        for sls in data.service_level_specification:
            orm.service_level_specification.append(
                ServiceLevelSpecificationOrm(
                    id=str(uuid.uuid4()),
                    service_spec_id=spec_id,
                    **sls.model_dump(),
                )
            )

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(self, spec_id: str, data: ServiceSpecificationPatch) -> ServiceSpecificationOrm | None:
        """Partial update of a ServiceSpecification (PATCH semantics).

        Only non-None fields in ``data`` overwrite existing values.

        Args:
            spec_id: Identifier of the specification to patch.
            data: Partial patch schema.

        Returns:
            Patched ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(spec_id)
        if orm is None:
            return None

        patch_data = data.model_dump(exclude_none=True, by_alias=False)

        field_map = {
            "type": "type",
            "base_type": "base_type",
            "schema_location": "schema_location",
        }

        for field, value in patch_data.items():
            mapped = field_map.get(field, field)
            if hasattr(orm, mapped):
                setattr(orm, mapped, value)

        orm.last_update = datetime.now(tz=timezone.utc).isoformat()
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, spec_id: str) -> bool:
        """Delete a ServiceSpecification by ID.

        Args:
            spec_id: Identifier of the specification to delete.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(spec_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
