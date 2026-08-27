"""
Dictation mode state manager.

Tracks whether VoicePilot is in dictation mode (speech → typed text)
or command mode (speech → commands).

The SpeechEngine routes transcriptions here first; if dictation mode
is active, text is injected into the focused application rather than
parsed as a command.
"""

from __future__ import annotations

import logging
import threading

from voicepilot.core.events import EventType, bus

logger = logging.getLogger(__name__)

_SOURCE = "dictation"


class DictationMode:
    """
    Manages the dictation mode toggle.

    When active, all transcribed text is injected as typed text.
    When inactive, text is sent to the command parser.

    Thread-safe — mode can be toggled from any thread.
    """

    def __init__(self) -> None:
        self._active = False
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._active:
                logger.debug("Dictation mode already active")
                return
            self._active = True

        logger.info("Dictation mode started")
        bus.publish_type(EventType.DICTATION_MODE_STARTED, source=_SOURCE)

    def stop(self) -> None:
        with self._lock:
            if not self._active:
                logger.debug("Dictation mode already inactive")
                return
            self._active = False

        logger.info("Dictation mode stopped")
        bus.publish_type(EventType.DICTATION_MODE_STOPPED, source=_SOURCE)

    def toggle(self) -> bool:
        """Toggle dictation mode. Returns the new state (True = active)."""
        with self._lock:
            self._active = not self._active
            new_state = self._active

        if new_state:
            logger.info("Dictation mode started (toggle)")
            bus.publish_type(EventType.DICTATION_MODE_STARTED, source=_SOURCE)
        else:
            logger.info("Dictation mode stopped (toggle)")
            bus.publish_type(EventType.DICTATION_MODE_STOPPED, source=_SOURCE)

        return new_state

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._active
