"""SQLAlchemy ORM models for TMF642 Alarm Management, TMF628 Performance Management,
and TMF657 Service Level Management (Assurance module).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.db.base import Base, TimestampMixin


class AlarmOrm(Base, TimestampMixin):
    """Represents a fault event raised against an active Service instance.

    Maps to the TMF642 ``Alarm`` entity.

    State machine:
        raised → acknowledged → cleared
    """

    __tablename__ = "alarm"

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
        default="raised",
        index=True,
    )  # raised | acknowledged | cleared

    # Fault classification
    alarm_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # critical | major | minor | warning | indeterminate
    probable_cause: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specific_problem: Mapped[str | None] = mapped_column(Text, nullable=True)

    # FK → Service (inventory); RESTRICT prevents service deletion while alarms remain
    service_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Timestamps for state transitions
    raised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PerformanceMeasurementOrm(Base, TimestampMixin):
    """Represents a scheduled or completed performance measurement on a Service.

    Maps to the TMF628 ``PerformanceMeasurement`` entity.

    State machine:
        scheduled → completed | failed
    """

    __tablename__ = "performance_measurement"

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
        default="scheduled",
        index=True,
    )  # scheduled | completed | failed

    # Metric details — metric_name is indexed for SLO violation lookup
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(64), nullable=True)
    granularity: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # minutely | hourly | daily | weekly | monthly

    # FK → Service (inventory)
    service_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Scheduling
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ServiceLevelObjectiveOrm(Base, TimestampMixin):
    """Represents a Service Level Objective (SLO) evaluated against metric measurements.

    Maps to the TMF657 ``ServiceLevel`` entity.

    State machine:
        active ↔ violated (only via check_violations)
        active | violated → suspended
        suspended → active
    """

    __tablename__ = "service_level_objective"

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
    )  # active | violated | suspended

    # Threshold definition
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    threshold_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    direction: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )  # above | below
    tolerance: Mapped[float | None] = mapped_column(Float, nullable=True)

    # FK → Service (inventory)
    service_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Optional FK → ServiceLevelSpecification (catalog)
    sls_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_level_specification.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
