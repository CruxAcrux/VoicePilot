"""Custom exceptions for VoicePilot."""

from __future__ import annotations


class VoicePilotError(Exception):
    """Base exception for all VoicePilot errors."""


# --- Speech ---

class SpeechEngineError(VoicePilotError):
    """Raised when the speech engine fails to initialise or process audio."""


class MicrophoneError(SpeechEngineError):
    """Raised when the microphone cannot be opened or read."""


class TranscriptionError(SpeechEngineError):
    """Raised when faster-whisper fails to transcribe audio."""


class WakeWordError(SpeechEngineError):
    """Raised when the wake-word detector encounters an unrecoverable error."""


class VADError(SpeechEngineError):
    """Raised when voice activity detection fails."""


# --- Parser ---

class ParserError(VoicePilotError):
    """Raised when the command parser cannot process input."""


class UnknownCommandError(ParserError):
    """Raised when no intent matches the spoken command."""

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__(f"Unknown command: {text!r}")


# --- Executor ---

class ExecutorError(VoicePilotError):
    """Raised when an action fails to execute."""


class ActionNotFoundError(ExecutorError):
    """Raised when a registered action cannot be located."""


class PermissionDeniedError(ExecutorError):
    """Raised when a command is blocked by the security policy."""


class ShellCommandBlockedError(PermissionDeniedError):
    """Raised when a shell command is not on the whitelist."""

    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__(f"Shell command not on whitelist: {command!r}")


# --- Confirmation ---

class ConfirmationError(VoicePilotError):
    """Raised when a confirmation flow encounters an error."""


class ConfirmationTimeoutError(ConfirmationError):
    """Raised when the user does not confirm within the allowed window."""


class ConfirmationCancelledError(ConfirmationError):
    """Raised when the user explicitly cancels a pending confirmation."""


# --- Settings ---

class SettingsError(VoicePilotError):
    """Raised when settings cannot be loaded or saved."""


class ConfigValidationError(SettingsError):
    """Raised when the configuration file contains invalid values."""


# --- UI ---

class UIError(VoicePilotError):
    """Raised when the UI layer encounters an unrecoverable error."""


# --- Plugins ---

class PluginError(VoicePilotError):
    """Raised when a plugin fails to load or execute."""


class PluginNotFoundError(PluginError):
    """Raised when a named plugin does not exist."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Plugin not found: {name!r}")
