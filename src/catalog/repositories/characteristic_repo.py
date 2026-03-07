"""Data-access layer for TMF633 ServiceSpecCharacteristic and CharacteristicValueSpecification."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models.orm import (
    CharacteristicValueSpecificationOrm,
    ServiceSpecCharacteristicOrm,
)
from src.catalog.models.schemas import (
    CharacteristicValueSpecCreate,
    ServiceSpecCharacteristicCreate,
    ServiceSpecCharacteristicPatch,
)


class CharacteristicSpecRepository:
    """Async repository for standalone CRUD on ``ServiceSpecCharacteristic``.

    All methods accept an ``AsyncSession`` injected by the FastAPI dependency.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_all_by_spec_id(
        self,
        spec_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ServiceSpecCharacteristicOrm], int]:
        """Return a paginated list of characteristics for a given specification.

        Args:
            spec_id: The parent ServiceSpecification UUID.
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            Tuple of (items, total_count).
        """
        base_q = select(ServiceSpecCharacteristicOrm).where(
            ServiceSpecCharacteristicOrm.service_spec_id == spec_id
        )
        count_q = (
            select(func.count())
            .select_from(ServiceSpecCharacteristicOrm)
            .where(ServiceSpecCharacteristicOrm.service_spec_id == spec_id)
        )

        total = (await self._db.execute(count_q)).scalar_one()
        result = await self._db.execute(
            base_q.offset(offset).limit(limit).order_by(
                ServiceSpecCharacteristicOrm.created_at.asc()
            )
        )
        return list(result.scalars().all()), total

    async def get_by_id(
        self, spec_id: str, char_id: str
    ) -> ServiceSpecCharacteristicOrm | None:
        """Fetch a single characteristic scoped to its parent specification.

        Args:
            spec_id: Parent specification UUID — ensures scope isolation.
            char_id: Characteristic UUID.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceSpecCharacteristicOrm).where(
                ServiceSpecCharacteristicOrm.id == char_id,
                ServiceSpecCharacteristicOrm.service_spec_id == spec_id,
            )
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(
        self, spec_id: str, data: ServiceSpecCharacteristicCreate
    ) -> ServiceSpecCharacteristicOrm:
        """Persist a new ServiceSpecCharacteristic under the given specification.

        Args:
            spec_id: Parent ServiceSpecification UUID.
            data: Validated create schema.

        Returns:
            The newly created ORM instance (with value specs loaded).
        """
        char_id = str(uuid.uuid4())
        char_data = data.model_dump(exclude={"characteristic_value_specification"})

        orm = ServiceSpecCharacteristicOrm(
            id=char_id,
            service_spec_id=spec_id,
            **char_data,
        )

        for vs in data.characteristic_value_specification:
            orm.characteristic_value_specification.append(
                CharacteristicValueSpecificationOrm(
                    id=str(uuid.uuid4()),
                    char_spec_id=char_id,
                    **vs.model_dump(),
                )
            )

        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(
        self, spec_id: str, char_id: str, data: ServiceSpecCharacteristicPatch
    ) -> ServiceSpecCharacteristicOrm | None:
        """Partial update of a ServiceSpecCharacteristic (PATCH semantics).

        Args:
            spec_id: Parent specification UUID.
            char_id: Characteristic UUID.
            data: Partial patch schema.

        Returns:
            Patched ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(spec_id, char_id)
        if orm is None:
            return None

        for field, value in data.model_dump(exclude_none=True).items():
            if hasattr(orm, field):
                setattr(orm, field, value)

        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, spec_id: str, char_id: str) -> bool:
        """Delete a ServiceSpecCharacteristic (and its value specs via CASCADE).

        Args:
            spec_id: Parent specification UUID.
            char_id: Characteristic UUID.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(spec_id, char_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True


class CharacteristicValueSpecRepository:
    """Async repository for standalone CRUD on ``CharacteristicValueSpecification``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_all_by_char_id(
        self,
        char_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[CharacteristicValueSpecificationOrm], int]:
        """Return all value specifications for a given characteristic.

        Args:
            char_id: Parent ServiceSpecCharacteristic UUID.
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            Tuple of (items, total_count).
        """
        base_q = select(CharacteristicValueSpecificationOrm).where(
            CharacteristicValueSpecificationOrm.char_spec_id == char_id
        )
        count_q = (
            select(func.count())
            .select_from(CharacteristicValueSpecificationOrm)
            .where(CharacteristicValueSpecificationOrm.char_spec_id == char_id)
        )

        total = (await self._db.execute(count_q)).scalar_one()
        result = await self._db.execute(
            base_q.offset(offset).limit(limit).order_by(
                CharacteristicValueSpecificationOrm.created_at.asc()
            )
        )
        return list(result.scalars().all()), total

    async def get_by_id(
        self, char_id: str, vs_id: str
    ) -> CharacteristicValueSpecificationOrm | None:
        """Fetch a single value specification scoped to its parent characteristic.

        Args:
            char_id: Parent characteristic UUID.
            vs_id: Value specification UUID.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(CharacteristicValueSpecificationOrm).where(
                CharacteristicValueSpecificationOrm.id == vs_id,
                CharacteristicValueSpecificationOrm.char_spec_id == char_id,
            )
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(
        self, char_id: str, data: CharacteristicValueSpecCreate
    ) -> CharacteristicValueSpecificationOrm:
        """Persist a new CharacteristicValueSpecification.

        Args:
            char_id: Parent ServiceSpecCharacteristic UUID.
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        orm = CharacteristicValueSpecificationOrm(
            id=str(uuid.uuid4()),
            char_spec_id=char_id,
            **data.model_dump(),
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, char_id: str, vs_id: str) -> bool:
        """Delete a CharacteristicValueSpecification.

        Args:
            char_id: Parent characteristic UUID.
            vs_id: Value specification UUID.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(char_id, vs_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True
