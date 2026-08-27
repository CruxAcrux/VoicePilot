"""
Window management actions using wmctrl and xdotool.

Handles:
  - minimize_window
  - maximize_window
  - close_window
  - move_workspace_left
  - move_workspace_right
"""

from __future__ import annotations

import logging
import shutil
import subprocess

from voicepilot.core.exceptions import ExecutorError
from voicepilot.executor.base import BaseAction
from voicepilot.parser.intent import ParsedCommand

logger = logging.getLogger(__name__)


def _run(args: list[str], timeout: int = 5) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


class WindowManagerAction(BaseAction):
    """Controls windows using wmctrl and xdotool."""

    handles = [
        "minimize_window",
        "maximize_window",
        "close_window",
        "move_workspace_left",
        "move_workspace_right",
    ]

    def can_execute(self, command: ParsedCommand) -> bool:
        return shutil.which("xdotool") is not None or shutil.which("wmctrl") is not None

    def execute(self, command: ParsedCommand) -> None:
        intent = command.intent_name

        if intent == "minimize_window":
            self._minimize(command.get_slot("app"))
        elif intent == "maximize_window":
            self._maximize(command.get_slot("app"))
        elif intent == "close_window":
            self._close_active()
        elif intent == "move_workspace_left":
            self._workspace_left()
        elif intent == "move_workspace_right":
            self._workspace_right()

    def _minimize(self, app: str | None) -> None:
        if app and shutil.which("wmctrl"):
            _run(["wmctrl", "-r", app, "-b", "add,hidden"])
        elif shutil.which("xdotool"):
            _run(["xdotool", "getactivewindow", "windowminimize"])
        else:
            raise ExecutorError("wmctrl or xdotool required to minimize windows")
        logger.info("Window minimized")

    def _maximize(self, app: str | None) -> None:
        if app and shutil.which("wmctrl"):
            _run(["wmctrl", "-r", app, "-b", "add,maximized_vert,maximized_horz"])
        elif shutil.which("xdotool"):
            win_id = subprocess.check_output(
                ["xdotool", "getactivewindow"], text=True
            ).strip()
            _run(["xdotool", "windowsize", "--sync", win_id, "100%", "100%"])
        else:
            raise ExecutorError("wmctrl or xdotool required to maximize windows")
        logger.info("Window maximized")

    def _close_active(self) -> None:
        if shutil.which("xdotool"):
            _run(["xdotool", "getactivewindow", "windowclose"])
        elif shutil.which("wmctrl"):
            _run(["wmctrl", "-c", ":ACTIVE:"])
        else:
            raise ExecutorError("xdotool or wmctrl required to close windows")
        logger.info("Active window closed")

    def _workspace_left(self) -> None:
        if shutil.which("xdotool"):
            _run(["xdotool", "set_desktop", "--relative", "--", "-1"])
        logger.info("Moved to workspace left")

    def _workspace_right(self) -> None:
        if shutil.which("xdotool"):
            _run(["xdotool", "set_desktop", "--relative", "1"])
        logger.info("Moved to workspace right")
