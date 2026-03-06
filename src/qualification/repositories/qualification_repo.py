"""Data-access layer for TMF645 ServiceQualification."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.qualification.models.orm import ServiceQualificationItemOrm, ServiceQualificationOrm
from src.qualification.models.schemas import (
    ServiceQualificationCreate,
    ServiceQualificationPatch,
)


class QualificationRepository:
    """Async repository providing CRUD operations for ``ServiceQualification``.

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
    ) -> tuple[list[ServiceQualificationOrm], int]:
        """Return a paginated list of qualifications and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional filter by qualification lifecycle state.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(ServiceQualificationOrm)
        count_query = select(func.count()).select_from(ServiceQualificationOrm)

        if state:
            base_query = base_query.where(ServiceQualificationOrm.state == state)
            count_query = count_query.where(ServiceQualificationOrm.state == state)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query
            .offset(offset)
            .limit(limit)
            .order_by(ServiceQualificationOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, qualification_id: str) -> ServiceQualificationOrm | None:
        """Fetch a single qualification by its ID.

        Args:
            qualification_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceQualificationOrm).where(
                ServiceQualificationOrm.id == qualification_id
            )
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: ServiceQualificationCreate) -> ServiceQualificationOrm:
        """Persist a new ServiceQualification with its nested items.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance (with items loaded).
        """
        qual_id = str(uuid.uuid4())

        orm = ServiceQualificationOrm(
            id=qual_id,
            href=(
                f"/tmf-api/serviceQualificationManagement/v4"
                f"/checkServiceQualification/{qual_id}"
            ),
            name=data.name,
            description=data.description,
            state="acknowledged",
            expected_qualification_date=data.expected_qualification_date,
            expiration_date=data.expiration_date,
            type=data.type,
            base_type=data.base_type,
            schema_location=data.schema_location,
        )

        # Attach nested items
        for item in data.items:
            orm.items.append(
                ServiceQualificationItemOrm(
                    id=str(uuid.uuid4()),
                    qualification_id=qual_id,
                    service_spec_id=item.service_spec_id,
                    state=item.state or "approved",
                    qualifier_message=item.qualifier_message,
                    termination_error=item.termination_error,
                )
            )

        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(
        self,
        qualification_id: str,
        data: ServiceQualificationPatch,
    ) -> ServiceQualificationOrm | None:
        """Partial update of a ServiceQualification (PATCH semantics).

        Only non-None fields in ``data`` overwrite existing values.

        Args:
            qualification_id: Identifier of the qualification to patch.
            data: Partial patch schema.

        Returns:
            Patched ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(qualification_id)
        if orm is None:
            return None

        patch_data = data.model_dump(exclude_none=True, by_alias=False)

        for field, value in patch_data.items():
            if hasattr(orm, field):
                setattr(orm, field, value)

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, qualification_id: str) -> bool:
        """Delete a ServiceQualification by ID.

        Cascade deletes all child ``ServiceQualificationItem`` records.

        Args:
            qualification_id: Identifier of the qualification to delete.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(qualification_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
