"""Generic Pydantic schemas for TMF event notifications.

These schemas can be used by any domain module to publish or consume
TMF-style lifecycle events (e.g. ``ServiceSpecificationCreateEvent``).
"""

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class EventPayload(BaseModel, Generic[T]):
    """Inner ``event`` object carrying the changed resource."""

    resource: T


class TMFEvent(BaseModel, Generic[T]):
    """Envelope for a TMF event notification message."""

    event_id: str = Field(description="Unique event identifier (UUID)")
    event_time: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="UTC timestamp when the event was generated",
    )
    event_type: str = Field(
        description="Event type discriminator, e.g. ServiceSpecificationCreateEvent"
    )
    domain: str | None = Field(default=None, description="Domain originating the event")
    title: str | None = Field(default=None, description="Human-readable event title")
    description: str | None = Field(default=None, description="Event description")
    priority: str | None = Field(default=None, description="Event priority level")
    correlation_id: str | None = Field(
        default=None,
        description="Correlation identifier for distributed tracing",
    )
    event: EventPayload[T] = Field(description="Payload carrying the changed resource")
