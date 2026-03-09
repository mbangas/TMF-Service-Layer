"""Data-access layer for TMF651 Agreement Management."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.commercial.models.orm import AgreementOrm, ServiceLevelAgreementOrm
from src.commercial.models.schemas import AgreementCreate, AgreementPatch, ServiceLevelAgreementCreate


class AgreementRepository:
    """Async repository providing CRUD operations for ``Agreement`` and its SLAs.

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
        agreement_type: str | None = None,
        related_service_spec_id: str | None = None,
    ) -> tuple[list[AgreementOrm], int]:
        """Return a paginated list of agreements and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional lifecycle state filter.
            agreement_type: Optional agreement type filter.
            related_service_spec_id: Optional service spec filter.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(AgreementOrm)
        count_query = select(func.count()).select_from(AgreementOrm)

        if state:
            base_query = base_query.where(AgreementOrm.state == state)
            count_query = count_query.where(AgreementOrm.state == state)
        if agreement_type:
            base_query = base_query.where(AgreementOrm.agreement_type == agreement_type)
            count_query = count_query.where(AgreementOrm.agreement_type == agreement_type)
        if related_service_spec_id:
            base_query = base_query.where(AgreementOrm.related_service_spec_id == related_service_spec_id)
            count_query = count_query.where(AgreementOrm.related_service_spec_id == related_service_spec_id)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query.offset(offset).limit(limit).order_by(AgreementOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, agreement_id: str) -> AgreementOrm | None:
        """Fetch a single agreement by its ID.

        Args:
            agreement_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(AgreementOrm).where(AgreementOrm.id == agreement_id)
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: AgreementCreate) -> AgreementOrm:
        """Persist a new Agreement (and any initial SLAs).

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        agreement_id = str(uuid.uuid4())
        orm = AgreementOrm(
            id=agreement_id,
            href=f"/tmf-api/agreementManagement/v4/agreement/{agreement_id}",
            name=data.name,
            description=data.description,
            agreement_type=data.agreement_type,
            state="inProgress",
            document_number=data.document_number,
            version=data.version,
            start_date=data.start_date,
            end_date=data.end_date,
            related_service_spec_id=data.related_service_spec_id,
            related_quote_id=data.related_quote_id,
            related_service_id=data.related_service_id,
        )
        for sla_data in data.slas:
            orm.slas.append(
                ServiceLevelAgreementOrm(
                    id=str(uuid.uuid4()),
                    name=sla_data.name,
                    description=sla_data.description,
                    metric=sla_data.metric,
                    metric_threshold=sla_data.metric_threshold,
                    metric_unit=sla_data.metric_unit,
                    conformance_period=sla_data.conformance_period,
                    agreement_id=agreement_id,
                )
            )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(self, agreement_id: str, data: AgreementPatch) -> AgreementOrm | None:
        """Partial update of an Agreement.

        Args:
            agreement_id: Identifier of the agreement to patch.
            data: Partial patch schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(agreement_id)
        if orm is None:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(orm, field, value)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, agreement_id: str) -> bool:
        """Delete an Agreement and its cascade-linked SLAs.

        Args:
            agreement_id: The UUID string identifier.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(agreement_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True

    # ── SLAs ──────────────────────────────────────────────────────────────────

    async def add_sla(self, agreement_id: str, data: ServiceLevelAgreementCreate) -> ServiceLevelAgreementOrm:
        """Append a new SLA metric to an Agreement.

        Args:
            agreement_id: The parent agreement UUID.
            data: SLA create schema.

        Returns:
            The newly created SLA ORM instance.
        """
        sla = ServiceLevelAgreementOrm(
            id=str(uuid.uuid4()),
            name=data.name,
            description=data.description,
            metric=data.metric,
            metric_threshold=data.metric_threshold,
            metric_unit=data.metric_unit,
            conformance_period=data.conformance_period,
            agreement_id=agreement_id,
        )
        self._db.add(sla)
        await self._db.flush()
        await self._db.refresh(sla)
        return sla

    async def get_sla_by_id(self, sla_id: str) -> ServiceLevelAgreementOrm | None:
        """Fetch a single SLA by its ID.

        Args:
            sla_id: The SLA UUID string.

        Returns:
            The ORM instance or ``None``.
        """
        result = await self._db.execute(
            select(ServiceLevelAgreementOrm).where(ServiceLevelAgreementOrm.id == sla_id)
        )
        return result.scalar_one_or_none()

    async def delete_sla(self, sla_id: str) -> bool:
        """Delete a single SLA by its ID.

        Args:
            sla_id: The SLA UUID string.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        sla = await self.get_sla_by_id(sla_id)
        if sla is None:
            return False
        await self._db.delete(sla)
        await self._db.flush()
        return True
