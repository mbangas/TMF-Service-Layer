"""Data-access layer for TMF640 ServiceActivationJob."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.provisioning.models.orm import ServiceActivationJobOrm, ServiceConfigurationParamOrm
from src.provisioning.models.schemas import ServiceActivationJobCreate, ServiceActivationJobPatch


class ActivationJobRepository:
    """Async repository providing CRUD operations for ``ServiceActivationJob``.

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
        job_type: str | None = None,
        service_id: str | None = None,
    ) -> tuple[list[ServiceActivationJobOrm], int]:
        """Return a paginated list of activation jobs and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional filter by job lifecycle state.
            job_type: Optional filter by job type.
            service_id: Optional filter by target service ID.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(ServiceActivationJobOrm)
        count_query = select(func.count()).select_from(ServiceActivationJobOrm)

        if state:
            base_query = base_query.where(ServiceActivationJobOrm.state == state)
            count_query = count_query.where(ServiceActivationJobOrm.state == state)
        if job_type:
            base_query = base_query.where(ServiceActivationJobOrm.job_type == job_type)
            count_query = count_query.where(ServiceActivationJobOrm.job_type == job_type)
        if service_id:
            base_query = base_query.where(ServiceActivationJobOrm.service_id == service_id)
            count_query = count_query.where(ServiceActivationJobOrm.service_id == service_id)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query
            .offset(offset)
            .limit(limit)
            .order_by(ServiceActivationJobOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, job_id: str) -> ServiceActivationJobOrm | None:
        """Fetch a single activation job by its ID.

        Args:
            job_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceActivationJobOrm).where(ServiceActivationJobOrm.id == job_id)
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: ServiceActivationJobCreate) -> ServiceActivationJobOrm:
        """Persist a new ServiceActivationJob.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        job_id = str(uuid.uuid4())

        orm = ServiceActivationJobOrm(
            id=job_id,
            href=f"/tmf-api/serviceActivationConfiguration/v4/serviceActivationJob/{job_id}",
            name=data.name,
            description=data.description,
            job_type=data.job_type,
            state="accepted",
            mode=data.mode,
            start_mode=data.start_mode,
            scheduled_start_date=data.scheduled_start_date,
            scheduled_completion_date=data.scheduled_completion_date,
            service_id=data.service_id,
            type=data.type,
            base_type=data.base_type,
            schema_location=data.schema_location,
        )

        # Attach nested configuration params
        for param in data.params:
            orm.params.append(
                ServiceConfigurationParamOrm(
                    id=str(uuid.uuid4()),
                    job_id=job_id,
                    name=param.name,
                    value=param.value,
                    value_type=param.value_type,
                )
            )

        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(
        self,
        job_id: str,
        data: ServiceActivationJobPatch,
        extra_fields: dict[str, object] | None = None,
    ) -> ServiceActivationJobOrm | None:
        """Partial update of a ServiceActivationJob (PATCH semantics).

        Only non-None fields in ``data`` overwrite existing values.
        Server-side fields (e.g. timestamps) can be supplied via ``extra_fields``.

        Args:
            job_id: Identifier of the job to patch.
            data: Partial patch schema.
            extra_fields: Optional dict of extra column name → value pairs.

        Returns:
            Patched ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(job_id)
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

    async def delete(self, job_id: str) -> bool:
        """Delete a ServiceActivationJob by ID.

        Args:
            job_id: Identifier of the job to delete.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(job_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
