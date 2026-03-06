"""SQLAlchemy ORM models for TMF645 Service Qualification Management."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.db.base import Base, TimestampMixin


class ServiceQualificationItemOrm(Base, TimestampMixin):
    """A single qualification item scoped to a service specification.

    Maps to the TMF645 ``ServiceQualificationItem`` entity.
    Each item records the result of checking feasibility for one
    service specification within a parent qualification request.
    """

    __tablename__ = "service_qualification_item"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # FK → parent qualification (CASCADE — deleting a qualification removes items)
    qualification_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_qualification.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    qualification: Mapped["ServiceQualificationOrm"] = relationship(back_populates="items")

    # Optional reference to a ServiceSpecification (TMF633)
    service_spec_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_specification.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Item lifecycle result
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="approved",
        index=True,
    )  # approved | rejected | unableToProvide

    qualifier_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    termination_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ServiceQualificationOrm(Base, TimestampMixin):
    """SQLAlchemy model for TMF645 ``ServiceQualification``.

    State machine:
        acknowledged → inProgress → accepted
                                 ↘ rejected
                     ↘ cancelled   (from acknowledged or inProgress)
    """

    __tablename__ = "service_qualification"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Core entity fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lifecycle state (default: acknowledged)
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="acknowledged",
        index=True,
    )

    # Scheduling / expiry
    expected_qualification_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expiration_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # TMF annotation fields
    type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    base_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    schema_location: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # One-to-many relationship to qualification items
    items: Mapped[list[ServiceQualificationItemOrm]] = relationship(
        back_populates="qualification",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
