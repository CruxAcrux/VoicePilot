"""
Keyboard shortcut actions using pynput.

Handles generic keyboard control — used by the VS Code integration
and any command that maps to a key combination.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Union

from voicepilot.executor.base import BaseAction
from voicepilot.parser.intent import ParsedCommand

if TYPE_CHECKING:
    from pynput.keyboard import Key

logger = logging.getLogger(__name__)

# Type alias for pynput key specifications. pynput is imported lazily inside
# the methods that need it, so it is only a type-checking reference here.
KeySpec = Union[str, "Key"] if TYPE_CHECKING else Any


class KeyboardAction(BaseAction):
    """
    Sends keyboard shortcuts using pynput.

    This class is both a BaseAction subclass *and* a utility used
    directly by other actions (e.g. VSCodeAction) to send key combos.
    """

    handles: list[str] = []  # Not registered directly; used as a utility

    def execute(self, command: ParsedCommand) -> None:
        pass  # Not dispatched directly

    # ------------------------------------------------------------------
    # Public utility methods
    # ------------------------------------------------------------------

    def hotkey(self, *keys: str) -> None:
        """
        Press and release a key combination.

        Example:
            kb.hotkey("ctrl", "s")          # Ctrl+S
            kb.hotkey("ctrl", "shift", "p") # Ctrl+Shift+P
        """
        from pynput.keyboard import Controller, Key  # type: ignore[import]

        key_map = {
            "ctrl": Key.ctrl,
            "shift": Key.shift,
            "alt": Key.alt,
            "super": Key.cmd,
            "enter": Key.enter,
            "tab": Key.tab,
            "escape": Key.esc,
            "esc": Key.esc,
            "backspace": Key.backspace,
            "delete": Key.delete,
            "home": Key.home,
            "end": Key.end,
            "page_up": Key.page_up,
            "page_down": Key.page_down,
            "up": Key.up,
            "down": Key.down,
            "left": Key.left,
            "right": Key.right,
            "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
            "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
            "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
        }

        kb = Controller()
        resolved: list[KeySpec] = []
        for k in keys:
            k_lower = k.lower()
            resolved.append(key_map.get(k_lower, k_lower))

        logger.debug("Sending hotkey: %s", "+".join(keys))

        # Press all modifier keys
        for key in resolved:
            kb.press(key)
            time.sleep(0.02)

        # Release in reverse order
        for key in reversed(resolved):
            kb.release(key)
            time.sleep(0.02)

    def type_text(self, text: str, delay_ms: int = 0) -> None:
        """Type a string character by character."""
        from pynput.keyboard import Controller  # type: ignore[import]

        kb = Controller()
        delay_s = delay_ms / 1000.0

        logger.debug("Typing %d characters", len(text))
        for char in text:
            kb.press(char)
            kb.release(char)
            if delay_s > 0:
                time.sleep(delay_s)

    def press_key(self, key_name: str) -> None:
        """Press and release a single named key."""
        self.hotkey(key_name)


# Module-level singleton for convenience
keyboard = KeyboardAction()
