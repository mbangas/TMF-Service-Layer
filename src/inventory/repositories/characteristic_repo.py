"""Data-access layer for TMF638 ServiceCharacteristic and CharacteristicValue."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.inventory.models.orm import CharacteristicValueOrm, ServiceCharacteristicOrm
from src.inventory.models.schemas import (
    CharacteristicValueCreate,
    ServiceCharacteristicCreate,
    ServiceCharacteristicPatch,
)


class ServiceCharacteristicRepository:
    """Async repository for standalone CRUD on ``ServiceCharacteristic``.

    All methods accept an ``AsyncSession`` injected by the FastAPI dependency.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_all_by_service_id(
        self,
        service_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ServiceCharacteristicOrm], int]:
        """Return a paginated list of characteristics for a service instance.

        Args:
            service_id: The parent Service UUID.
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            Tuple of (items, total_count).
        """
        base_q = select(ServiceCharacteristicOrm).where(
            ServiceCharacteristicOrm.service_id == service_id
        )
        count_q = (
            select(func.count())
            .select_from(ServiceCharacteristicOrm)
            .where(ServiceCharacteristicOrm.service_id == service_id)
        )

        total = (await self._db.execute(count_q)).scalar_one()
        result = await self._db.execute(
            base_q.offset(offset).limit(limit).order_by(
                ServiceCharacteristicOrm.created_at.asc()
            )
        )
        return list(result.scalars().all()), total

    async def get_by_id(
        self, service_id: str, char_id: str
    ) -> ServiceCharacteristicOrm | None:
        """Fetch a single characteristic scoped to its parent service.

        Args:
            service_id: Parent service UUID — ensures scope isolation.
            char_id: Characteristic UUID.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceCharacteristicOrm).where(
                ServiceCharacteristicOrm.id == char_id,
                ServiceCharacteristicOrm.service_id == service_id,
            )
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(
        self, service_id: str, data: ServiceCharacteristicCreate
    ) -> ServiceCharacteristicOrm:
        """Persist a new ServiceCharacteristic under the given service.

        Args:
            service_id: Parent Service UUID.
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        char_id = str(uuid.uuid4())
        char_data = data.model_dump(exclude={"characteristic_value"})

        orm = ServiceCharacteristicOrm(
            id=char_id,
            service_id=service_id,
            **char_data,
        )

        for cv in data.characteristic_value:
            orm.characteristic_value.append(
                CharacteristicValueOrm(
                    id=str(uuid.uuid4()),
                    char_id=char_id,
                    **cv.model_dump(),
                )
            )

        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(
        self, service_id: str, char_id: str, data: ServiceCharacteristicPatch
    ) -> ServiceCharacteristicOrm | None:
        """Partial update of a ServiceCharacteristic (PATCH semantics).

        Args:
            service_id: Parent service UUID.
            char_id: Characteristic UUID.
            data: Partial patch schema.

        Returns:
            Patched ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(service_id, char_id)
        if orm is None:
            return None

        for field, value in data.model_dump(exclude_none=True).items():
            if hasattr(orm, field):
                setattr(orm, field, value)

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, service_id: str, char_id: str) -> bool:
        """Delete a ServiceCharacteristic and its values (CASCADE).

        Args:
            service_id: Parent service UUID.
            char_id: Characteristic UUID.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(service_id, char_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True


class CharacteristicValueRepository:
    """Async repository for standalone CRUD on ``CharacteristicValue``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_all_by_char_id(
        self,
        char_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[CharacteristicValueOrm], int]:
        """Return all values for a given characteristic.

        Args:
            char_id: Parent ServiceCharacteristic UUID.
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            Tuple of (items, total_count).
        """
        base_q = select(CharacteristicValueOrm).where(
            CharacteristicValueOrm.char_id == char_id
        )
        count_q = (
            select(func.count())
            .select_from(CharacteristicValueOrm)
            .where(CharacteristicValueOrm.char_id == char_id)
        )

        total = (await self._db.execute(count_q)).scalar_one()
        result = await self._db.execute(
            base_q.offset(offset).limit(limit).order_by(
                CharacteristicValueOrm.created_at.asc()
            )
        )
        return list(result.scalars().all()), total

    async def get_by_id(
        self, char_id: str, val_id: str
    ) -> CharacteristicValueOrm | None:
        """Fetch a single value scoped to its parent characteristic.

        Args:
            char_id: Parent characteristic UUID.
            val_id: CharacteristicValue UUID.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(CharacteristicValueOrm).where(
                CharacteristicValueOrm.id == val_id,
                CharacteristicValueOrm.char_id == char_id,
            )
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(
        self, char_id: str, data: CharacteristicValueCreate
    ) -> CharacteristicValueOrm:
        """Persist a new CharacteristicValue.

        Args:
            char_id: Parent ServiceCharacteristic UUID.
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        orm = CharacteristicValueOrm(
            id=str(uuid.uuid4()),
            char_id=char_id,
            **data.model_dump(),
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, char_id: str, val_id: str) -> bool:
        """Delete a CharacteristicValue.

        Args:
            char_id: Parent characteristic UUID.
            val_id: CharacteristicValue UUID.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(char_id, val_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
