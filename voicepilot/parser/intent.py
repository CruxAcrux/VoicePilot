"""
Intent data models.

An Intent represents what the user wants to do.
A ParsedCommand is the result of matching a transcription to an intent,
with any extracted slot values filled in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class RiskLevel(Enum):
    """
    Safety classification for commands.

    LOW    — execute immediately
    MEDIUM — ask "confirm?"
    HIGH   — ask for full confirmation phrase
    """
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()


class IntentCategory(Enum):
    """Top-level grouping of command intents."""
    APP_CONTROL = auto()        # open / close / switch applications
    FILE_MANAGEMENT = auto()    # create / delete / search files & folders
    WINDOW_CONTROL = auto()     # minimize, maximize, move windows
    SYSTEM = auto()             # lock, shutdown, restart, volume
    DICTATION = auto()          # start/stop dictation mode
    VSCODE = auto()             # VS Code specific commands
    NAVIGATION = auto()         # go to line, open tab, etc.
    UNKNOWN = auto()


@dataclass
class Intent:
    """
    Defines a command that VoicePilot can execute.

    Fields
    ------
    name:
        Unique identifier, e.g. "open_application".
    category:
        High-level grouping.
    patterns:
        List of template strings with {slot} placeholders.
        Patterns are matched via rapidfuzz against the transcription.
    required_slots:
        Slot names that must be present for the intent to be valid.
    optional_slots:
        Slot names that may be absent.
    risk:
        Safety classification that determines confirmation behaviour.
    description:
        Human-readable description shown in help / settings.
    examples:
        Example phrases shown in documentation.
    """

    name: str
    category: IntentCategory
    patterns: list[str]
    required_slots: list[str] = field(default_factory=list)
    optional_slots: list[str] = field(default_factory=list)
    risk: RiskLevel = RiskLevel.LOW
    description: str = ""
    examples: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"Intent({self.name!r}, risk={self.risk.name})"


@dataclass
class ParsedCommand:
    """
    The result of matching a transcription to an Intent.

    Fields
    ------
    intent:
        The matched Intent object.
    slots:
        Extracted slot values, e.g. {"app": "firefox"}.
    raw_text:
        The original transcription string.
    confidence:
        Match confidence (0–100, from rapidfuzz ratio).
    pattern_matched:
        The specific pattern that produced the match.
    """

    intent: Intent
    slots: dict[str, Any]
    raw_text: str
    confidence: float
    pattern_matched: str

    @property
    def risk(self) -> RiskLevel:
        return self.intent.risk

    @property
    def intent_name(self) -> str:
        return self.intent.name

    def get_slot(self, name: str, default: Any = None) -> Any:
        return self.slots.get(name, default)

    def __repr__(self) -> str:
        return (
            f"ParsedCommand(intent={self.intent.name!r}, "
            f"slots={self.slots}, confidence={self.confidence:.1f})"
        )
