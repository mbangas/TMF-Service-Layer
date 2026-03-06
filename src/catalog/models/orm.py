"""SQLAlchemy ORM models for TMF633 Service Catalog Management."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.db.base import Base, TimestampMixin


class ServiceSpecCharacteristicOrm(Base, TimestampMixin):
    """Represents a configurable characteristic of a ServiceSpecification.

    Maps to the TMF633 ``ServiceSpecCharacteristic`` entity.
    """

    __tablename__ = "service_spec_characteristic"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_unique: Mapped[bool] = mapped_column(default=False, nullable=False)
    min_cardinality: Mapped[int] = mapped_column(default=0, nullable=False)
    max_cardinality: Mapped[int] = mapped_column(default=1, nullable=False)
    extensible: Mapped[bool] = mapped_column(default=False, nullable=False)

    # FK to parent specification
    service_spec_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_specification.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_specification: Mapped["ServiceSpecificationOrm"] = relationship(
        back_populates="service_spec_characteristic"
    )


class ServiceLevelSpecificationOrm(Base, TimestampMixin):
    """Represents a Service Level Specification linked to a ServiceSpecification.

    Maps to the TMF633 ``ServiceLevelSpecification`` entity.
    """

    __tablename__ = "service_level_specification"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    validity_period_start: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validity_period_end: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # FK to parent specification
    service_spec_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_specification.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_specification: Mapped["ServiceSpecificationOrm"] = relationship(
        back_populates="service_level_specification"
    )


class ServiceSpecificationOrm(Base, TimestampMixin):
    """SQLAlchemy model for TMF633 ``ServiceSpecification``.

    Lifecycle states: draft → active → obsolete → retired
    """

    __tablename__ = "service_specification"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        index=True,
    )
    is_bundle: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_update: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # TMF annotation fields
    type: Mapped[str | None] = mapped_column("type", String(128), nullable=True)
    base_type: Mapped[str | None] = mapped_column("base_type", String(128), nullable=True)
    schema_location: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Relationships
    service_spec_characteristic: Mapped[list[ServiceSpecCharacteristicOrm]] = relationship(
        back_populates="service_specification",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    service_level_specification: Mapped[list[ServiceLevelSpecificationOrm]] = relationship(
        back_populates="service_specification",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
