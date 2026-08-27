"""
Internal event bus for VoicePilot.

All inter-module communication happens through this bus.
Modules publish events; other modules subscribe to them.
This decouples every layer from every other layer.

Usage:
    bus = EventBus()

    @bus.subscribe(EventType.TRANSCRIPTION_READY)
    def handle(event: Event) -> None:
        print(event.data)

    bus.publish(Event(EventType.TRANSCRIPTION_READY, data={"text": "open firefox"}))
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class EventType(Enum):
    # --- Audio / Speech ---
    AUDIO_CHUNK_READY = auto()          # Raw PCM audio chunk captured
    VAD_SPEECH_START = auto()           # Voice activity detected
    VAD_SPEECH_END = auto()             # Silence detected after speech
    WAKE_WORD_DETECTED = auto()         # Wake word confirmed
    TRANSCRIPTION_READY = auto()        # Whisper produced a transcription
    TRANSCRIPTION_FAILED = auto()       # Transcription error

    # --- Parser ---
    COMMAND_PARSED = auto()             # Intent recognised from transcription
    COMMAND_UNKNOWN = auto()            # No intent matched
    DICTATION_TEXT_READY = auto()       # Text to inject (dictation mode)

    # --- Confirmation ---
    CONFIRMATION_REQUIRED = auto()      # Action needs user confirmation
    CONFIRMATION_RECEIVED = auto()      # User said "confirm"
    CONFIRMATION_CANCELLED = auto()     # User said "cancel" or timed out
    CONFIRMATION_TIMEOUT = auto()       # Confirmation window expired

    # --- Executor ---
    ACTION_STARTED = auto()             # Executor began running action
    ACTION_COMPLETED = auto()           # Action finished successfully
    ACTION_FAILED = auto()              # Action raised an error

    # --- Dictation ---
    DICTATION_MODE_STARTED = auto()
    DICTATION_MODE_STOPPED = auto()

    # --- Application lifecycle ---
    APP_READY = auto()
    APP_SHUTDOWN = auto()
    APP_ERROR = auto()

    # --- UI ---
    UI_STATUS_UPDATE = auto()           # Overlay should display a status message
    UI_NOTIFICATION = auto()            # Tray notification
    UI_SETTINGS_CHANGED = auto()        # User changed settings in the UI


@dataclass
class Event:
    """An event that flows through the bus."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"             # Module name that published the event

    def __repr__(self) -> str:
        return f"Event({self.type.name}, source={self.source!r}, data={self.data})"


# Type alias for subscriber callables
Subscriber = Callable[[Event], None]


class EventBus:
    """
    Thread-safe synchronous/asynchronous publish-subscribe event bus.

    Supports both synchronous callbacks and asyncio coroutines.
    All callbacks are invoked in the order they subscribed.
    Exceptions in callbacks are caught and logged so they do not
    break other subscribers.
    """

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[Subscriber]] = defaultdict(list)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(self, event_type: EventType) -> Callable[[Subscriber], Subscriber]:
        """Decorator to subscribe a function to an event type."""
        def decorator(func: Subscriber) -> Subscriber:
            self._add_subscriber(event_type, func)
            return func
        return decorator

    def on(self, event_type: EventType, callback: Subscriber) -> None:
        """Subscribe *callback* to *event_type* (imperative form)."""
        self._add_subscriber(event_type, callback)

    def off(self, event_type: EventType, callback: Subscriber) -> None:
        """Remove a previously registered subscriber."""
        with self._lock:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass

    def _add_subscriber(self, event_type: EventType, callback: Subscriber) -> None:
        with self._lock:
            self._subscribers[event_type].append(callback)
        logger.debug("Subscribed %s to %s", callback.__qualname__, event_type.name)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(self, event: Event) -> None:
        """
        Synchronously deliver *event* to all registered subscribers.

        Exceptions raised by individual subscribers are caught and logged
        so that one bad subscriber does not prevent others from receiving
        the event.
        """
        with self._lock:
            subscribers = list(self._subscribers.get(event.type, []))

        logger.debug("Publishing %r to %d subscriber(s)", event, len(subscribers))

        for subscriber in subscribers:
            try:
                result = subscriber(event)
                # If subscriber returned a coroutine, schedule it.
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        # No running loop — run synchronously
                        asyncio.run(result)
            except Exception:
                logger.exception(
                    "Subscriber %s raised an exception handling %s",
                    subscriber.__qualname__,
                    event.type.name,
                )

    def publish_type(
        self,
        event_type: EventType,
        data: dict[str, Any] | None = None,
        source: str = "unknown",
    ) -> None:
        """Convenience method: build and publish an event in one call."""
        self.publish(Event(type=event_type, data=data or {}, source=source))

    def clear(self) -> None:
        """Remove all subscribers. Useful in tests."""
        with self._lock:
            self._subscribers.clear()


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly in any module
# ---------------------------------------------------------------------------
bus = EventBus()
