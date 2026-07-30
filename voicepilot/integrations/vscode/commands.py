"""
VS Code integration — action handler for all vscode_* intents.

Uses two integration methods:
  1. `code` CLI subprocess — for opening projects/files
  2. pynput keyboard shortcuts — for editor navigation and actions

This covers ~90% of coding workflows without requiring a VS Code extension.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

from voicepilot.core.exceptions import ExecutorError
from voicepilot.executor.base import BaseAction
from voicepilot.executor.keyboard import KeyboardAction
from voicepilot.parser.intent import ParsedCommand

logger = logging.getLogger(__name__)


class VSCodeAction(BaseAction):
    """Handles all VS Code specific commands."""

    handles = [
        "vscode_open_project",
        "vscode_open_file",
        "vscode_go_to_line",
        "vscode_save_file",
        "vscode_run_project",
        "vscode_open_terminal",
        "vscode_rename_symbol",
        "vscode_copy",
        "vscode_paste",
    ]

    def __init__(
        self,
        projects_dir: Path | str = "~/Projects",
        code_binary: str = "code",
    ) -> None:
        self.projects_dir = Path(projects_dir).expanduser()
        self.code_binary = code_binary
        self._kb = KeyboardAction()

    def can_execute(self, command: ParsedCommand) -> bool:
        return shutil.which(self.code_binary) is not None

    def execute(self, command: ParsedCommand) -> None:
        intent = command.intent_name

        dispatch = {
            "vscode_open_project": self._open_project,
            "vscode_open_file": self._open_file,
            "vscode_go_to_line": self._go_to_line,
            "vscode_save_file": self._save_file,
            "vscode_run_project": self._run_project,
            "vscode_open_terminal": self._open_terminal,
            "vscode_rename_symbol": self._rename_symbol,
            "vscode_copy": self._copy,
            "vscode_paste": self._paste,
        }

        handler = dispatch.get(intent)
        if handler:
            handler(command)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _open_project(self, command: ParsedCommand) -> None:
        project = command.get_slot("project", "").strip()
        if not project:
            raise ExecutorError("No project name specified")

        path = self.projects_dir / project
        if not path.exists():
            # Try case-insensitive match
            matches = [
                d for d in self.projects_dir.iterdir()
                if d.is_dir() and d.name.lower() == project.lower()
            ]
            if matches:
                path = matches[0]
            else:
                raise ExecutorError(
                    f"Project {project!r} not found in {self.projects_dir}"
                )

        logger.info("Opening VS Code project: %s", path)
        subprocess.Popen(
            [self.code_binary, str(path)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _open_file(self, command: ParsedCommand) -> None:
        filename = command.get_slot("file", "").strip()
        if not filename:
            raise ExecutorError("No file name specified")

        # Search for the file in current directory and home
        for base in [Path.cwd(), Path.home()]:
            candidate = base / filename
            if candidate.exists():
                logger.info("Opening file in VS Code: %s", candidate)
                subprocess.Popen(
                    [self.code_binary, str(candidate)],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return

        # File not found locally — open by name (VS Code will handle it)
        logger.info("Opening %r in VS Code (path not resolved)", filename)
        subprocess.Popen(
            [self.code_binary, filename],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _go_to_line(self, command: ParsedCommand) -> None:
        line = command.get_slot("line", "").strip()
        if not line or not line.isdigit():
            raise ExecutorError(f"Invalid line number: {line!r}")

        logger.info("VS Code: go to line %s", line)
        # Ctrl+G opens the "go to line" dialog
        self._kb.hotkey("ctrl", "g")
        time.sleep(0.3)
        self._kb.type_text(line)
        time.sleep(0.1)
        self._kb.press_key("enter")

    def _save_file(self, command: ParsedCommand) -> None:
        logger.info("VS Code: save file")
        self._kb.hotkey("ctrl", "s")

    def _run_project(self, command: ParsedCommand) -> None:
        logger.info("VS Code: run project (Ctrl+F5)")
        self._kb.hotkey("ctrl", "f5")

    def _open_terminal(self, command: ParsedCommand) -> None:
        logger.info("VS Code: open terminal (Ctrl+`)")
        self._kb.hotkey("ctrl", "`")

    def _rename_symbol(self, command: ParsedCommand) -> None:
        logger.info("VS Code: rename symbol (F2)")
        self._kb.press_key("f2")

    def _copy(self, command: ParsedCommand) -> None:
        logger.info("VS Code: copy (Ctrl+C)")
        self._kb.hotkey("ctrl", "c")

    def _paste(self, command: ParsedCommand) -> None:
        logger.info("VS Code: paste (Ctrl+V)")
        self._kb.hotkey("ctrl", "v")
