"""
Command grammar — defines every intent VoicePilot understands.

Each Intent has one or more pattern templates.  Slot names appear
in {braces}.  The interpreter will extract slot values from the
matched portion of the transcription.

Adding a new command is as simple as adding a new Intent entry here.
"""

from __future__ import annotations

from voicepilot.parser.intent import Intent, IntentCategory, RiskLevel

# ---------------------------------------------------------------------------
# Application control
# ---------------------------------------------------------------------------

INTENT_OPEN_APP = Intent(
    name="open_application",
    category=IntentCategory.APP_CONTROL,
    patterns=[
        "open {app}",
        "launch {app}",
        "start {app}",
    ],
    required_slots=["app"],
    risk=RiskLevel.LOW,
    description="Open an application by name.",
    examples=["open firefox", "launch terminal", "start vs code"],
)

INTENT_CLOSE_APP = Intent(
    name="close_application",
    category=IntentCategory.APP_CONTROL,
    patterns=[
        "close {app}",
        "quit {app}",
        "exit {app}",
    ],
    required_slots=["app"],
    risk=RiskLevel.MEDIUM,
    description="Close a running application.",
    examples=["close firefox", "quit terminal"],
)

INTENT_SWITCH_APP = Intent(
    name="switch_to_application",
    category=IntentCategory.APP_CONTROL,
    patterns=[
        "switch to {app}",
        "go to {app}",
        "focus {app}",
        "bring up {app}",
    ],
    required_slots=["app"],
    risk=RiskLevel.LOW,
    description="Switch focus to a running application.",
    examples=["switch to terminal", "focus vs code"],
)

# ---------------------------------------------------------------------------
# File management
# ---------------------------------------------------------------------------

INTENT_OPEN_FOLDER = Intent(
    name="open_folder",
    category=IntentCategory.FILE_MANAGEMENT,
    patterns=[
        "open {folder} folder",
        "open folder {folder}",
        "show folder {folder}",
        "go to folder {folder}",
    ],
    required_slots=["folder"],
    risk=RiskLevel.LOW,
    description="Open a folder in the file manager.",
    examples=["open downloads folder", "open documents"],
)

INTENT_CREATE_FOLDER = Intent(
    name="create_folder",
    category=IntentCategory.FILE_MANAGEMENT,
    patterns=[
        "create folder {name}",
        "create a folder called {name}",
        "make folder {name}",
        "new folder {name}",
    ],
    required_slots=["name"],
    risk=RiskLevel.LOW,
    description="Create a new folder.",
    examples=["create folder Projects", "make folder backups"],
)

INTENT_CREATE_FILE = Intent(
    name="create_file",
    category=IntentCategory.FILE_MANAGEMENT,
    patterns=[
        "create file {name}",
        "create a file called {name}",
        "make file {name}",
        "new file {name}",
        "touch {name}",
    ],
    required_slots=["name"],
    risk=RiskLevel.LOW,
    description="Create a new empty file.",
    examples=["create file notes.txt", "new file readme.md"],
)

INTENT_DELETE_FILE = Intent(
    name="delete_file",
    category=IntentCategory.FILE_MANAGEMENT,
    patterns=[
        "delete file {name}",
        "remove file {name}",
        "delete {name}",
    ],
    required_slots=["name"],
    risk=RiskLevel.MEDIUM,
    description="Delete a file.",
    examples=["delete file notes.txt"],
)

INTENT_DELETE_FOLDER = Intent(
    name="delete_folder",
    category=IntentCategory.FILE_MANAGEMENT,
    patterns=[
        "delete folder {name}",
        "remove folder {name}",
        "delete directory {name}",
    ],
    required_slots=["name"],
    risk=RiskLevel.HIGH,
    description="Delete a folder and all its contents.",
    examples=["delete folder old_projects"],
)

INTENT_SEARCH_FILE = Intent(
    name="search_file",
    category=IntentCategory.FILE_MANAGEMENT,
    patterns=[
        "search for {name}",
        "search {name}",
        "find {name}",
        "find file {name}",
        "locate {name}",
        "where is {name}",
    ],
    required_slots=["name"],
    risk=RiskLevel.LOW,
    description="Search for a file or folder.",
    examples=["search for report.pdf", "find notes.txt"],
)

# ---------------------------------------------------------------------------
# Window control
# ---------------------------------------------------------------------------

INTENT_MINIMIZE_WINDOW = Intent(
    name="minimize_window",
    category=IntentCategory.WINDOW_CONTROL,
    patterns=[
        "minimize window",
        "minimize {app}",
        "hide window",
        "minimize this",
    ],
    optional_slots=["app"],
    risk=RiskLevel.LOW,
    description="Minimize the current or named window.",
    examples=["minimize window", "minimize firefox"],
)

INTENT_MAXIMIZE_WINDOW = Intent(
    name="maximize_window",
    category=IntentCategory.WINDOW_CONTROL,
    patterns=[
        "maximize window",
        "maximize {app}",
        "full screen",
        "fullscreen",
    ],
    optional_slots=["app"],
    risk=RiskLevel.LOW,
    description="Maximize the current or named window.",
    examples=["maximize window", "fullscreen"],
)

INTENT_CLOSE_WINDOW = Intent(
    name="close_window",
    category=IntentCategory.WINDOW_CONTROL,
    patterns=[
        "close window",
        "close this window",
        "close current window",
    ],
    risk=RiskLevel.MEDIUM,
    description="Close the currently focused window.",
    examples=["close window"],
)

INTENT_MOVE_WORKSPACE_LEFT = Intent(
    name="move_workspace_left",
    category=IntentCategory.WINDOW_CONTROL,
    patterns=["workspace left", "go left", "previous workspace"],
    risk=RiskLevel.LOW,
    description="Switch to the workspace on the left.",
    examples=["workspace left"],
)

INTENT_MOVE_WORKSPACE_RIGHT = Intent(
    name="move_workspace_right",
    category=IntentCategory.WINDOW_CONTROL,
    patterns=["workspace right", "go right", "next workspace"],
    risk=RiskLevel.LOW,
    description="Switch to the workspace on the right.",
    examples=["workspace right"],
)

# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

INTENT_LOCK_COMPUTER = Intent(
    name="lock_computer",
    category=IntentCategory.SYSTEM,
    patterns=[
        "lock computer",
        "lock screen",
        "lock the screen",
        "lock my computer",
    ],
    risk=RiskLevel.MEDIUM,
    description="Lock the computer screen.",
    examples=["lock computer", "lock screen"],
)

INTENT_SHUTDOWN = Intent(
    name="shutdown",
    category=IntentCategory.SYSTEM,
    patterns=[
        "shutdown",
        "shut down",
        "power off",
        "turn off computer",
    ],
    risk=RiskLevel.HIGH,
    description="Shut down the computer.",
    examples=["shutdown", "power off"],
)

INTENT_RESTART = Intent(
    name="restart",
    category=IntentCategory.SYSTEM,
    patterns=[
        "restart",
        "reboot",
        "restart computer",
        "reboot computer",
    ],
    risk=RiskLevel.HIGH,
    description="Restart the computer.",
    examples=["restart", "reboot"],
)

INTENT_VOLUME_UP = Intent(
    name="volume_up",
    category=IntentCategory.SYSTEM,
    patterns=["volume up", "increase volume", "louder", "turn up volume"],
    risk=RiskLevel.LOW,
    description="Increase system volume.",
    examples=["volume up", "louder"],
)

INTENT_VOLUME_DOWN = Intent(
    name="volume_down",
    category=IntentCategory.SYSTEM,
    patterns=["volume down", "decrease volume", "quieter", "turn down volume"],
    risk=RiskLevel.LOW,
    description="Decrease system volume.",
    examples=["volume down", "quieter"],
)

INTENT_VOLUME_MUTE = Intent(
    name="volume_mute",
    category=IntentCategory.SYSTEM,
    patterns=["mute", "mute volume", "mute sound", "silence"],
    risk=RiskLevel.LOW,
    description="Mute system audio.",
    examples=["mute"],
)

INTENT_TAKE_SCREENSHOT = Intent(
    name="take_screenshot",
    category=IntentCategory.SYSTEM,
    patterns=[
        "take screenshot",
        "screenshot",
        "take a screenshot",
        "capture screen",
    ],
    risk=RiskLevel.LOW,
    description="Take a screenshot.",
    examples=["take screenshot", "screenshot"],
)

# ---------------------------------------------------------------------------
# Dictation
# ---------------------------------------------------------------------------

INTENT_START_DICTATION = Intent(
    name="start_dictation",
    category=IntentCategory.DICTATION,
    patterns=[
        "start dictation",
        "dictation mode",
        "begin dictation",
        "start typing",
    ],
    risk=RiskLevel.LOW,
    description="Enter dictation mode — spoken words are typed into the focused app.",
    examples=["start dictation", "dictation mode"],
)

INTENT_STOP_DICTATION = Intent(
    name="stop_dictation",
    category=IntentCategory.DICTATION,
    patterns=[
        "stop dictation",
        "end dictation",
        "exit dictation",
        "stop typing",
        "command mode",
    ],
    risk=RiskLevel.LOW,
    description="Exit dictation mode and return to command mode.",
    examples=["stop dictation", "command mode"],
)

# ---------------------------------------------------------------------------
# VS Code
# ---------------------------------------------------------------------------

INTENT_VSCODE_OPEN_PROJECT = Intent(
    name="vscode_open_project",
    category=IntentCategory.VSCODE,
    patterns=[
        "open project {project}",
        "open {project} project",
    ],
    required_slots=["project"],
    risk=RiskLevel.LOW,
    description="Open a project folder in VS Code.",
    examples=["open project VoicePilot"],
)

INTENT_VSCODE_OPEN_FILE = Intent(
    name="vscode_open_file",
    category=IntentCategory.VSCODE,
    patterns=[
        "open file {file}",
        "edit file {file}",
        "show file {file}",
    ],
    required_slots=["file"],
    risk=RiskLevel.LOW,
    description="Open a file in VS Code.",
    examples=["open file main.py", "open readme.md"],
)

INTENT_VSCODE_GO_TO_LINE = Intent(
    name="vscode_go_to_line",
    category=IntentCategory.VSCODE,
    patterns=[
        "go to line {line}",
        "line {line}",
        "jump to line {line}",
    ],
    required_slots=["line"],
    risk=RiskLevel.LOW,
    description="Navigate to a specific line number in VS Code.",
    examples=["go to line 150", "line 42"],
)

INTENT_VSCODE_SAVE_FILE = Intent(
    name="vscode_save_file",
    category=IntentCategory.VSCODE,
    patterns=["save file", "save", "save current file"],
    risk=RiskLevel.LOW,
    description="Save the current file in VS Code.",
    examples=["save file"],
)

INTENT_VSCODE_RUN_PROJECT = Intent(
    name="vscode_run_project",
    category=IntentCategory.VSCODE,
    patterns=["run project", "run code", "run", "execute project"],
    risk=RiskLevel.MEDIUM,
    description="Run the current project in VS Code.",
    examples=["run project"],
)

INTENT_VSCODE_OPEN_TERMINAL = Intent(
    name="vscode_open_terminal",
    category=IntentCategory.VSCODE,
    patterns=["open integrated terminal", "new terminal in code", "vscode terminal"],
    risk=RiskLevel.LOW,
    description="Open an integrated terminal in VS Code.",
    examples=["open terminal", "new terminal"],
)

INTENT_VSCODE_RENAME_SYMBOL = Intent(
    name="vscode_rename_symbol",
    category=IntentCategory.VSCODE,
    patterns=[
        "rename symbol",
        "rename variable",
        "rename selected",
        "rename this",
    ],
    risk=RiskLevel.MEDIUM,
    description="Trigger rename symbol refactoring in VS Code.",
    examples=["rename variable", "rename symbol"],
)

INTENT_VSCODE_COPY = Intent(
    name="vscode_copy",
    category=IntentCategory.VSCODE,
    patterns=["copy", "copy selected", "copy selection", "copy code"],
    risk=RiskLevel.LOW,
    description="Copy selected text in VS Code.",
    examples=["copy", "copy selected"],
)

INTENT_VSCODE_PASTE = Intent(
    name="vscode_paste",
    category=IntentCategory.VSCODE,
    patterns=["paste", "paste below", "paste code"],
    risk=RiskLevel.LOW,
    description="Paste clipboard content in VS Code.",
    examples=["paste", "paste below"],
)

# ---------------------------------------------------------------------------
# Master registry — the interpreter iterates this list
# ---------------------------------------------------------------------------

ALL_INTENTS: list[Intent] = [
    # Dictation first — these must be matched before any ambiguous command
    INTENT_START_DICTATION,
    INTENT_STOP_DICTATION,
    # App control
    INTENT_OPEN_APP,
    INTENT_CLOSE_APP,
    INTENT_SWITCH_APP,
    # File management
    INTENT_OPEN_FOLDER,
    INTENT_CREATE_FOLDER,
    INTENT_CREATE_FILE,
    INTENT_DELETE_FILE,
    INTENT_DELETE_FOLDER,
    INTENT_SEARCH_FILE,
    # Window control
    INTENT_MINIMIZE_WINDOW,
    INTENT_MAXIMIZE_WINDOW,
    INTENT_CLOSE_WINDOW,
    INTENT_MOVE_WORKSPACE_LEFT,
    INTENT_MOVE_WORKSPACE_RIGHT,
    # System
    INTENT_LOCK_COMPUTER,
    INTENT_SHUTDOWN,
    INTENT_RESTART,
    INTENT_VOLUME_UP,
    INTENT_VOLUME_DOWN,
    INTENT_VOLUME_MUTE,
    INTENT_TAKE_SCREENSHOT,
    # VS Code
    INTENT_VSCODE_OPEN_PROJECT,
    INTENT_VSCODE_OPEN_FILE,
    INTENT_VSCODE_GO_TO_LINE,
    INTENT_VSCODE_SAVE_FILE,
    INTENT_VSCODE_RUN_PROJECT,
    INTENT_VSCODE_OPEN_TERMINAL,
    INTENT_VSCODE_RENAME_SYMBOL,
    INTENT_VSCODE_COPY,
    INTENT_VSCODE_PASTE,
]
