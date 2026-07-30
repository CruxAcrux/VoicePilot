"""
Logging configuration for VoicePilot.

Call `setup_logging()` once at application startup.
After that, every module can use `logging.getLogger(__name__)`.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

_FORMATTER_VERBOSE = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)-40s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_FORMATTER_SIMPLE = logging.Formatter(
    fmt="%(levelname)-8s %(name)s: %(message)s",
)


def setup_logging(
    level: str = "INFO",
    log_dir: Path | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
) -> None:
    """
    Configure the root logger for VoicePilot.

    Parameters
    ----------
    level:
        Logging level string — "DEBUG", "INFO", "WARNING", "ERROR".
    log_dir:
        Directory where rotating log files are written.
        If None, file logging is skipped.
    max_bytes:
        Maximum size of each log file before rotation.
    backup_count:
        Number of rotated log files to keep.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Remove any handlers already attached (e.g. from pytest)
    root.handlers.clear()

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(_FORMATTER_SIMPLE)
    root.addHandler(console_handler)

    # --- Rotating file handler ---
    if log_dir is not None:
        log_dir = Path(log_dir).expanduser()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "voicepilot.log"

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(_FORMATTER_VERBOSE)
        root.addHandler(file_handler)

    # Suppress overly chatty third-party loggers
    _silence = [
        "faster_whisper",
        "urllib3",
        "PIL",
    ]
    for name in _silence:
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger("voicepilot").info(
        "Logging initialised — level=%s, log_dir=%s", level, log_dir
    )
