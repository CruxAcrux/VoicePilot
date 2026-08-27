"""
Action registry — maps intent names to BaseAction instances.

Actions are registered at startup.  The registry is the single
dispatch point between the ConfirmationManager and the actual
platform-specific action implementations.
"""

from __future__ import annotations

import logging
from typing import Any

from voicepilot.executor.base import BaseAction
from voicepilot.parser.intent import ParsedCommand

logger = logging.getLogger(__name__)


class ActionRegistry:
    """
    Maintains a mapping of intent_name → BaseAction.

    Usage
    -----
        registry = ActionRegistry()
        registry.register(MyAction())

        # Later:
        registry.dispatch(parsed_command)
    """

    def __init__(self) -> None:
        self._actions: dict[str, BaseAction] = {}

    def register(self, action: BaseAction) -> None:
        """Register *action* for every intent name in `action.handles`."""
        for intent_name in action.handles:
            if intent_name in self._actions:
                logger.warning(
                    "Overriding existing action for %r: %s → %s",
                    intent_name,
                    self._actions[intent_name].__class__.__name__,
                    action.__class__.__name__,
                )
            self._actions[intent_name] = action
            logger.debug("Registered %s for intent %r", action.__class__.__name__, intent_name)

    def register_many(self, *actions: BaseAction) -> None:
        for action in actions:
            self.register(action)

    def dispatch(self, command: ParsedCommand) -> Any:
        """
        Find and execute the action for *command*.

        Raises
        ------
        KeyError
            If no action is registered for the command's intent.
        """
        intent_name = command.intent_name
        action = self._actions.get(intent_name)

        if action is None:
            raise KeyError(f"No action registered for intent {intent_name!r}")

        if not action.can_execute(command):
            raise RuntimeError(
                f"Action {action.__class__.__name__} reported it cannot execute "
                f"intent {intent_name!r} in the current environment"
            )

        logger.info(
            "Dispatching %r → %s (slots=%s)",
            intent_name,
            action.__class__.__name__,
            command.slots,
        )
        return action.execute(command)

    def has_action(self, intent_name: str) -> bool:
        return intent_name in self._actions

    def registered_intents(self) -> list[str]:
        return list(self._actions.keys())
