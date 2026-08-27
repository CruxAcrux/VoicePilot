"""
Base class for all VoicePilot actions.

Every concrete action inherits from BaseAction and implements `execute()`.
The ActionRegistry dispatches ParsedCommands to the right BaseAction subclass.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from voicepilot.parser.intent import ParsedCommand

logger = logging.getLogger(__name__)


class BaseAction(ABC):
    """
    Abstract base class for all executable actions.

    Subclasses must implement `execute(command)`.
    They may optionally implement `can_execute(command)` to signal
    whether they are available in the current environment.
    """

    #: Intent name(s) this action handles
    handles: list[str] = []

    def can_execute(self, command: ParsedCommand) -> bool:  # noqa: ARG002
        """Return True if this action can currently execute *command*."""
        return True

    @abstractmethod
    def execute(self, command: ParsedCommand) -> Any:
        """Perform the action. Raises on failure."""

    def describe(self, command: ParsedCommand) -> str:
        """Return a short human-readable description of what will happen."""
        return f"{self.__class__.__name__} for {command.intent_name}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(handles={self.handles})"
