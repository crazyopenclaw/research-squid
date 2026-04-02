"""
In-process event bus with optional Postgres persistence.

The event bus is the sole interface between the research engine and
any presentation layer. The core system emits events; subscribers
decide how to display or store them.

Architecture:
    - Synchronous subscribers (callbacks) for immediate display (CLI)
    - Async subscribers for I/O-bound operations (DB persistence)
    - Wildcard "*" subscription to catch all events
    - Thread-safe for future multi-threaded agent execution
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

from src.config import Settings, settings as default_settings
from src.models.events import Event, EventType
from src.session_context import get_current_session_id

logger = logging.getLogger(__name__)

# Type aliases for subscriber callbacks
SyncSubscriber = Callable[[Event], None]
AsyncSubscriber = Callable[[Event], Coroutine[Any, Any, None]]
Subscriber = SyncSubscriber | AsyncSubscriber


class EventBus:
    """
    Publish/subscribe event bus for research institute events.

    Subscribers register for specific event types or use "*" to
    receive all events. Supports both sync and async callbacks.

    Usage:
        bus = EventBus()

        # Subscribe to specific events
        bus.subscribe(EventType.ARTIFACT_CREATED, my_handler)

        # Subscribe to everything
        bus.subscribe("*", log_all_events)

        # Publish
        await bus.publish(Event(event_type=EventType.ARTIFACT_CREATED, ...))
    """

    def __init__(self, config: Settings | None = None) -> None:
        self._config = config or default_settings
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)
        self._history: list[Event] = []
        self._max_history = self._config.event_bus_max_history

    def subscribe(
        self,
        event_type: EventType | str,
        callback: Subscriber,
    ) -> None:
        """
        Register a callback for a specific event type.

        Args:
            event_type: The event type to listen for, or "*" for all events.
            callback: Sync or async function called with the Event.
        """
        key = event_type.value if isinstance(event_type, EventType) else event_type
        self._subscribers[key].append(callback)

    def unsubscribe(
        self,
        event_type: EventType | str,
        callback: Subscriber,
    ) -> None:
        """Remove a previously registered callback."""
        key = event_type.value if isinstance(event_type, EventType) else event_type
        self._subscribers[key] = [
            cb for cb in self._subscribers[key] if cb is not callback
        ]

    async def publish(self, event: Event) -> None:
        """
        Emit an event to all matching subscribers.

        Notifies both type-specific and wildcard ("*") subscribers.
        Async subscribers are awaited; sync subscribers are called directly.
        Errors in subscribers are logged but don't prevent other
        subscribers from receiving the event.
        """
        if not event.session_id:
            event.session_id = get_current_session_id()

        # Keep a bounded history for replay/debugging
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Collect all matching subscribers
        key = event.event_type.value
        targets = list(self._subscribers.get(key, []))
        targets.extend(self._subscribers.get("*", []))

        for callback in targets:
            try:
                result = callback(event)
                # If the callback is async, await it
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception(
                    "Event subscriber error for %s", event.event_type
                )

    @property
    def history(self) -> list[Event]:
        """Recent event history for debugging and replay."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear the event history buffer."""
        self._history.clear()
