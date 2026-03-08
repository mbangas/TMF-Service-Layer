"""Data-access layer for TMF621 Trouble Ticket Management."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.problem.models.orm import TroubleTicketNoteOrm, TroubleTicketOrm
from src.problem.models.schemas import TroubleTicketCreate, TroubleTicketNoteCreate, TroubleTicketPatch


class TroubleTicketRepository:
    """Async repository providing CRUD operations for ``TroubleTicket`` and its notes.

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
        severity: str | None = None,
        related_service_id: str | None = None,
    ) -> tuple[list[TroubleTicketOrm], int]:
        """Return a paginated list of trouble tickets and the total count.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            state: Optional lifecycle state filter.
            severity: Optional severity filter.
            related_service_id: Optional service instance filter.

        Returns:
            Tuple of (items, total_count).
        """
        base_query = select(TroubleTicketOrm)
        count_query = select(func.count()).select_from(TroubleTicketOrm)

        if state:
            base_query = base_query.where(TroubleTicketOrm.state == state)
            count_query = count_query.where(TroubleTicketOrm.state == state)
        if severity:
            base_query = base_query.where(TroubleTicketOrm.severity == severity)
            count_query = count_query.where(TroubleTicketOrm.severity == severity)
        if related_service_id:
            base_query = base_query.where(TroubleTicketOrm.related_service_id == related_service_id)
            count_query = count_query.where(TroubleTicketOrm.related_service_id == related_service_id)

        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base_query.offset(offset).limit(limit).order_by(TroubleTicketOrm.created_at.desc())
        )
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, ticket_id: str) -> TroubleTicketOrm | None:
        """Fetch a single trouble ticket by its ID.

        Args:
            ticket_id: The UUID string identifier.

        Returns:
            The ORM instance or ``None`` if not found.
        """
        result = await self._db.execute(
            select(TroubleTicketOrm).where(TroubleTicketOrm.id == ticket_id)
        )
        return result.scalar_one_or_none()

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, data: TroubleTicketCreate) -> TroubleTicketOrm:
        """Persist a new TroubleTicket (and any initial notes).

        Args:
            data: Validated create schema.

        Returns:
            The newly created ORM instance.
        """
        ticket_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc)
        orm = TroubleTicketOrm(
            id=ticket_id,
            href=f"/tmf-api/troubleTicketManagement/v4/troubleTicket/{ticket_id}",
            name=data.name,
            description=data.description,
            state="submitted",
            severity=data.severity,
            priority=data.priority,
            ticket_type=data.ticket_type,
            expected_resolution_date=data.expected_resolution_date,
            related_service_id=data.related_service_id,
            related_alarm_id=data.related_alarm_id,
        )
        # Attach initial notes
        for note_data in data.notes:
            orm.notes.append(
                TroubleTicketNoteOrm(
                    id=str(uuid.uuid4()),
                    text=note_data.text,
                    author=note_data.author,
                    note_date=now,
                    ticket_id=ticket_id,
                )
            )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def patch(self, ticket_id: str, data: TroubleTicketPatch) -> TroubleTicketOrm | None:
        """Partial update of a TroubleTicket.

        Args:
            ticket_id: Identifier of the ticket to patch.
            data: Partial patch schema.

        Returns:
            Updated ORM instance or ``None`` if not found.
        """
        orm = await self.get_by_id(ticket_id)
        if orm is None:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(orm, field, value)
        await self._db.flush()
        await self._db.refresh(orm)
        return orm

    async def delete(self, ticket_id: str) -> bool:
        """Delete a TroubleTicket and its cascade-linked notes.

        Args:
            ticket_id: The UUID string identifier.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        orm = await self.get_by_id(ticket_id)
        if orm is None:
            return False
        await self._db.delete(orm)
        await self._db.flush()
        return True

    # ── Notes ─────────────────────────────────────────────────────────────────

    async def add_note(self, ticket_id: str, data: TroubleTicketNoteCreate) -> TroubleTicketNoteOrm:
        """Append a new note to a TroubleTicket.

        Args:
            ticket_id: The parent ticket UUID.
            data: Note create schema.

        Returns:
            The newly created note ORM instance.
        """
        note = TroubleTicketNoteOrm(
            id=str(uuid.uuid4()),
            text=data.text,
            author=data.author,
            note_date=datetime.now(tz=timezone.utc),
            ticket_id=ticket_id,
        )
        self._db.add(note)
        await self._db.flush()
        await self._db.refresh(note)
        return note

    async def get_note_by_id(self, note_id: str) -> TroubleTicketNoteOrm | None:
        """Fetch a single note by its ID.

        Args:
            note_id: The note UUID string.

        Returns:
            The ORM instance or ``None``.
        """
        result = await self._db.execute(
            select(TroubleTicketNoteOrm).where(TroubleTicketNoteOrm.id == note_id)
        )
        return result.scalar_one_or_none()

    async def delete_note(self, note_id: str) -> bool:
        """Delete a single note by its ID.

        Args:
            note_id: The note UUID string.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        note = await self.get_note_by_id(note_id)
        if note is None:
            return False
        await self._db.delete(note)
        await self._db.flush()
        return True
