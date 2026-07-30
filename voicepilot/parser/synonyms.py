"""
Synonym expansion for the command parser.

Maps alternative spoken forms → canonical form so that grammar patterns
stay clean and do not need to enumerate every possible phrasing.

Example:
    "launch firefox"  → normalised to "open firefox"
    "quit firefox"    → normalised to "close firefox"
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Verb synonyms — map any of these to the canonical verb
# ---------------------------------------------------------------------------

VERB_SYNONYMS: dict[str, list[str]] = {
    "open": [
        "launch", "start", "run", "load", "bring up", "pull up",
        "fire up", "boot", "open up", "execute",
    ],
    "close": [
        "quit", "exit", "kill", "shut", "shut down", "terminate",
        "stop", "end", "close down", "kill off",
    ],
    "create": [
        "make", "new", "add", "create new", "generate", "build",
        "touch", "write",
    ],
    "delete": [
        "remove", "erase", "trash", "get rid of", "wipe", "destroy",
        "drop", "eliminate",
    ],
    "search": [
        "find", "look for", "locate", "search for", "where is",
        "show me", "look up",
    ],
    "go to": [
        "navigate to", "jump to", "move to", "switch to", "goto",
    ],
    "rename": [
        "change name", "rename to", "call it", "call this",
    ],
    "save": [
        "write", "store", "keep",
    ],
    "copy": [
        "duplicate", "clone",
    ],
    "paste": [
        "insert", "put",
    ],
    "undo": [
        "revert", "go back",
    ],
    "redo": [
        "repeat",
    ],
    "minimize": [
        "minimise", "hide", "shrink",
    ],
    "maximize": [
        "maximise", "fullscreen", "full screen", "expand",
    ],
}

# ---------------------------------------------------------------------------
# Application name normalisations
# ---------------------------------------------------------------------------

APP_SYNONYMS: dict[str, list[str]] = {
    "firefox": ["fire fox", "mozilla firefox", "mozilla"],
    "chrome": ["google chrome", "google-chrome", "chromium"],
    "terminal": ["console", "bash", "shell", "command line", "gnome terminal", "term"],
    "vs code": ["visual studio code", "vscode", "code editor"],
    "files": ["file manager", "nautilus", "file browser"],
    "slack": ["slack messenger"],
    "discord": ["discord app"],
}

# ---------------------------------------------------------------------------
# Folder name normalisations
# ---------------------------------------------------------------------------

FOLDER_SYNONYMS: dict[str, list[str]] = {
    "downloads": ["download"],
    "documents": ["docs", "document"],
    "pictures": ["photos", "images", "picture", "photo"],
    "desktop": ["my desktop"],
    "home": ["home folder", "home directory", "my home"],
    "projects": ["project"],
}

# ---------------------------------------------------------------------------
# Build reverse lookup tables
# ---------------------------------------------------------------------------

def _build_reverse(mapping: dict[str, list[str]]) -> dict[str, str]:
    """Build synonym → canonical form reverse lookup."""
    rev: dict[str, str] = {}
    for canonical, synonyms in mapping.items():
        for syn in synonyms:
            rev[syn.lower()] = canonical
    return rev


_VERB_REV = _build_reverse(VERB_SYNONYMS)
_APP_REV = _build_reverse(APP_SYNONYMS)
_FOLDER_REV = _build_reverse(FOLDER_SYNONYMS)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalise_text(text: str) -> str:
    """
    Expand synonyms in *text* to canonical forms.

    Applied in order: verbs → app names → folder names.
    Text is lowercased and extra whitespace is collapsed.
    """
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)

    # Verb normalisation (longest match first to avoid partial replacements)
    text = _replace_synonyms(text, _VERB_REV)
    text = _replace_synonyms(text, _APP_REV)
    text = _replace_synonyms(text, _FOLDER_REV)

    return text


def _replace_synonyms(text: str, rev_map: dict[str, str]) -> str:
    """Replace all occurrences of synonym phrases with their canonical forms."""
    # Sort by length descending so longer phrases match before shorter subsets
    for synonym in sorted(rev_map, key=len, reverse=True):
        canonical = rev_map[synonym]
        # Word-boundary aware replacement
        pattern = r"\b" + re.escape(synonym) + r"\b"
        text = re.sub(pattern, canonical, text, flags=re.IGNORECASE)
    return text


def canonical_app(name: str) -> str:
    """Return the canonical app name for a given spoken name."""
    return _APP_REV.get(name.lower(), name.lower())


def canonical_folder(name: str) -> str:
    """Return the canonical folder name for a given spoken folder name."""
    return _FOLDER_REV.get(name.lower(), name.lower())
