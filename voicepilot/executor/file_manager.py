"""
File and folder management actions.

Handles:
  - open_folder
  - create_folder
  - create_file
  - delete_file
  - delete_folder
  - search_file

All file operations use pathlib and subprocess only.
No shell=True, no glob expansion from user input.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from voicepilot.core.exceptions import ExecutorError
from voicepilot.executor.base import BaseAction
from voicepilot.parser.intent import ParsedCommand

logger = logging.getLogger(__name__)


class FileManagerAction(BaseAction):
    """Handles file and folder creation, deletion, opening, and searching."""

    handles = [
        "open_folder",
        "create_folder",
        "create_file",
        "delete_file",
        "delete_folder",
        "search_file",
    ]

    def __init__(self, folder_aliases: dict[str, str]) -> None:
        """
        Parameters
        ----------
        folder_aliases:
            Mapping of spoken folder name → path (e.g. "downloads" → "~/Downloads").
        """
        self.folder_aliases = {k.lower(): Path(v).expanduser() for k, v in folder_aliases.items()}

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def execute(self, command: ParsedCommand) -> None:
        intent = command.intent_name

        if intent == "open_folder":
            self._open_folder(command.get_slot("folder", ""))
        elif intent == "create_folder":
            self._create_folder(command.get_slot("name", ""))
        elif intent == "create_file":
            self._create_file(command.get_slot("name", ""))
        elif intent == "delete_file":
            self._delete_file(command.get_slot("name", ""))
        elif intent == "delete_folder":
            self._delete_folder(command.get_slot("name", ""))
        elif intent == "search_file":
            self._search_file(command.get_slot("name", ""))

    # ------------------------------------------------------------------
    # Open folder
    # ------------------------------------------------------------------

    def _open_folder(self, spoken: str) -> None:
        spoken = spoken.strip().lower()
        if not spoken:
            # Open home directory
            path = Path.home()
        elif spoken in self.folder_aliases:
            path = self.folder_aliases[spoken]
        else:
            # Try treating it as a literal path
            path = Path(spoken).expanduser()

        if not path.exists():
            raise ExecutorError(f"Folder not found: {path}")

        logger.info("Opening folder: %s", path)
        subprocess.Popen(
            ["xdg-open", str(path)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # ------------------------------------------------------------------
    # Create folder
    # ------------------------------------------------------------------

    def _create_folder(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ExecutorError("Folder name cannot be empty")

        path = Path.cwd() / name

        if path.exists():
            raise ExecutorError(f"Folder already exists: {path}")

        path.mkdir(parents=True, exist_ok=False)
        logger.info("Created folder: %s", path)

    # ------------------------------------------------------------------
    # Create file
    # ------------------------------------------------------------------

    def _create_file(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ExecutorError("File name cannot be empty")

        path = Path.cwd() / name

        if path.exists():
            raise ExecutorError(f"File already exists: {path}")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        logger.info("Created file: %s", path)

    # ------------------------------------------------------------------
    # Delete file
    # ------------------------------------------------------------------

    def _delete_file(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ExecutorError("File name cannot be empty")

        path = self._resolve_file(name)

        if not path.exists():
            raise ExecutorError(f"File not found: {path}")

        if not path.is_file():
            raise ExecutorError(f"Not a file: {path}")

        path.unlink()
        logger.info("Deleted file: %s", path)

    # ------------------------------------------------------------------
    # Delete folder
    # ------------------------------------------------------------------

    def _delete_folder(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ExecutorError("Folder name cannot be empty")

        path = self._resolve_folder(name)

        if not path.exists():
            raise ExecutorError(f"Folder not found: {path}")

        if not path.is_dir():
            raise ExecutorError(f"Not a directory: {path}")

        shutil.rmtree(path)
        logger.info("Deleted folder: %s", path)

    # ------------------------------------------------------------------
    # Search file
    # ------------------------------------------------------------------

    def _search_file(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ExecutorError("Search term cannot be empty")

        logger.info("Searching for: %s", name)

        # Try 'locate' first (fast, uses index)
        if shutil.which("locate"):
            result = subprocess.run(
                ["locate", "-i", name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                results = result.stdout.strip().splitlines()
                logger.info("Found %d result(s) via locate", len(results))
                # Open file manager at the first result's directory
                first = Path(results[0])
                self._open_folder(str(first.parent))
                return

        # Fall back to 'find' in home directory
        result = subprocess.run(
            ["find", str(Path.home()), "-iname", f"*{name}*", "-maxdepth", "6"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            results = result.stdout.strip().splitlines()
            logger.info("Found %d result(s) via find", len(results))
            first = Path(results[0])
            self._open_folder(str(first.parent))
        else:
            raise ExecutorError(f"No files found matching: {name!r}")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _resolve_file(self, name: str) -> Path:
        """Attempt to locate a file by name in cwd, then home."""
        for base in [Path.cwd(), Path.home()]:
            candidate = base / name
            if candidate.exists():
                return candidate
        return Path.cwd() / name

    def _resolve_folder(self, name: str) -> Path:
        """Resolve a folder alias or literal name."""
        low = name.lower()
        if low in self.folder_aliases:
            return self.folder_aliases[low]
        for base in [Path.cwd(), Path.home()]:
            candidate = base / name
            if candidate.exists():
                return candidate
        return Path.cwd() / name
