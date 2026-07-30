"""
Configuration management for VoicePilot.

Loads configuration from (in order of precedence, highest last):
  1. Bundled defaults  (config/default.toml inside the package)
  2. System-wide config  (/etc/voicepilot/config.toml)
  3. User config  (~/.config/voicepilot/config.toml)

All values are merged; later sources override earlier ones.
The result is validated via Pydantic and exposed as a typed `AppConfig` object.
"""

from __future__ import annotations

import copy
import logging
import sys
from pathlib import Path
from typing import Any

# tomllib is stdlib in Python 3.11+; use tomli as a backport for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        # Last-resort fallback using the 'toml' package (read-only shim)
        import toml as _toml  # type: ignore[import]

        class _TomllibShim:
            @staticmethod
            def load(fp):
                return _toml.loads(fp.read().decode())

        tomllib = _TomllibShim()  # type: ignore[assignment]

from pydantic import BaseModel, Field, field_validator

from voicepilot.core.exceptions import ConfigValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models — one per TOML section
# ---------------------------------------------------------------------------


class AppSection(BaseModel):
    name: str = "VoicePilot"
    version: str = "0.1.0"
    data_dir: Path = Path("~/.local/share/voicepilot")
    log_dir: Path = Path("~/.local/share/voicepilot/logs")

    @field_validator("data_dir", "log_dir", mode="before")
    @classmethod
    def expand(cls, v: Any) -> Path:
        return Path(str(v)).expanduser()


class SpeechSection(BaseModel):
    activation_mode: str = "wake_word"
    wake_word: str = "hey jarvis"
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    language: str = "sv"
    microphone_index: int | None = None
    sample_rate: int = 16000
    vad_threshold: float = 0.5
    silence_duration: float = 1.2
    max_recording_seconds: int = 30


class ConfirmationSection(BaseModel):
    timeout_seconds: int = 10
    high_risk_phrase: str = "bekräfta radera"
    medium_risk_phrase: str = "bekräfta"
    cancel_phrase: str = "avbryt"


class DictationSection(BaseModel):
    injection_method: str = "auto"
    typing_delay_ms: int = 0


class UISection(BaseModel):
    overlay_position: str = "top-right"
    overlay_opacity: float = 0.92
    theme: str = "dark"
    show_transcription: bool = True
    font_size: int = 13


class FeedbackSection(BaseModel):
    tts_enabled: bool = True
    tts_engine: str = "espeak"
    tts_rate: int = 170
    tts_volume: float = 0.9
    sound_effects: bool = True


class LoggingSection(BaseModel):
    level: str = "INFO"
    max_file_size_mb: int = 10
    backup_count: int = 3
    log_commands: bool = True


class SecuritySection(BaseModel):
    shell_command_whitelist: list[str] = Field(
        default_factory=lambda: [
            "loginctl",
            "systemctl",
            "xdg-open",
            "wmctrl",
            "xdotool",
            "locate",
            "find",
        ]
    )
    always_confirm_shell: bool = True


class VSCodeSection(BaseModel):
    enabled: bool = True
    binary: str = "code"
    projects_dir: Path = Path("~/projects")

    @field_validator("projects_dir", mode="before")
    @classmethod
    def expand(cls, v: Any) -> Path:
        return Path(str(v)).expanduser()


class AppsSection(BaseModel):
    aliases: dict[str, str] = Field(
        default_factory=lambda: {
            "firefox": "firefox",
            "chrome": "google-chrome",
            "chromium": "chromium-browser",
            "terminal": "gnome-terminal",
            "files": "nautilus",
            "file manager": "nautilus",
            "vs code": "code",
            "vscode": "code",
            "code": "code",
            "slack": "slack",
            "discord": "discord",
            "spotify": "spotify",
            "settings": "gnome-control-center",
            "calculator": "gnome-calculator",
            "text editor": "gedit",
        }
    )


class FoldersSection(BaseModel):
    aliases: dict[str, str] = Field(
        default_factory=lambda: {
            "home": "~",
            "desktop": "~/Desktop",
            "downloads": "~/Downloads",
            "documents": "~/Documents",
            "pictures": "~/Pictures",
            "music": "~/Music",
            "videos": "~/Videos",
            "projects": "~/projects",
        }
    )


class AppConfig(BaseModel):
    """Root configuration object. Access via `config.speech.whisper_model` etc."""

    app: AppSection = Field(default_factory=AppSection)
    speech: SpeechSection = Field(default_factory=SpeechSection)
    confirmation: ConfirmationSection = Field(default_factory=ConfirmationSection)
    dictation: DictationSection = Field(default_factory=DictationSection)
    ui: UISection = Field(default_factory=UISection)
    feedback: FeedbackSection = Field(default_factory=FeedbackSection)
    logging: LoggingSection = Field(default_factory=LoggingSection)
    security: SecuritySection = Field(default_factory=SecuritySection)
    vscode: VSCodeSection = Field(default_factory=VSCodeSection)
    apps: AppsSection = Field(default_factory=AppsSection)
    folders: FoldersSection = Field(default_factory=FoldersSection)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _load_toml(path: Path, required: bool = False) -> dict[str, Any]:
    """
    Load a TOML file, returning an empty dict if it does not exist.

    A malformed *user* config is a warning — the app still starts on defaults.
    A malformed *bundled* config is a packaging bug that would silently discard
    every default, so it is raised rather than swallowed.
    """
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as exc:
        if required:
            raise ConfigValidationError(
                f"Bundled default config at {path} is invalid: {exc}"
            ) from exc
        logger.warning("Could not load config from %s: %s", path, exc)
        return {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base* (non-destructive)."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _default_config_path() -> Path:
    """
    Return the path to the bundled default.toml.

    Checked in order: inside the installed package, then the repository layout
    (``<repo>/config/default.toml``) which is what an editable install sees,
    then the system location. The repo path is returned as a fallback so the
    error message names the expected location when nothing is found.
    """
    package_root = Path(__file__).resolve().parent.parent
    repo_config = package_root.parent / "config" / "default.toml"

    candidates = [
        package_root / "config" / "default.toml",
        repo_config,
        Path("/usr/share/voicepilot/config/default.toml"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return repo_config


def load_config(user_config_path: Path | None = None) -> AppConfig:
    """
    Load and merge all configuration sources.

    Parameters
    ----------
    user_config_path:
        Optional explicit path to a user config file.
        Defaults to ``~/.config/voicepilot/config.toml``.

    Returns
    -------
    AppConfig
        Fully merged and validated configuration object.
    """
    merged: dict[str, Any] = {}

    # 1. Bundled defaults
    defaults = _load_toml(_default_config_path(), required=True)
    merged = _deep_merge(merged, defaults)

    # 2. System-wide config
    system_cfg = _load_toml(Path("/etc/voicepilot/config.toml"))
    merged = _deep_merge(merged, system_cfg)

    # 3. User config
    if user_config_path is None:
        user_config_path = Path("~/.config/voicepilot/config.toml").expanduser()
    user_cfg = _load_toml(user_config_path)
    merged = _deep_merge(merged, user_cfg)

    logger.debug("Merged config keys: %s", list(merged.keys()))

    return AppConfig.model_validate(merged)


# ---------------------------------------------------------------------------
# User config persistence
# ---------------------------------------------------------------------------

def save_user_config(config: AppConfig, path: Path | None = None) -> None:
    """Persist the current configuration to the user config file."""
    import toml  # runtime import — only needed when saving

    if path is None:
        path = Path("~/.config/voicepilot/config.toml").expanduser()

    path.parent.mkdir(parents=True, exist_ok=True)

    # Serialise via Pydantic then write as TOML
    data = config.model_dump(mode="python")

    # Convert Path objects to strings for TOML serialisation
    def _stringify_paths(obj: Any) -> Any:
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, dict):
            return {k: _stringify_paths(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_stringify_paths(i) for i in obj]
        return obj

    data = _stringify_paths(data)

    with open(path, "w", encoding="utf-8") as f:
        toml.dump(data, f)

    logger.info("Config saved to %s", path)
