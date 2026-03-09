"""SQLAlchemy ORM models for TMF648 Quote Management and TMF651 Agreement Management."""

import uuid
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.db.base import Base, TimestampMixin


class QuoteItemOrm(Base, TimestampMixin):
    """A line item within a Quote.

    Maps to the TMF648 ``QuoteItem`` sub-entity.
    """

    __tablename__ = "quote_item"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="add",
    )  # add | modify | delete | noChange
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="inProgress",
    )
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    item_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    price_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # recurring | nonRecurring | usage
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # FK → Quote CASCADE
    quote_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("quote.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # FK → ServiceSpecification RESTRICT (optional)
    related_service_spec_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_specification.id", ondelete="RESTRICT"),
        nullable=True,
    )


class QuoteOrm(Base, TimestampMixin):
    """Represents a commercial quote for a service.

    Maps to the TMF648 ``Quote`` entity.

    State machine:
        inProgress → pending | cancelled
        pending → approved | rejected | inProgress
        approved → accepted | cancelled
    """

    __tablename__ = "quote"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Core fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Lifecycle state
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="inProgress",
        index=True,
    )  # inProgress | pending | cancelled | approved | accepted | rejected

    # Dates
    from datetime import datetime

    quote_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    requested_completion_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expected_fulfillment_start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completion_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # FK → ServiceSpecification RESTRICT (optional)
    related_service_spec_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_specification.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Child items
    items: Mapped[list[QuoteItemOrm]] = relationship(
        "QuoteItemOrm",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ServiceLevelAgreementOrm(Base, TimestampMixin):
    """A contractual SLA metric attached to an Agreement.

    Maps to the TMF651 ``ServiceLevelAgreement`` sub-entity.
    """

    __tablename__ = "service_level_agreement"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # availability | latency | throughput | mttr | packetLoss | jitter
    metric_threshold: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    metric_unit: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # percent | ms | Mbps | hours
    conformance_period: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # daily | weekly | monthly

    # FK → Agreement CASCADE
    agreement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agreement.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class AgreementOrm(Base, TimestampMixin):
    """Represents a commercial or technical agreement tied to a service.

    Maps to the TMF651 ``Agreement`` entity.

    State machine:
        inProgress → active | cancelled
        active → expired | terminated
    Terminal states: expired | terminated | cancelled
    """

    __tablename__ = "agreement"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Core fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    agreement_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # commercial | technical | SLA

    # Lifecycle state
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="inProgress",
        index=True,
    )  # inProgress | active | expired | terminated | cancelled

    # Document metadata
    document_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default="1.0"
    )

    # Dates
    from datetime import datetime

    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_change_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # FK → ServiceSpecification RESTRICT (optional)
    related_service_spec_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_specification.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # FK → Quote SET NULL (safe to delete quote without cascading to agreement)
    related_quote_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("quote.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # FK → Service RESTRICT (optional)
    related_service_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Child SLAs
    slas: Mapped[list[ServiceLevelAgreementOrm]] = relationship(
        "ServiceLevelAgreementOrm",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
