"""SQLAlchemy ORM models for TMF640 Service Activation & Configuration."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.db.base import Base, TimestampMixin


class ServiceConfigurationParamOrm(Base, TimestampMixin):
    """A key/value configuration parameter associated with an activation job.

    Maps to the TMF640 ``ServiceConfigurationParam`` entity.
    """

    __tablename__ = "service_configuration_param"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # FK → parent job (CASCADE — deleting a job removes its params)
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_activation_job.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job: Mapped["ServiceActivationJobOrm"] = relationship(back_populates="params")


class ServiceActivationJobOrm(Base, TimestampMixin):
    """SQLAlchemy model for TMF640 ``ServiceActivationJob``.

    Job state machine:
        accepted → running → succeeded
                           ↘ failed
                 ↘ cancelled  (from accepted or running)
    """

    __tablename__ = "service_activation_job"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    href: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Core fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Job type: provision | activate | modify | deactivate | terminate
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Lifecycle state (default: accepted)
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="accepted",
        index=True,
    )

    # Execution mode
    mode: Mapped[str | None] = mapped_column(String(32), nullable=True)         # immediate | deferred
    start_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)   # automatic | manual

    # Scheduling / actuals
    scheduled_start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_completion_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_completion_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Failure info
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # TMF annotation fields
    type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    base_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    schema_location: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # FK → Service (RESTRICT — cannot delete a Service with pending/running jobs)
    service_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationship to configuration params (eager-loaded)
    params: Mapped[list[ServiceConfigurationParamOrm]] = relationship(
        back_populates="job",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
