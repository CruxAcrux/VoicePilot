"""
Plugin system skeleton.

Plugins extend VoicePilot with custom intents and actions.
A plugin is a Python module (or package) that exports a subclass of
BasePlugin.

Plugin discovery:
  1. Built-in plugins in voicepilot/plugins/
  2. User plugins in ~/.local/share/voicepilot/plugins/
  3. System plugins in /usr/share/voicepilot/plugins/

Each plugin has the opportunity to:
  - Register new Intent objects with the CommandInterpreter
  - Register new BaseAction objects with the ActionRegistry
  - Subscribe to events on the bus
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from voicepilot.executor.registry import ActionRegistry
    from voicepilot.parser.interpreter import CommandInterpreter

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    """
    Abstract base class for VoicePilot plugins.

    Plugins are discovered and loaded at startup.
    They declare their intents and actions, which are merged into
    the global registry.

    Attributes
    ----------
    name:
        Unique plugin identifier (snake_case).
    version:
        Plugin version string.
    description:
        Short description shown in the plugin manager.
    author:
        Plugin author name.
    """

    name: str = "unnamed_plugin"
    version: str = "0.0.1"
    description: str = ""
    author: str = ""

    @abstractmethod
    def setup(
        self,
        interpreter: CommandInterpreter,
        registry: ActionRegistry,
    ) -> None:
        """
        Called once at startup.

        Use this method to:
          - Append new Intents to `interpreter.intents`
          - Call `registry.register(MyAction())`
          - Subscribe to event bus events
        """

    def teardown(self) -> None:
        """Called when the plugin is unloaded. Override to clean up."""

    def __repr__(self) -> str:
        return f"Plugin({self.name!r} v{self.version})"
