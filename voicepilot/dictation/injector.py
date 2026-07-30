"""
Text injector — types transcribed text into the currently focused application.

Injection strategies (in preference order):
  1. xdotool type  (X11, most reliable)
  2. Clipboard paste via xclip/xsel + Ctrl+V (fallback for special characters)

The injector is used exclusively in dictation mode.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time

from voicepilot.core.exceptions import ExecutorError

logger = logging.getLogger(__name__)


class TextInjector:
    """
    Injects text into the currently focused window.

    Parameters
    ----------
    method:
        "auto"      — try xdotool, fall back to clipboard
        "xdotool"   — use xdotool type
        "clipboard" — paste via clipboard
    typing_delay_ms:
        Delay between keystrokes in milliseconds (0 = instant).
    """

    def __init__(self, method: str = "auto", typing_delay_ms: int = 0) -> None:
        self.method = method
        self.typing_delay_ms = typing_delay_ms
        self._resolved_method: str | None = None

    def inject(self, text: str) -> None:
        """Inject *text* into the focused application."""
        if not text:
            return

        method = self._resolve_method()

        logger.debug("Injecting %d chars via %s", len(text), method)

        if method == "xdotool":
            self._inject_xdotool(text)
        elif method == "ydotool":
            self._inject_ydotool(text)
        elif method == "clipboard":
            self._inject_clipboard(text)
        else:
            raise ExecutorError(
                f"Unknown text injection method {method!r}. "
                "Expected one of: xdotool, ydotool, clipboard, auto."
            )

    # ------------------------------------------------------------------
    # Strategy implementations
    # ------------------------------------------------------------------

    def _inject_xdotool(self, text: str) -> None:
        args = ["xdotool", "type", "--clearmodifiers"]
        if self.typing_delay_ms > 0:
            args += ["--delay", str(self.typing_delay_ms)]
        args += ["--", text]

        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(
                "xdotool type failed (rc=%d): %s — falling back to clipboard",
                result.returncode,
                result.stderr.strip(),
            )
            self._inject_clipboard(text)

    def _inject_ydotool(self, text: str) -> None:
        """Type via ydotool (Wayland). Requires access to /dev/uinput."""
        args = ["ydotool", "type"]
        if self.typing_delay_ms > 0:
            args += ["--key-delay", str(self.typing_delay_ms)]
        args += ["--", text]

        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(
                "ydotool type failed (rc=%d): %s — falling back to clipboard",
                result.returncode,
                result.stderr.strip(),
            )
            self._inject_clipboard(text)

    def _inject_clipboard(self, text: str) -> None:
        """Copy text to clipboard, then send Ctrl+V."""
        original = self._clipboard_get()
        try:
            self._clipboard_set(text)
            time.sleep(0.05)  # Let clipboard settle
            self._send_paste()
            time.sleep(0.05)
        finally:
            # Restore original clipboard content
            if original is not None:
                time.sleep(0.1)
                self._clipboard_set(original)

    # Clipboard helpers, in preference order. wl-clipboard works on Wayland,
    # xclip/xsel on X11; whichever is installed is used.
    _CLIPBOARD_WRITERS = [
        ("wl-copy", ["wl-copy"]),
        ("xclip", ["xclip", "-selection", "clipboard"]),
        ("xsel", ["xsel", "--clipboard", "--input"]),
    ]
    _CLIPBOARD_READERS = [
        ("wl-paste", ["wl-paste", "--no-newline"]),
        ("xclip", ["xclip", "-selection", "clipboard", "-o"]),
        ("xsel", ["xsel", "--clipboard", "--output"]),
    ]

    def _clipboard_set(self, text: str) -> None:
        for binary, args in self._CLIPBOARD_WRITERS:
            if shutil.which(binary):
                proc = subprocess.Popen(args, stdin=subprocess.PIPE)
                proc.communicate(input=text.encode())
                return

        try:
            import pyperclip  # type: ignore[import]
            pyperclip.copy(text)
        except Exception as exc:
            raise ExecutorError(
                "Cannot set clipboard: install xclip (X11) or wl-clipboard (Wayland)"
            ) from exc

    def _clipboard_get(self) -> str | None:
        try:
            for binary, args in self._CLIPBOARD_READERS:
                if shutil.which(binary):
                    result = subprocess.run(args, capture_output=True, text=True)
                    return result.stdout if result.returncode == 0 else None

            import pyperclip  # type: ignore[import]
            return pyperclip.paste()
        except Exception:
            return None

    def _send_paste(self) -> None:
        from pynput.keyboard import Controller, Key  # type: ignore[import]

        kb = Controller()
        with kb.pressed(Key.ctrl):
            kb.press("v")
            kb.release("v")

    # ------------------------------------------------------------------
    # Method resolution
    # ------------------------------------------------------------------

    def _resolve_method(self) -> str:
        if self._resolved_method:
            return self._resolved_method

        if self.method != "auto":
            self._resolved_method = self.method
            return self.method

        session_type = os.environ.get("XDG_SESSION_TYPE", "x11").lower()

        if session_type == "wayland":
            # ydotool can work on Wayland (requires root or uinput group)
            if shutil.which("ydotool"):
                self._resolved_method = "ydotool"
            else:
                self._resolved_method = "clipboard"
        else:
            if shutil.which("xdotool"):
                self._resolved_method = "xdotool"
            else:
                self._resolved_method = "clipboard"

        logger.info("Text injection method resolved: %s", self._resolved_method)
        return self._resolved_method
