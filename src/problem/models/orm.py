"""SQLAlchemy ORM models for TMF621 Trouble Ticket Management and TMF656 Service Problem Management."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.db.base import Base, TimestampMixin


class TroubleTicketNoteOrm(Base):
    """A timestamped note attached to a TroubleTicket.

    Maps to the TMF621 ``Note`` sub-entity.
    """

    __tablename__ = "trouble_ticket_note"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # FK → TroubleTicket CASCADE
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("trouble_ticket.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class TroubleTicketOrm(Base, TimestampMixin):
    """Represents a trouble ticket raised by or for a customer against a service.

    Maps to the TMF621 ``TroubleTicket`` entity.

    State machine:
        submitted → inProgress → pending → inProgress → resolved → closed
        inProgress → resolved (shortcut)
        pending → resolved (shortcut)
    """

    __tablename__ = "trouble_ticket"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Core fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lifecycle state
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="submitted",
        index=True,
    )  # submitted | inProgress | pending | resolved | closed

    # Classification
    severity: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )  # critical | major | minor | warning
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ticket_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # serviceFailure | servicePerformanceDegradation | scheduledMaintenance | others

    # Resolution
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_resolution_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # FK → Service (inventory); RESTRICT prevents service deletion while tickets exist
    related_service_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # FK → Alarm; SET NULL so deleting the alarm preserves the ticket history
    related_alarm_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("alarm.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Child notes
    notes: Mapped[list[TroubleTicketNoteOrm]] = relationship(
        "TroubleTicketNoteOrm",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TroubleTicketNoteOrm.note_date",
    )


class ServiceProblemOrm(Base, TimestampMixin):
    """Represents a service problem record that aggregates tickets into a root-cause analysis.

    Maps to the TMF656 ``ServiceProblem`` entity.

    State machine:
        submitted → confirmed | rejected
        confirmed → active | rejected
        active → resolved
        resolved → closed
    """

    __tablename__ = "service_problem"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Core fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lifecycle state
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="submitted",
        index=True,
    )  # submitted | confirmed | active | rejected | resolved | closed

    # Classification
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    impact: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )  # criticalSystemImpact | localImpact | serviceImpact | noImpact
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Root cause & resolution
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_resolution_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # FK → Service (inventory); RESTRICT
    related_service_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # FK → TroubleTicket; SET NULL so deleting the ticket preserves problem history
    related_ticket_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("trouble_ticket.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
