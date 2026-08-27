"""
Risk classifier — assigns a RiskLevel to any ParsedCommand.

The risk level determines how much confirmation is required before
an action is executed.  The grammar defines a base risk per intent,
but this module can escalate risk based on contextual factors
(e.g. "delete" on a non-empty folder is always HIGH).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from voicepilot.parser.intent import ParsedCommand, RiskLevel

if TYPE_CHECKING:
    from voicepilot.core.config import ConfirmationSection

logger = logging.getLogger(__name__)

# Svensk beskrivning av varje intent-namn, för den TALADE sammanfattningen i
# bekräftelseprompten. Intent-namnen själva (engelska interna identifierare)
# rörs inte — bara hur de beskrivs muntligt för användaren.
_INTENT_DESCRIPTIONS_SV: dict[str, str] = {
    "open_application": "öppna program",
    "close_application": "stänga program",
    "create_folder": "skapa mapp",
    "create_file": "skapa fil",
    "delete_file": "ta bort fil",
    "delete_folder": "ta bort mapp",
    "move_file": "flytta fil",
    "copy_file": "kopiera fil",
    "rename_file": "byta namn på fil",
    "lock_computer": "låsa skärmen",
    "shutdown": "stänga av datorn",
    "restart": "starta om datorn",
    "take_screenshot": "ta en skärmbild",
    "minimize_window": "minimera fönstret",
    "maximize_window": "maximera fönstret",
    "close_window": "stänga fönstret",
    "vscode_run_project": "köra projektet i VS Code",
    "vscode_rename_symbol": "byta namn på symbol i VS Code",
}

# ---------------------------------------------------------------------------
# Escalation rules
# ---------------------------------------------------------------------------

# Intent names that are always HIGH risk regardless of grammar definition
_ALWAYS_HIGH: frozenset[str] = frozenset(
    {
        "shutdown",
        "restart",
        "delete_folder",
    }
)

# Intent names that are always MEDIUM risk
_ALWAYS_MEDIUM: frozenset[str] = frozenset(
    {
        "close_application",
        "close_window",
        "delete_file",
        "lock_computer",
        "vscode_run_project",
        "vscode_rename_symbol",
    }
)


def classify(command: ParsedCommand) -> RiskLevel:
    """
    Return the effective RiskLevel for *command*.

    Applies escalation rules on top of the grammar's base risk.
    """
    name = command.intent_name

    if name in _ALWAYS_HIGH:
        return RiskLevel.HIGH

    if name in _ALWAYS_MEDIUM and command.intent.risk == RiskLevel.LOW:
        return RiskLevel.MEDIUM

    return command.intent.risk


def risk_message(
    command: ParsedCommand,
    risk: RiskLevel,
    config: ConfirmationSection,
) -> str:
    """
    Return the spoken confirmation prompt for a given risk level.

    *config* supplies the actual configured confirmation phrases
    (``medium_risk_phrase``, ``high_risk_phrase``, ``cancel_phrase``) so the
    prompt always tells the user to say exactly what
    :meth:`ConfirmationManager.receive_response` will actually accept —
    never a hardcoded phrase that could drift out of sync with config.
    """
    action_summary = _summarise(command)

    if risk == RiskLevel.MEDIUM:
        return (
            f"Jag uppfattade: {action_summary}. "
            f"Säg '{config.medium_risk_phrase}' för att fortsätta "
            f"eller '{config.cancel_phrase}' för att avbryta."
        )
    if risk == RiskLevel.HIGH:
        return (
            f"Varning: {action_summary}. Detta går inte att ångra. "
            f"Säg '{config.high_risk_phrase}' för att fortsätta "
            f"eller '{config.cancel_phrase}' för att avbryta."
        )
    return ""


def _summarise(command: ParsedCommand) -> str:
    """Build a short, spoken-Swedish summary of the command."""
    name = _INTENT_DESCRIPTIONS_SV.get(
        command.intent_name, command.intent_name.replace("_", " ")
    )
    slots = command.slots
    if slots:
        slot_str = ", ".join(f"{k}={v!r}" for k, v in slots.items())
        return f"{name} ({slot_str})"
    return name
