"""
Main application window (invisible controller).

The MainWindow is not a visible window in the traditional sense.
It is the Qt QMainWindow that:
  - Owns the system tray icon
  - Owns the overlay HUD
  - Connects UI signals to application logic
  - Handles application-level keyboard shortcuts (push-to-talk)
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow

from voicepilot.core.config import AppConfig
from voicepilot.core.events import EventType, bus
from voicepilot.ui.overlay import OverlayHUD
from voicepilot.ui.settings import SettingsDialog
from voicepilot.ui.tray import SystemTray

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Invisible Qt main window that owns tray + overlay.

    Does not appear in the taskbar (Qt.Tool flag set on child widgets).
    The application's visible presence is entirely via the system tray
    icon and the overlay HUD.
    """

    def __init__(
        self,
        config: AppConfig,
        on_dictation_toggle: callable = None,
        on_quit: callable = None,
    ) -> None:
        super().__init__()
        self.config = config
        self._on_dictation_toggle = on_dictation_toggle or (lambda: None)
        self._on_quit = on_quit or (lambda: None)

        # Create sub-widgets
        self._tray = SystemTray(parent=self)
        self._overlay = OverlayHUD(
            position=config.ui.overlay_position,
            opacity=config.ui.overlay_opacity,
            font_size=config.ui.font_size,
        )

        # Connect tray signals
        self._tray.settings_requested.connect(self._open_settings)
        self._tray.quit_requested.connect(self._do_quit)
        self._tray.dictation_toggled.connect(self._toggle_dictation)

        # Show the tray icon
        self._tray.show()

        # Announce readiness
        QTimer.singleShot(500, self._on_ready)

        logger.info("MainWindow initialised")

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config, parent=None)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self, config: AppConfig) -> None:
        self.config = config
        bus.publish_type(
            EventType.UI_SETTINGS_CHANGED,
            data={"config": config},
            source="main_window",
        )
        logger.info("Settings updated")

    def _toggle_dictation(self) -> None:
        self._on_dictation_toggle()

    def _do_quit(self) -> None:
        self._on_quit()
        QApplication.quit()

    def _on_ready(self) -> None:
        self._tray.notify(
            "VoicePilot",
            "VoicePilot is running. Say 'Hey Pilot' to begin.",
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def show_overlay(self) -> None:
        self._overlay.show()

    def hide_overlay(self) -> None:
        self._overlay.hide()

    @property
    def tray(self) -> SystemTray:
        return self._tray

    @property
    def overlay(self) -> OverlayHUD:
        return self._overlay
