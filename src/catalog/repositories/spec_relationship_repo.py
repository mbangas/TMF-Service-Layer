"""Data-access layer for TMF633 ServiceSpecRelationship."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models.orm import ServiceSpecRelationshipOrm
from src.catalog.models.schemas import ServiceSpecRelationshipCreate


class SpecRelationshipRepository:
    """Async repository for CRUD operations on ``ServiceSpecRelationship``.

    All methods accept an ``AsyncSession`` injected by the FastAPI dependency.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_all_by_spec_id(
        self,
        spec_id: str,
    ) -> list[ServiceSpecRelationshipOrm]:
        """Return all ServiceSpecRelationship entries for a given specification.

        Args:
            spec_id: The parent ServiceSpecification UUID.

        Returns:
            List of ORM instances.
        """
        result = await self._db.execute(
            select(ServiceSpecRelationshipOrm)
            .where(ServiceSpecRelationshipOrm.spec_id == spec_id)
            .order_by(ServiceSpecRelationshipOrm.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, rel_id: str) -> ServiceSpecRelationshipOrm | None:
        """Fetch a single ServiceSpecRelationship by its ID.

        Args:
            rel_id: The UUID of the relationship record.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceSpecRelationshipOrm).where(
                ServiceSpecRelationshipOrm.id == rel_id
            )
        )
        return result.scalar_one_or_none()

    async def exists(
        self,
        spec_id: str,
        related_spec_id: str,
        relationship_type: str,
    ) -> bool:
        """Check whether a specific relationship triple already exists.

        Args:
            spec_id: Owning spec UUID.
            related_spec_id: Related spec UUID.
            relationship_type: The relationship type string.

        Returns:
            ``True`` if the triple is already present.
        """
        result = await self._db.execute(
            select(ServiceSpecRelationshipOrm.id).where(
                and_(
                    ServiceSpecRelationshipOrm.spec_id == spec_id,
                    ServiceSpecRelationshipOrm.related_spec_id == related_spec_id,
                    ServiceSpecRelationshipOrm.relationship_type == relationship_type,
                )
            )
        )
        return result.scalar_one_or_none() is not None

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(
        self,
        spec_id: str,
        data: ServiceSpecRelationshipCreate,
    ) -> ServiceSpecRelationshipOrm:
        """Persist a new ServiceSpecRelationship.

        Args:
            spec_id: The UUID of the owning ServiceSpecification.
            data: Validated create payload.

        Returns:
            The newly created ORM instance.
        """
        orm = ServiceSpecRelationshipOrm(
            id=str(uuid.uuid4()),
            spec_id=spec_id,
            relationship_type=data.relationship_type,
            related_spec_id=data.related_spec_id,
            related_spec_name=data.related_spec_name,
            related_spec_href=data.related_spec_href,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, orm: ServiceSpecRelationshipOrm) -> None:
        """Delete a ServiceSpecRelationship.

        Args:
            orm: The ORM instance to delete.
        """
        await self._db.delete(orm)
        await self._db.flush()
