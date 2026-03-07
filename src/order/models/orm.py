"""SQLAlchemy ORM models for TMF641 Service Order Management."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.db.base import Base, TimestampMixin


class ServiceOrderItemRelationshipOrm(Base, TimestampMixin):
    """Represents a dependency between two ServiceOrderItems within the same order.

    Maps to the TMF641 ``ServiceOrderItemRelationship`` entity.
    The ``related_item_label`` stores the client-assigned ``order_item_id`` string
    of the predecessor item (e.g. ``"1"``, ``"2"``), per TMF641 specification.
    """

    __tablename__ = "service_order_item_relationship"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False)
    related_item_label: Mapped[str] = mapped_column(String(64), nullable=False)

    # FK → parent order item (CASCADE — deleting an item removes its relationships)
    order_item_orm_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_order_item.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_item: Mapped["ServiceOrderItemOrm"] = relationship(
        back_populates="item_relationships"
    )


class ServiceOrderItemOrm(Base, TimestampMixin):
    """Represents a single item within a ServiceOrder.

    Maps to the TMF641 ``ServiceOrderItem`` entity.
    """

    __tablename__ = "service_order_item"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    order_item_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Client-assigned sequence label (e.g. '1', '2')",
    )
    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="add",
        comment="add | modify | delete | noChange",
    )
    state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # FK → parent service_order
    service_order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_order: Mapped["ServiceOrderOrm"] = relationship(back_populates="order_item")

    # FK → service_specification (RESTRICT so spec cannot be deleted while referenced)
    service_spec_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_specification.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    service_spec_href: Mapped[str | None] = mapped_column(String(512), nullable=True)
    service_spec_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Service fields
    service_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Intra-order item relationships (TMF641 ServiceOrderItemRelationship)
    item_relationships: Mapped[list["ServiceOrderItemRelationshipOrm"]] = relationship(
        back_populates="order_item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ServiceOrderOrm(Base, TimestampMixin):
    """SQLAlchemy model for TMF641 ``ServiceOrder``.

    Lifecycle states: acknowledged → inProgress → completed | failed | cancelled
    """

    __tablename__ = "service_order"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # BaseEntity-like fields stored on ORM
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)

    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="acknowledged",
        index=True,
    )

    order_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completion_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_completion_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expected_completion_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # TMF annotation fields
    type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    base_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    schema_location: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Relationship
    order_item: Mapped[list[ServiceOrderItemOrm]] = relationship(
        back_populates="service_order",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
