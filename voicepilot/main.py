"""
VoicePilot entry point.

Usage:
    python -m voicepilot
    voicepilot                    # after installation
    voicepilot --no-ui            # CLI/headless mode
    voicepilot --config PATH      # custom config file
    voicepilot --debug            # verbose logging
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="voicepilot",
        description="VoicePilot — voice-controlled Linux desktop assistant",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to user configuration file (default: ~/.config/voicepilot/config.toml)",
    )
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Run in headless mode without the Qt GUI",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="VoicePilot 0.1.0",
    )
    return parser.parse_args()


def main() -> None:
    """Application entry point."""
    args = _parse_args()

    # --- Load configuration first ---
    from voicepilot.core.config import load_config
    from voicepilot.core.logging import setup_logging

    config = load_config(user_config_path=args.config)

    log_level = "DEBUG" if args.debug else config.logging.level
    setup_logging(
        level=log_level,
        log_dir=config.app.log_dir,
        max_bytes=config.logging.max_file_size_mb * 1024 * 1024,
        backup_count=config.logging.backup_count,
    )

    import logging
    logger = logging.getLogger(__name__)
    logger.info("VoicePilot starting (version=%s)", config.app.version)

    # --- Instantiate the application logic ---
    from voicepilot.app import VoicePilotApp

    vp_app = VoicePilotApp(config)

    # --- Headless mode (no Qt) ---
    if args.no_ui:
        _run_headless(vp_app, logger)
        return

    # --- GUI mode ---
    _run_gui(vp_app, config, logger)


def _run_headless(vp_app, logger) -> None:
    """Run VoicePilot without a Qt UI — useful for testing and server use."""
    import time

    logger.info("Running in headless mode — Ctrl+C to quit")
    vp_app.start()

    def _shutdown(sig, frame):
        logger.info("Shutting down…")
        vp_app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        vp_app.stop()


def _check_gui_prerequisites(logger) -> None:
    """
    Fail with an actionable message rather than a Qt abort.

    When Qt cannot load its "xcb" platform plugin it calls abort(), which
    produces a core dump and a message that does not say which package is
    missing. Checking first turns that into an instruction the user can act on.
    """
    import ctypes.util
    import os

    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        logger.error("No graphical display detected (DISPLAY and WAYLAND_DISPLAY are unset).")
        logger.error("Run VoicePilot in headless mode instead:  voicepilot --no-ui")
        sys.exit(1)

    # Qt 6.5+ requires libxcb-cursor at runtime; the PyQt6 wheel does not
    # bundle it and most desktops do not install it by default.
    if os.environ.get("DISPLAY") and ctypes.util.find_library("xcb-cursor") is None:
        logger.error(
            "The Qt 'xcb' platform plugin needs libxcb-cursor0, which is not installed."
        )
        logger.error("Install it with:")
        logger.error("  sudo apt install libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0")
        logger.error("Or run without the GUI:  voicepilot --no-ui")
        sys.exit(1)


def _run_gui(vp_app, config, logger) -> None:
    """Run VoicePilot with the full PyQt6 UI."""
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        logger.error("PyQt6 is not installed. Run: pip install PyQt6")
        sys.exit(1)

    _check_gui_prerequisites(logger)

    # Qt requires this before any QWidget is created
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("VoicePilot")
    qt_app.setApplicationVersion("0.1.0")
    qt_app.setOrganizationName("VoicePilot")

    # Prevent app from quitting when last window is closed (tray app)
    qt_app.setQuitOnLastWindowClosed(False)

    # Check that system tray is available
    from PyQt6.QtWidgets import QSystemTrayIcon
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.error("System tray is not available on this desktop environment")
        sys.exit(1)

    # Apply stylesheet
    _apply_stylesheet(qt_app, config.ui.theme)

    # Build main window (owns tray + overlay)
    from voicepilot.ui.main_window import MainWindow

    # Held on the QApplication rather than a local: the window owns the tray
    # icon and overlay, and dropping the last reference would take them with it.
    qt_app.voicepilot_window = MainWindow(  # type: ignore[attr-defined]
        config=config,
        on_dictation_toggle=vp_app.dictation_mode.toggle,
        on_quit=vp_app.stop,
    )

    # Start audio processing
    vp_app.start()

    logger.info("Qt event loop starting")
    exit_code = qt_app.exec()
    logger.info("Qt event loop exited (code=%d)", exit_code)
    vp_app.stop()
    sys.exit(exit_code)


def _apply_stylesheet(app, theme: str) -> None:
    """Apply a minimal dark or light stylesheet."""
    if theme == "dark":
        app.setStyleSheet("""
            QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: "Segoe UI", "Ubuntu", sans-serif;
            }
            QDialog {
                background-color: #1e1e2e;
            }
            QTabWidget::pane {
                border: 1px solid #313244;
            }
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                color: #cdd6f4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #45475a;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #89b4fa;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QCheckBox {
                color: #cdd6f4;
            }
        """)
    else:
        # Light theme — rely on system defaults
        app.setStyleSheet("")


if __name__ == "__main__":
    main()
