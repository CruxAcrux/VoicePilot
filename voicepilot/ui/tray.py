"""
System tray icon and menu for VoicePilot.

Provides a persistent system tray icon that:
  - Shows current state (idle / listening / transcribing / dictating)
  - Provides right-click menu for common actions
  - Allows opening the settings dialog
  - Allows toggling dictation mode
  - Provides a quit action
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from voicepilot.core.events import Event, EventType, bus

logger = logging.getLogger(__name__)


def _make_icon(color: str, size: int = 22) -> QIcon:
    """Create a simple coloured circle icon for the tray."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(QColor(color).darker(120))
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.end()

    return QIcon(pixmap)


# State colours
_COLORS = {
    "IDLE": "#4a9eff",           # Blue
    "LISTENING_FOR_WAKE_WORD": "#4a9eff",
    "CAPTURING": "#2ecc71",      # Green — actively capturing
    "TRANSCRIBING": "#f39c12",   # Orange — processing
    "DICTATING": "#9b59b6",      # Purple — dictation mode
    "STOPPED": "#7f8c8d",        # Grey — not running
    "ERROR": "#e74c3c",          # Red
}


class SystemTray(QSystemTrayIcon):
    """
    VoicePilot system tray icon.

    Signals
    -------
    settings_requested:
        Emitted when the user clicks "Settings" in the tray menu.
    quit_requested:
        Emitted when the user clicks "Quit".
    dictation_toggled:
        Emitted when the user clicks "Toggle Dictation".
    """

    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    dictation_toggled = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._current_state = "STOPPED"
        self._dictation_active = False

        self._icons: dict[str, QIcon] = {
            state: _make_icon(color)
            for state, color in _COLORS.items()
        }

        self.setIcon(self._icons["STOPPED"])
        self.setToolTip("VoicePilot — Stopped")

        self._build_menu()
        self.activated.connect(self._on_activated)

        # Subscribe to engine state changes
        bus.on(EventType.UI_STATUS_UPDATE, self._on_status_update)
        bus.on(EventType.DICTATION_MODE_STARTED, self._on_dictation_started)
        bus.on(EventType.DICTATION_MODE_STOPPED, self._on_dictation_stopped)
        bus.on(EventType.APP_ERROR, self._on_error)

        logger.debug("SystemTray initialised")

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menu = QMenu()

        self._status_action = QAction("VoicePilot — Stopped", menu)
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)

        menu.addSeparator()

        self._dictation_action = QAction("Start Dictation", menu)
        self._dictation_action.triggered.connect(self.dictation_toggled.emit)
        menu.addAction(self._dictation_action)

        menu.addSeparator()

        settings_action = QAction("Settings…", menu)
        settings_action.triggered.connect(self.settings_requested.emit)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("Quit VoicePilot", menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    # ------------------------------------------------------------------
    # State updates (must run on Qt main thread)
    # ------------------------------------------------------------------

    def _on_status_update(self, event: Event) -> None:
        state = event.data.get("state", "IDLE")
        # Use Qt's thread-safe invocation
        QTimer.singleShot(0, lambda: self._apply_state(state))

    def _apply_state(self, state: str) -> None:
        self._current_state = state
        icon = self._icons.get(state, self._icons["IDLE"])
        self.setIcon(icon)

        label = state.replace("_", " ").title()
        if self._dictation_active:
            label = "Dictation Active"
        self.setToolTip(f"VoicePilot — {label}")
        self._status_action.setText(f"State: {label}")

    def _on_dictation_started(self, event: Event) -> None:
        QTimer.singleShot(0, self._set_dictation_on)

    def _set_dictation_on(self) -> None:
        self._dictation_active = True
        self.setIcon(self._icons["DICTATING"])
        self.setToolTip("VoicePilot — Dictation Active")
        self._dictation_action.setText("Stop Dictation")

    def _on_dictation_stopped(self, event: Event) -> None:
        QTimer.singleShot(0, self._set_dictation_off)

    def _set_dictation_off(self) -> None:
        self._dictation_active = False
        self._apply_state(self._current_state)
        self._dictation_action.setText("Start Dictation")

    def _on_error(self, event: Event) -> None:
        QTimer.singleShot(0, lambda: self._apply_state("ERROR"))

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single left-click — show/hide overlay (handled by MainWindow)
            pass

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def notify(self, title: str, message: str, duration_ms: int = 3000) -> None:
        """Show a desktop notification balloon from the tray."""
        self.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            duration_ms,
        )
