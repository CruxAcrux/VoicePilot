"""
Overlay HUD — always-on-top status display.

Shows:
  - Current engine state (Idle / Listening / Capturing / Transcribing)
  - Live transcription text (while capturing)
  - Confirmation prompts
  - Feedback messages

The overlay is a small, semi-transparent, frameless window that
appears in a corner of the screen and auto-hides after a configurable
duration.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from voicepilot.core.events import Event, EventType, bus

logger = logging.getLogger(__name__)


class OverlayHUD(QWidget):
    """
    Compact, semi-transparent always-on-top status HUD.

    Parameters
    ----------
    position:
        Corner of the screen: "top-right" | "top-left" | "bottom-right" | "bottom-left"
    opacity:
        Window opacity (0.0–1.0).
    font_size:
        Base font size in points.
    auto_hide_ms:
        How long to show feedback messages before fading out (0 = stay).
    """

    def __init__(
        self,
        position: str = "top-right",
        opacity: float = 0.92,
        font_size: int = 13,
        auto_hide_ms: int = 4000,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.position = position
        self._opacity_value = opacity
        self.font_size = font_size
        self.auto_hide_ms = auto_hide_ms

        self._setup_window()
        self._setup_ui()
        self._setup_timers()
        self._subscribe_events()

        # Start hidden
        self.hide()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(self._opacity_value)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # State label (small, muted)
        self._state_label = QLabel("VoicePilot")
        self._state_label.setFont(QFont("Monospace", self.font_size - 2))
        self._state_label.setStyleSheet("color: #7f8c8d; background: transparent;")
        layout.addWidget(self._state_label)

        # Main message label
        self._msg_label = QLabel("")
        self._msg_label.setFont(QFont("Sans Serif", self.font_size, QFont.Weight.Medium))
        self._msg_label.setStyleSheet("color: #ecf0f1; background: transparent;")
        self._msg_label.setWordWrap(True)
        self._msg_label.setMaximumWidth(400)
        layout.addWidget(self._msg_label)

        self.setLayout(layout)

    def _setup_timers(self) -> None:
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def _subscribe_events(self) -> None:
        bus.on(EventType.UI_STATUS_UPDATE, self._on_status)
        bus.on(EventType.CONFIRMATION_REQUIRED, self._on_confirmation)
        bus.on(EventType.DICTATION_MODE_STARTED, self._on_dictation_start)
        bus.on(EventType.DICTATION_MODE_STOPPED, self._on_dictation_stop)
        bus.on(EventType.ACTION_COMPLETED, self._on_action_done)
        bus.on(EventType.ACTION_FAILED, self._on_action_failed)
        bus.on(EventType.TRANSCRIPTION_READY, self._on_transcription)
        bus.on(EventType.WAKE_WORD_DETECTED, self._on_wake_word)

    # ------------------------------------------------------------------
    # Event handlers — must schedule on Qt thread
    # ------------------------------------------------------------------

    def _on_status(self, event: Event) -> None:
        state = event.data.get("state", "")
        labels = {
            "IDLE": ("Idle", "Listening for wake word…"),
            "LISTENING_FOR_WAKE_WORD": ("Listening", "Say 'Hey Pilot'…"),
            "CAPTURING": ("Capturing", "Listening…"),
            "TRANSCRIBING": ("Processing", "Understanding…"),
            "STOPPED": ("Stopped", "VoicePilot is stopped"),
        }
        state_text, msg = labels.get(state, (state, ""))
        QTimer.singleShot(0, lambda: self._show_message(state_text, msg, persistent=True))

    def _on_wake_word(self, event: Event) -> None:
        QTimer.singleShot(0, lambda: self._show_message("Listening", "I'm listening…", auto_hide=False))

    def _on_transcription(self, event: Event) -> None:
        text = event.data.get("text", "")
        QTimer.singleShot(
            0,
            lambda: self._show_message("Heard", f'"{text}"', auto_hide=True)
        )

    def _on_confirmation(self, event: Event) -> None:
        prompt = event.data.get("prompt", "Confirm?")
        QTimer.singleShot(
            0,
            lambda: self._show_message("Confirm", prompt, auto_hide=False)
        )

    def _on_dictation_start(self, event: Event) -> None:
        QTimer.singleShot(
            0,
            lambda: self._show_message("Dictation", "Dictation mode active", auto_hide=False)
        )

    def _on_dictation_stop(self, event: Event) -> None:
        QTimer.singleShot(
            0,
            lambda: self._show_message("Command Mode", "Dictation stopped", auto_hide=True)
        )

    def _on_action_done(self, event: Event) -> None:
        intent = event.data.get("intent", "").replace("_", " ")
        QTimer.singleShot(
            0,
            lambda: self._show_message("Done", intent.title(), auto_hide=True)
        )

    def _on_action_failed(self, event: Event) -> None:
        error = event.data.get("error", "Unknown error")
        QTimer.singleShot(
            0,
            lambda: self._show_message("Error", error[:80], auto_hide=True)
        )

    # ------------------------------------------------------------------
    # Display logic
    # ------------------------------------------------------------------

    def _show_message(
        self,
        state: str,
        message: str,
        auto_hide: bool = True,
        persistent: bool = False,
    ) -> None:
        """Update the overlay content and show it."""
        self._state_label.setText(state.upper())
        self._msg_label.setText(message)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

        self._hide_timer.stop()
        if auto_hide and self.auto_hide_ms > 0 and not persistent:
            self._hide_timer.start(self.auto_hide_ms)

    def _reposition(self) -> None:
        """Move the widget to the configured corner of the screen."""
        screen = self.screen()
        if screen is None:
            return

        geo = screen.availableGeometry()
        margin = 16
        w, h = self.width() or 300, self.height() or 80

        if self.position == "top-right":
            x, y = geo.right() - w - margin, geo.top() + margin
        elif self.position == "top-left":
            x, y = geo.left() + margin, geo.top() + margin
        elif self.position == "bottom-right":
            x, y = geo.right() - w - margin, geo.bottom() - h - margin
        else:  # bottom-left
            x, y = geo.left() + margin, geo.bottom() - h - margin

        self.move(x, y)

    # ------------------------------------------------------------------
    # Paint — dark rounded background
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(20, 20, 30, 220))
        painter.setPen(QColor(60, 60, 80, 200))
        painter.drawRoundedRect(self.rect(), 10, 10)
        super().paintEvent(event)
