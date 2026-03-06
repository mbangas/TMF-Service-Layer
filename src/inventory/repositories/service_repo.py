"""Data-access layer for TMF638 Service (inventory instances)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.inventory.models.orm import ServiceCharacteristicOrm, ServiceOrm
from src.inventory.models.schemas import ServiceCreate, ServicePatch


class ServiceRepository:
    """Async repository providing CRUD operations for ``Service``.

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
    ) -> tuple[list[ServiceOrm], int]:
        """Return a paginated list of service instances and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional filter by lifecycle state.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(ServiceOrm)
        count_query = select(func.count()).select_from(ServiceOrm)

        if state:
            base_query = base_query.where(ServiceOrm.state == state)
            count_query = count_query.where(ServiceOrm.state == state)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query.offset(offset).limit(limit).order_by(ServiceOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, service_id: str) -> ServiceOrm | None:
        """Fetch a single service instance by its ID.

        Args:
            service_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceOrm).where(ServiceOrm.id == service_id)
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: ServiceCreate) -> ServiceOrm:
        """Persist a new Service instance.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        service_id = str(uuid.uuid4())

        orm = ServiceOrm(
            id=service_id,
            href=f"/tmf-api/serviceInventory/v4/service/{service_id}",
            name=data.name,
            description=data.description,
            service_type=data.service_type,
            state=data.state,
            start_date=data.start_date,
            end_date=data.end_date,
            service_spec_id=data.service_spec_id,
            service_order_id=data.service_order_id,
            type=data.type,
            base_type=data.base_type,
            schema_location=data.schema_location,
        )

        # Attach nested characteristics
        for char in data.service_characteristic:
            orm.service_characteristic.append(
                ServiceCharacteristicOrm(
                    id=str(uuid.uuid4()),
                    service_id=service_id,
                    name=char.name,
                    value=char.value,
                    value_type=char.value_type,
                )
            )

        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(
        self,
        service_id: str,
        data: ServicePatch,
        extra_fields: dict[str, object] | None = None,
    ) -> ServiceOrm | None:
        """Partial update of a Service instance (PATCH semantics).

        Only non-None fields in ``data`` overwrite existing values.
        Server-side fields (e.g. ``start_date`` set automatically) can be
        supplied via ``extra_fields``.

        Args:
            service_id: Identifier of the service to patch.
            data: Partial patch schema.
            extra_fields: Optional dict of extra column name → value pairs.

        Returns:
            Patched ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(service_id)
        if orm is None:
            return None

        patch_data = data.model_dump(exclude_none=True, by_alias=False)

        for field, value in patch_data.items():
            if hasattr(orm, field):
                setattr(orm, field, value)

        if extra_fields:
            for field, value in extra_fields.items():
                if hasattr(orm, field):
                    setattr(orm, field, value)

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, service_id: str) -> bool:
        """Delete a Service instance by ID.

        Args:
            service_id: Identifier of the service to delete.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(service_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
