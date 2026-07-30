"""
Risk classifier — assigns a RiskLevel to any ParsedCommand.

The risk level determines how much confirmation is required before
an action is executed.  The grammar defines a base risk per intent,
but this module can escalate risk based on contextual factors
(e.g. "delete" on a non-empty folder is always HIGH).
"""

from __future__ import annotations

import logging

from voicepilot.parser.intent import ParsedCommand, RiskLevel

logger = logging.getLogger(__name__)

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


def risk_message(command: ParsedCommand, risk: RiskLevel) -> str:
    """Return the spoken confirmation prompt for a given risk level."""
    action_summary = _summarise(command)

    if risk == RiskLevel.MEDIUM:
        return (
            f"I understood: {action_summary}. "
            "Say 'confirm' to proceed or 'cancel' to abort."
        )
    if risk == RiskLevel.HIGH:
        return (
            f"Warning: {action_summary}. This cannot be undone. "
            "Say 'confirm delete' to proceed or 'cancel' to abort."
        )
    return ""


def _summarise(command: ParsedCommand) -> str:
    """Build a short human-readable summary of the command."""
    name = command.intent_name.replace("_", " ")
    slots = command.slots
    if slots:
        slot_str = ", ".join(f"{k}={v!r}" for k, v in slots.items())
        return f"{name} ({slot_str})"
    return name
