"""
Application launcher action.

Handles:
  - open_application
  - close_application
  - switch_to_application

Uses xdg-open for generic opening, direct subprocess for known apps,
and wmctrl for window focus switching.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time

import psutil

from voicepilot.core.desktop import resolve_app
from voicepilot.core.exceptions import ExecutorError
from voicepilot.executor.base import BaseAction
from voicepilot.parser.intent import ParsedCommand

logger = logging.getLogger(__name__)


class AppLauncherAction(BaseAction):
    """Opens, closes, or switches to an application."""

    handles = ["open_application", "close_application", "switch_to_application"]

    def __init__(self, app_aliases: dict[str, str]) -> None:
        """
        Parameters
        ----------
        app_aliases:
            Mapping of spoken app name → executable name.
            Loaded from config.apps.aliases.
        """
        self.app_aliases = {k.lower(): v for k, v in app_aliases.items()}

    # ------------------------------------------------------------------
    # BaseAction
    # ------------------------------------------------------------------

    def execute(self, command: ParsedCommand) -> None:
        intent = command.intent_name
        app_slot = command.get_slot("app", "").strip().lower()

        if not app_slot:
            raise ExecutorError("No application name provided")

        executable = self._resolve(app_slot)

        if intent == "open_application":
            self._open(executable, app_slot)
        elif intent == "close_application":
            self._close(executable, app_slot)
        elif intent == "switch_to_application":
            self._focus(executable, app_slot)

    # ------------------------------------------------------------------
    # Open
    # ------------------------------------------------------------------

    def _open(self, executable: str, spoken_name: str) -> None:
        if not shutil.which(executable):
            raise ExecutorError(
                f"Application {spoken_name!r} not found on PATH (tried: {executable!r}). "
                "Is it installed?"
            )

        logger.info("Launching application: %s", executable)
        subprocess.Popen(
            [executable],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def _close(self, executable: str, spoken_name: str) -> None:
        """Gracefully terminate all processes matching the executable name."""
        killed: list[int] = []

        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                proc_name = (proc.info.get("name") or "").lower()
                proc_exe = (proc.info.get("exe") or "").lower()
                if executable.lower() in proc_name or executable.lower() in proc_exe:
                    proc.terminate()
                    killed.append(proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if not killed:
            raise ExecutorError(
                f"No running process found for {spoken_name!r} (tried: {executable!r})"
            )

        logger.info("Terminated %d process(es) for %r: %s", len(killed), executable, killed)

        # Give processes 2 seconds to exit gracefully; force-kill stragglers
        time.sleep(2)
        for pid in killed:
            try:
                proc = psutil.Process(pid)
                if proc.is_running():
                    proc.kill()
                    logger.warning("Force-killed PID %d", pid)
            except psutil.NoSuchProcess:
                pass

    # ------------------------------------------------------------------
    # Focus / switch
    # ------------------------------------------------------------------

    def _focus(self, executable: str, spoken_name: str) -> None:
        """Bring a running application's window to the foreground."""
        if shutil.which("wmctrl"):
            result = subprocess.run(
                ["wmctrl", "-a", executable],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info("Focused window for %r via wmctrl", executable)
                return
            # wmctrl may not find by executable; try window title
            result2 = subprocess.run(
                ["wmctrl", "-a", spoken_name],
                capture_output=True,
                text=True,
            )
            if result2.returncode == 0:
                logger.info("Focused window by title %r", spoken_name)
                return

        logger.warning(
            "wmctrl not found or failed — cannot focus %r", executable
        )
        # Fall back to opening the app
        self._open(executable, spoken_name)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _resolve(self, spoken_name: str) -> str:
        """
        Map a spoken name to an executable.

        The configured alias wins when the binary it names is installed. When
        it is not — the common case when a config written on one distribution
        is used on another, e.g. "files" → nautilus on a Mint box that ships
        nemo — fall back to whatever equivalent this desktop actually has.
        """
        alias = self.app_aliases.get(spoken_name)

        if alias and shutil.which(alias):
            return alias

        installed = resolve_app(spoken_name)
        if installed:
            if alias and alias != installed:
                logger.info(
                    "Configured executable %r for %r is not installed — using %r",
                    alias,
                    spoken_name,
                    installed,
                )
            return installed

        # Nothing known is installed; keep the configured alias so the error
        # message names what the user actually asked for.
        return alias or spoken_name
