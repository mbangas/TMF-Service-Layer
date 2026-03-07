"""SQLAlchemy ORM models for TMF653 Service Test Management.

Three tables:
  - ``service_test_specification`` — test templates (analogous to ServiceSpecification)
  - ``service_test``               — test run instances linked to active services
  - ``test_measure``               — nested measurement results within a test run

State machines:
    ServiceTestSpecification: active → retired → obsolete
    ServiceTest:              planned → inProgress → completed | failed | cancelled
    TestMeasure:              no lifecycle state — immutable once recorded
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.db.base import Base, TimestampMixin


class ServiceTestSpecificationOrm(Base, TimestampMixin):
    """Template definition for a category of service tests.

    Maps to the TMF653 ``ServiceTestSpecification`` entity.

    State machine:
        active → retired → obsolete
    """

    __tablename__ = "service_test_specification"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Core entity fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lifecycle state
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        index=True,
    )  # active | retired | obsolete

    # Test classification
    test_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # connectivity | performance | functional | etc.
    version: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Validity period
    valid_for_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_for_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Optional FK → ServiceSpecification (catalog); RESTRICT prevents orphan refs
    service_spec_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_specification.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )


class ServiceTestOrm(Base, TimestampMixin):
    """A scheduled or executed test run against an active Service instance.

    Maps to the TMF653 ``ServiceTest`` entity.

    State machine:
        planned → inProgress | cancelled
        inProgress → completed | failed | cancelled

    Note: direct planned → completed is intentionally blocked so that every
    test must progress through inProgress (i.e. actually run) before completing.
    """

    __tablename__ = "service_test"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Core entity fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lifecycle state
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="planned",
        index=True,
    )  # planned | inProgress | completed | failed | cancelled

    # Execution mode
    mode: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )  # automated | manual

    # Scheduling timestamps
    start_date_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_date_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # FK → Service (inventory); RESTRICT prevents deleting a service that has tests
    service_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Optional FK → ServiceTestSpecification; RESTRICT, nullable (ad-hoc tests allowed)
    test_spec_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_test_specification.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )


class TestMeasureOrm(Base):
    """A single metric result recorded during a ``ServiceTest`` run.

    Maps to the TMF653 ``TestMeasure`` entity.  TestMeasures are child records
    of a ServiceTest — they are CASCADE-deleted when the parent test is deleted,
    and are only accessible through the nested ``.../testMeasure`` sub-resource.

    Records are immutable once written; there is no PATCH endpoint.
    """

    __tablename__ = "test_measure"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # FK → ServiceTest; CASCADE so measures are cleaned up with the parent test
    service_test_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_test.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Metric details
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Qualitative result
    result: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # pass | fail | inconclusive

    # When the measurement was captured
    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
