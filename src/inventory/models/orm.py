"""SQLAlchemy ORM models for TMF638 Service Inventory Management."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.db.base import Base, TimestampMixin


class ServiceCharacteristicOrm(Base, TimestampMixin):
    """Represents a runtime characteristic value of an active Service instance.

    Maps to the TMF638 ``ServiceCharacteristic`` entity.
    """

    __tablename__ = "service_characteristic"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # FK → parent service (CASCADE — deleting a service removes its characteristics)
    service_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service: Mapped["ServiceOrm"] = relationship(back_populates="service_characteristic")


class ServiceOrm(Base, TimestampMixin):
    """SQLAlchemy model for TMF638 ``Service`` (active inventory instance).

    Lifecycle states: feasibilityChecked → designed → reserved →
                      inactive → active → terminated
    """

    __tablename__ = "service"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Core entity fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Lifecycle
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="inactive",
        index=True,
    )

    # Service dates
    start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # TMF annotation fields
    type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    base_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    schema_location: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # FK → ServiceSpecification (RESTRICT — spec cannot be deleted while a service
    # instance references it)
    service_spec_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_specification.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # FK → ServiceOrder (SET NULL — deleting an order does not orphan inventory
    # records; the service instance remains but loses its order reference)
    service_order_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_order.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationship to runtime characteristics (eager-loaded)
    service_characteristic: Mapped[list[ServiceCharacteristicOrm]] = relationship(
        back_populates="service",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
