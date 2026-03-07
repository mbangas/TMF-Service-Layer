"""Data-access layer for TMF642 Alarm Management."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.assurance.models.orm import AlarmOrm
from src.assurance.models.schemas import AlarmCreate, AlarmPatch


class AlarmRepository:
    """Async repository providing CRUD operations for ``Alarm``.

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
    ) -> tuple[list[AlarmOrm], int]:
        """Return a paginated list of alarms and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional filter by alarm lifecycle state.
            service_id: Optional filter by service instance.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(AlarmOrm)
        count_query = select(func.count()).select_from(AlarmOrm)

        if state:
            base_query = base_query.where(AlarmOrm.state == state)
            count_query = count_query.where(AlarmOrm.state == state)

        if service_id:
            base_query = base_query.where(AlarmOrm.service_id == service_id)
            count_query = count_query.where(AlarmOrm.service_id == service_id)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query
            .offset(offset)
            .limit(limit)
            .order_by(AlarmOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, alarm_id: str) -> AlarmOrm | None:
        """Fetch a single alarm by its ID.

        Args:
            alarm_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(AlarmOrm).where(AlarmOrm.id == alarm_id)
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: AlarmCreate) -> AlarmOrm:
        """Persist a new Alarm.

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        alarm_id = str(uuid.uuid4())
        orm = AlarmOrm(
            id=alarm_id,
            href=f"/tmf-api/alarmManagement/v4/alarm/{alarm_id}",
            name=data.name,
            description=data.description,
            state="raised",
            alarm_type=data.alarm_type,
            severity=data.severity,
            probable_cause=data.probable_cause,
            specific_problem=data.specific_problem,
            service_id=data.service_id,
            raised_at=data.raised_at or datetime.now(tz=timezone.utc),
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(self, alarm_id: str, data: AlarmPatch) -> AlarmOrm | None:
        """Partial update of an Alarm.

        Args:
            alarm_id: Identifier of the alarm to patch.
            data: Partial patch schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(alarm_id)
        if orm is None:
            return None

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(orm, field, value)

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, alarm_id: str) -> bool:
        """Delete an Alarm by ID.

        Args:
            alarm_id: The UUID string identifier.

        Returns:
            ``True`` if the record was deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(alarm_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
