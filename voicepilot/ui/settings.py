"""
Settings dialog — PyQt6 window for configuring VoicePilot.

Sections:
  - General (theme, overlay position)
  - Speech (microphone, model, wake word, activation mode)
  - Dictation (injection method)
  - Feedback (TTS, sound effects)
  - Security (shell whitelist)
  - About
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from voicepilot.core.config import AppConfig, save_user_config

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """
    Modal settings dialog.

    Signals
    -------
    settings_saved:
        Emitted with the updated AppConfig when the user clicks Save.
    """

    settings_saved = pyqtSignal(object)   # AppConfig

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config

        self.setWindowTitle("VoicePilot Settings")
        self.setMinimumSize(560, 480)
        self.setModal(True)

        self._build_ui()
        self._load_values()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("VoicePilot Settings")
        title.setFont(QFont("Sans Serif", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_speech_tab(), "Speech")
        self._tabs.addTab(self._build_ui_tab(), "Interface")
        self._tabs.addTab(self._build_dictation_tab(), "Dictation")
        self._tabs.addTab(self._build_feedback_tab(), "Feedback")
        self._tabs.addTab(self._build_about_tab(), "About")
        layout.addWidget(self._tabs)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # --- Speech tab ---

    def _build_speech_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Speech Recognition")
        form = QFormLayout(group)

        self._activation_combo = QComboBox()
        self._activation_combo.addItems(["wake_word", "push_to_talk", "always_on"])
        form.addRow("Activation mode:", self._activation_combo)

        self._wake_word_edit = QLineEdit()
        self._wake_word_edit.setPlaceholderText("hey pilot")
        form.addRow("Wake word:", self._wake_word_edit)

        self._model_combo = QComboBox()
        self._model_combo.addItems(["tiny.en", "base.en", "small.en", "medium.en", "large-v3"])
        form.addRow("Whisper model:", self._model_combo)

        self._device_combo = QComboBox()
        self._device_combo.addItems(["cpu", "cuda"])
        form.addRow("Inference device:", self._device_combo)

        self._language_edit = QLineEdit()
        self._language_edit.setPlaceholderText("en")
        form.addRow("Language code:", self._language_edit)

        self._vad_slider = QSlider(Qt.Orientation.Horizontal)
        self._vad_slider.setRange(1, 99)
        self._vad_slider.setTickInterval(10)
        self._vad_label = QLabel("0.50")
        self._vad_slider.valueChanged.connect(
            lambda v: self._vad_label.setText(f"{v / 100:.2f}")
        )
        vad_row = QHBoxLayout()
        vad_row.addWidget(self._vad_slider)
        vad_row.addWidget(self._vad_label)
        vad_container = QWidget()
        vad_container.setLayout(vad_row)
        form.addRow("VAD sensitivity:", vad_container)

        self._silence_spin = QSpinBox()
        self._silence_spin.setRange(5, 50)
        self._silence_spin.setSuffix(" × 0.1 s")
        form.addRow("Silence duration:", self._silence_spin)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    # --- UI/Interface tab ---

    def _build_ui_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Overlay")
        form = QFormLayout(group)

        self._position_combo = QComboBox()
        self._position_combo.addItems(
            ["top-right", "top-left", "bottom-right", "bottom-left"]
        )
        form.addRow("Overlay position:", self._position_combo)

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(20, 100)
        self._opacity_label = QLabel("0.92")
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v / 100:.2f}")
        )
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self._opacity_slider)
        opacity_row.addWidget(self._opacity_label)
        opacity_container = QWidget()
        opacity_container.setLayout(opacity_row)
        form.addRow("Opacity:", opacity_container)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["dark", "light"])
        form.addRow("Theme:", self._theme_combo)

        self._show_transcription_cb = QCheckBox("Show live transcription in overlay")
        form.addRow("", self._show_transcription_cb)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(9, 24)
        form.addRow("Font size:", self._font_size_spin)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    # --- Dictation tab ---

    def _build_dictation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Text Injection")
        form = QFormLayout(group)

        self._injection_combo = QComboBox()
        self._injection_combo.addItems(["auto", "xdotool", "clipboard"])
        form.addRow("Injection method:", self._injection_combo)

        self._typing_delay_spin = QSpinBox()
        self._typing_delay_spin.setRange(0, 200)
        self._typing_delay_spin.setSuffix(" ms")
        form.addRow("Typing delay:", self._typing_delay_spin)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    # --- Feedback tab ---

    def _build_feedback_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Audio Feedback")
        form = QFormLayout(group)

        self._tts_enabled_cb = QCheckBox("Enable text-to-speech responses")
        form.addRow("", self._tts_enabled_cb)

        self._tts_engine_combo = QComboBox()
        self._tts_engine_combo.addItems(["espeak", "pyttsx3"])
        form.addRow("TTS engine:", self._tts_engine_combo)

        self._tts_rate_spin = QSpinBox()
        self._tts_rate_spin.setRange(80, 300)
        self._tts_rate_spin.setSuffix(" wpm")
        form.addRow("Speaking rate:", self._tts_rate_spin)

        self._sound_effects_cb = QCheckBox("Enable sound effects")
        form.addRow("", self._sound_effects_cb)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    # --- About tab ---

    def _build_about_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = QLabel("🎙")
        logo.setFont(QFont("Sans Serif", 48))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        name = QLabel("VoicePilot")
        name.setFont(QFont("Sans Serif", 20, QFont.Weight.Bold))
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)

        version = QLabel(f"Version {self.config.app.version}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        desc = QLabel(
            "Voice-controlled Linux desktop assistant.\n"
            "Privacy-first. Fully local. Open source."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(desc)

        layout.addStretch()
        return widget

    # ------------------------------------------------------------------
    # Load / Save values
    # ------------------------------------------------------------------

    def _load_values(self) -> None:
        """Populate all widgets with current config values."""
        s = self.config.speech
        self._activation_combo.setCurrentText(s.activation_mode)
        self._wake_word_edit.setText(s.wake_word)
        self._model_combo.setCurrentText(s.whisper_model)
        self._device_combo.setCurrentText(s.whisper_device)
        self._language_edit.setText(s.language)
        self._vad_slider.setValue(int(s.vad_threshold * 100))
        self._silence_spin.setValue(int(s.silence_duration * 10))

        u = self.config.ui
        self._position_combo.setCurrentText(u.overlay_position)
        self._opacity_slider.setValue(int(u.overlay_opacity * 100))
        self._theme_combo.setCurrentText(u.theme)
        self._show_transcription_cb.setChecked(u.show_transcription)
        self._font_size_spin.setValue(u.font_size)

        d = self.config.dictation
        self._injection_combo.setCurrentText(d.injection_method)
        self._typing_delay_spin.setValue(d.typing_delay_ms)

        f = self.config.feedback
        self._tts_enabled_cb.setChecked(f.tts_enabled)
        self._tts_engine_combo.setCurrentText(f.tts_engine)
        self._tts_rate_spin.setValue(f.tts_rate)
        self._sound_effects_cb.setChecked(f.sound_effects)

    def _on_save(self) -> None:
        """Write widget values back to config and persist."""
        try:
            self.config.speech.activation_mode = self._activation_combo.currentText()
            self.config.speech.wake_word = self._wake_word_edit.text() or "hey pilot"
            self.config.speech.whisper_model = self._model_combo.currentText()
            self.config.speech.whisper_device = self._device_combo.currentText()
            self.config.speech.language = self._language_edit.text() or "en"
            self.config.speech.vad_threshold = self._vad_slider.value() / 100
            self.config.speech.silence_duration = self._silence_spin.value() / 10

            self.config.ui.overlay_position = self._position_combo.currentText()
            self.config.ui.overlay_opacity = self._opacity_slider.value() / 100
            self.config.ui.theme = self._theme_combo.currentText()
            self.config.ui.show_transcription = self._show_transcription_cb.isChecked()
            self.config.ui.font_size = self._font_size_spin.value()

            self.config.dictation.injection_method = self._injection_combo.currentText()
            self.config.dictation.typing_delay_ms = self._typing_delay_spin.value()

            self.config.feedback.tts_enabled = self._tts_enabled_cb.isChecked()
            self.config.feedback.tts_engine = self._tts_engine_combo.currentText()
            self.config.feedback.tts_rate = self._tts_rate_spin.value()
            self.config.feedback.sound_effects = self._sound_effects_cb.isChecked()

            save_user_config(self.config)
            self.settings_saved.emit(self.config)
            logger.info("Settings saved")

        except Exception as exc:
            logger.exception("Failed to save settings: %s", exc)

        self.accept()
