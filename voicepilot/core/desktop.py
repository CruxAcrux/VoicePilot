"""
Desktop environment detection and executable resolution.

VoicePilot targets "Linux desktop" rather than one specific distribution, but
the concrete binaries behind a spoken name differ between them: "files" is
``nautilus`` on Ubuntu/GNOME, ``nemo`` on Linux Mint Cinnamon, ``thunar`` on
XFCE and ``dolphin`` on KDE. Hard-coding one set makes the app work on the
machine it was written on and fail everywhere else.

This module resolves a spoken name to the first candidate that is actually
installed, preferring the ones native to the running desktop. Config aliases
still win when the user sets them — see ``AppLauncherAction._resolve``.
"""

from __future__ import annotations

import logging
import os
import shutil

logger = logging.getLogger(__name__)


def detect_desktop() -> str:
    """
    Return the running desktop environment as a lowercase name.

    One of: "cinnamon", "gnome", "kde", "xfce", "mate", "lxqt", "unity",
    or "unknown".
    """
    # XDG_CURRENT_DESKTOP may be a colon-separated list and may carry a vendor
    # prefix, e.g. Mint reports "X-Cinnamon", Ubuntu reports "ubuntu:GNOME".
    raw = (
        os.environ.get("XDG_CURRENT_DESKTOP")
        or os.environ.get("DESKTOP_SESSION")
        or ""
    ).lower()

    for name in ("cinnamon", "gnome", "kde", "plasma", "xfce", "mate", "lxqt", "unity"):
        if name in raw:
            return "kde" if name == "plasma" else name

    return "unknown"


def is_wayland() -> bool:
    """True if the session is running on Wayland rather than X11."""
    if os.environ.get("WAYLAND_DISPLAY"):
        return True
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def which_first(candidates: list[str]) -> str | None:
    """Return the first candidate found on PATH, or None if none are."""
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    return None


# Desktop-native candidates, tried before the generic list below. Only entries
# that genuinely differ per desktop need to appear here.
_DESKTOP_PREFERRED: dict[str, dict[str, list[str]]] = {
    "cinnamon": {
        "files": ["nemo"],
        "terminal": ["gnome-terminal", "x-terminal-emulator"],
        "settings": ["cinnamon-settings"],
        "text editor": ["xed"],
    },
    "gnome": {
        "files": ["nautilus"],
        "terminal": ["gnome-terminal"],
        "settings": ["gnome-control-center"],
        "text editor": ["gedit", "gnome-text-editor"],
    },
    "mate": {
        "files": ["caja"],
        "terminal": ["mate-terminal"],
        "settings": ["mate-control-center"],
        "text editor": ["pluma"],
    },
    "xfce": {
        "files": ["thunar"],
        "terminal": ["xfce4-terminal"],
        "settings": ["xfce4-settings-manager"],
        "text editor": ["mousepad"],
    },
    "kde": {
        "files": ["dolphin"],
        "terminal": ["konsole"],
        "settings": ["systemsettings", "systemsettings5"],
        "text editor": ["kate", "kwrite"],
    },
}

# Generic fallbacks, tried after the desktop-native ones. Ordered by how
# commonly they are installed.
_GENERIC: dict[str, list[str]] = {
    "files": ["nautilus", "nemo", "thunar", "dolphin", "caja", "pcmanfm"],
    "file manager": ["nautilus", "nemo", "thunar", "dolphin", "caja", "pcmanfm"],
    "terminal": [
        "x-terminal-emulator",
        "gnome-terminal",
        "konsole",
        "xfce4-terminal",
        "mate-terminal",
        "alacritty",
        "kitty",
        "xterm",
    ],
    "settings": [
        "gnome-control-center",
        "cinnamon-settings",
        "systemsettings",
        "xfce4-settings-manager",
        "mate-control-center",
    ],
    "text editor": ["gedit", "xed", "kate", "mousepad", "pluma", "gnome-text-editor"],
    "calculator": ["gnome-calculator", "kcalc", "galculator", "mate-calc"],
    "browser": ["firefox", "google-chrome", "chromium", "chromium-browser", "x-www-browser"],
    "chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    "chromium": ["chromium", "chromium-browser", "google-chrome"],
    "firefox": ["firefox", "firefox-esr"],
}

# Aliases that mean the same thing as an entry above.
_SYNONYMS = {
    "file manager": "files",
    "web browser": "browser",
}


def resolve_app(spoken_name: str) -> str | None:
    """
    Resolve a spoken application name to an installed executable.

    Returns None if nothing matching is installed, so the caller can fall back
    to treating the spoken name as a literal executable.
    """
    key = _SYNONYMS.get(spoken_name.lower(), spoken_name.lower())
    desktop = detect_desktop()

    preferred = _DESKTOP_PREFERRED.get(desktop, {}).get(key, [])
    generic = _GENERIC.get(key, [])

    # Desktop-native first, then generic, without retrying the same binary.
    seen: set[str] = set()
    candidates = [c for c in preferred + generic if not (c in seen or seen.add(c))]

    if not candidates:
        return None

    found = which_first(candidates)
    if found:
        logger.debug("Resolved %r → %r (desktop=%s)", spoken_name, found, desktop)
    return found


# ---------------------------------------------------------------------------
# System tool chains — resolved at call time so a tool installed later works
# without restarting.
# ---------------------------------------------------------------------------

#: Screen lock commands, in preference order. Each is (binary, full argv).
LOCK_COMMANDS: list[tuple[str, list[str]]] = [
    ("loginctl", ["loginctl", "lock-session"]),
    ("cinnamon-screensaver-command", ["cinnamon-screensaver-command", "--lock"]),
    ("mate-screensaver-command", ["mate-screensaver-command", "--lock"]),
    ("xfce4-screensaver-command", ["xfce4-screensaver-command", "--lock"]),
    ("gnome-screensaver-command", ["gnome-screensaver-command", "--lock"]),
    ("qdbus", ["qdbus", "org.freedesktop.ScreenSaver", "/ScreenSaver", "Lock"]),
    ("xdg-screensaver", ["xdg-screensaver", "lock"]),
    ("dm-tool", ["dm-tool", "lock"]),
]

#: Interactive screenshot commands, in preference order.
SCREENSHOT_COMMANDS: list[tuple[str, list[str]]] = [
    ("gnome-screenshot", ["gnome-screenshot", "-i"]),
    ("xfce4-screenshooter", ["xfce4-screenshooter"]),
    ("spectacle", ["spectacle"]),
    ("mate-screenshot", ["mate-screenshot", "-i"]),
    ("flameshot", ["flameshot", "gui"]),
    ("scrot", ["scrot", "-s"]),
    ("import", ["import", "-window", "root", "screenshot.png"]),
]


def first_available(commands: list[tuple[str, list[str]]]) -> list[str] | None:
    """Return the argv of the first command whose binary is on PATH."""
    for binary, argv in commands:
        if shutil.which(binary):
            return argv
    return None
