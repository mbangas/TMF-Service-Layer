"""Data-access layer for TMF638 ServiceRelationship (SID GB922)."""

import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.inventory.models.orm import ServiceRelationshipOrm
from src.inventory.models.schemas import ServiceRelationshipCreate


class ServiceRelationshipRepository:
    """Async repository for CRUD operations on ``ServiceRelationship``.

    All methods accept an ``AsyncSession`` injected by the FastAPI dependency.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_all_by_service_id(
        self,
        service_id: str,
    ) -> list[ServiceRelationshipOrm]:
        """Return all ServiceRelationship entries for a given service instance.

        Args:
            service_id: The parent Service UUID.

        Returns:
            List of ORM instances.
        """
        result = await self._db.execute(
            select(ServiceRelationshipOrm)
            .where(ServiceRelationshipOrm.service_id == service_id)
            .order_by(ServiceRelationshipOrm.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, rel_id: str) -> ServiceRelationshipOrm | None:
        """Fetch a single ServiceRelationship by its ID.

        Args:
            rel_id: The UUID of the relationship record.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(ServiceRelationshipOrm).where(ServiceRelationshipOrm.id == rel_id)
        )
        return result.scalar_one_or_none()

    async def exists(
        self,
        service_id: str,
        related_service_id: str,
        relationship_type: str,
    ) -> bool:
        """Check whether a specific service relationship triple already exists.

        Args:
            service_id: Owning service UUID.
            related_service_id: Related service UUID.
            relationship_type: The relationship type string.

        Returns:
            ``True`` if the triple is already present.
        """
        result = await self._db.execute(
            select(ServiceRelationshipOrm.id).where(
                and_(
                    ServiceRelationshipOrm.service_id == service_id,
                    ServiceRelationshipOrm.related_service_id == related_service_id,
                    ServiceRelationshipOrm.relationship_type == relationship_type,
                )
            )
        )
        return result.scalar_one_or_none() is not None

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(
        self,
        service_id: str,
        data: ServiceRelationshipCreate,
    ) -> ServiceRelationshipOrm:
        """Persist a new ServiceRelationship.

        Args:
            service_id: UUID of the owning Service instance.
            data: Validated create payload.

        Returns:
            The newly created ORM instance.
        """
        orm = ServiceRelationshipOrm(
            id=str(uuid.uuid4()),
            service_id=service_id,
            relationship_type=data.relationship_type,
            related_service_id=data.related_service_id,
            related_service_name=data.related_service_name,
            related_service_href=data.related_service_href,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, orm: ServiceRelationshipOrm) -> None:
        """Delete a ServiceRelationship.

        Args:
            orm: The ORM instance to delete.
        """
        await self._db.delete(orm)
        await self._db.flush()
