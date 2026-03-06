"""In-memory event bus for TMF lifecycle event notifications.

Implements a simple singleton ``EventBus`` backed by a :class:`collections.deque`
with a fixed maximum length.  Designed for development diagnostics only — events
are lost on process restart.
"""

from collections import deque

from src.shared.events.schemas import TMFEvent

# Module-level singleton storage
_event_store: deque[TMFEvent] = deque(maxlen=500)


class EventBus:
    """Singleton event bus for publishing and reading TMF events.

    All methods are class-level so callers do not need to hold an instance.
    """

    @classmethod
    def publish(cls, event: TMFEvent) -> None:
        """Append an event to the in-memory store.

        Args:
            event: The :class:`TMFEvent` to persist.
        """
        _event_store.append(event)

    @classmethod
    def get_events(cls, limit: int = 100) -> list[TMFEvent]:
        """Return the most recent events up to *limit*.

        Args:
            limit: Maximum number of events to return (most recent first).

        Returns:
            A list of :class:`TMFEvent` instances.
        """
        events = list(_event_store)
        return events[-limit:]

    @classmethod
    def clear(cls) -> None:
        """Remove all events from the store (useful in tests)."""
        _event_store.clear()
