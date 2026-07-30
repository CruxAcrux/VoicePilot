"""
VoicePilot Application Bootstrap.

This module wires together all components into a running application:

  SpeechEngine
      ↓ transcription text
  ConfirmationManager.receive_response  (if pending)
      or
  CommandInterpreter.parse
      ↓ ParsedCommand
  ConfirmationManager.handle
      ↓ (cleared)
  ActionRegistry.dispatch
      ↓
  BaseAction.execute

  DictationMode (parallel path when active)
      ↓ transcription text
  TextInjector.inject

The Qt event loop runs on the main thread.
The SpeechEngine runs audio capture and transcription on daemon threads.
The ConfirmationManager timer runs on a daemon thread.
All inter-module communication goes through the EventBus.
"""

from __future__ import annotations

import logging
import threading

from voicepilot.confirmation.audit import AuditLog
from voicepilot.confirmation.manager import ConfirmationManager
from voicepilot.core.config import AppConfig
from voicepilot.core.events import EventType, bus
from voicepilot.core.exceptions import UnknownCommandError
from voicepilot.dictation.injector import TextInjector
from voicepilot.dictation.mode import DictationMode
from voicepilot.executor.app_launcher import AppLauncherAction
from voicepilot.executor.file_manager import FileManagerAction
from voicepilot.executor.registry import ActionRegistry
from voicepilot.executor.shell import SystemAction
from voicepilot.executor.window_manager import WindowManagerAction
from voicepilot.integrations.vscode.commands import VSCodeAction
from voicepilot.parser.interpreter import CommandInterpreter
from voicepilot.plugins.loader import PluginLoader
from voicepilot.settings.store import SettingsStore
from voicepilot.speech.engine import SpeechEngine

logger = logging.getLogger(__name__)


class VoicePilotApp:
    """
    Top-level application object.

    Owns and manages the lifecycle of every component.
    Does not touch Qt — the UI layer is injected separately.

    Usage
    -----
        config = load_config()
        app = VoicePilotApp(config)
        app.start()
        # ... run Qt event loop ...
        app.stop()
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._started = False

        # Storage
        data_dir = config.app.data_dir
        self._audit_log = AuditLog(data_dir / "audit.db")
        self._settings_store = SettingsStore(data_dir / "settings.db")

        # Dictation
        self._dictation_mode = DictationMode()
        self._text_injector = TextInjector(
            method=config.dictation.injection_method,
            typing_delay_ms=config.dictation.typing_delay_ms,
        )

        # Command parsing
        self._interpreter = CommandInterpreter()

        # Action registry — register all built-in actions
        self._registry = ActionRegistry()
        self._register_actions()

        # TTS / feedback
        self._tts = self._build_tts()

        # Confirmation manager
        self._confirmation = ConfirmationManager(
            config=config.confirmation,
            on_execute=self._dispatch_action,
            on_speak=self._speak,
            audit_log=self._audit_log,
        )

        # Speech engine
        self._speech_engine = SpeechEngine(
            config=config.speech,
            on_transcription=self._on_transcription,
        )

        # Plugins
        self._plugin_loader = PluginLoader()
        self._load_plugins()

        logger.info("VoicePilotApp initialised")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start listening and processing voice commands."""
        if self._started:
            return
        self._started = True
        self._speech_engine.start()
        logger.info("VoicePilot started")

    def stop(self) -> None:
        """Gracefully stop the application."""
        if not self._started:
            return
        self._speech_engine.stop()
        self._started = False
        logger.info("VoicePilot stopped")

    # ------------------------------------------------------------------
    # Core transcription handler
    # ------------------------------------------------------------------

    def _on_transcription(self, text: str) -> None:
        """
        Receive transcribed text from the SpeechEngine.

        Routes to:
          - DictationMode (if active) → TextInjector
          - ConfirmationManager.receive_response (if confirmation pending)
          - CommandInterpreter → ConfirmationManager → ActionRegistry
        """
        text = text.strip()
        if not text:
            return

        logger.info("Transcription: %r", text)

        # 1. Dictation mode — inject text directly
        if self._dictation_mode.is_active:
            # Still check for stop-dictation command
            if any(
                phrase in text.lower()
                for phrase in ["stop dictation", "end dictation", "command mode", "stop typing"]
            ):
                self._dictation_mode.stop()
                self._speak("Dictation stopped.")
                return

            try:
                self._text_injector.inject(text + " ")
            except Exception as exc:
                logger.error("Text injection failed: %s", exc)
            return

        # 2. Confirmation response — route to manager first
        if self._confirmation.has_pending:
            consumed = self._confirmation.receive_response(text)
            if consumed:
                return

        # 3. Parse as command
        try:
            command = self._interpreter.parse(text)
        except UnknownCommandError:
            logger.info("Unknown command: %r", text)
            self._speak("Sorry, I didn't understand that.")
            bus.publish_type(
                EventType.UI_STATUS_UPDATE,
                data={"state": "IDLE"},
                source="app",
            )
            return

        # Handle dictation toggle at parse level
        if command.intent_name == "start_dictation":
            self._dictation_mode.start()
            self._speak("Dictation mode started. Speak freely.")
            return

        if command.intent_name == "stop_dictation":
            self._dictation_mode.stop()
            self._speak("Dictation stopped.")
            return

        # 4. Send to confirmation manager (handles risk classification + execution)
        self._confirmation.handle(command)

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    def _dispatch_action(self, command) -> None:
        """Dispatch a confirmed command to the action registry."""
        try:
            self._registry.dispatch(command)
            self._speak_completion(command.intent_name)
        except KeyError:
            msg = f"No action registered for: {command.intent_name}"
            logger.error(msg)
            raise

    def _speak_completion(self, intent_name: str) -> None:
        """Provide brief spoken feedback on successful action."""
        completions = {
            "open_application": "Opening.",
            "close_application": "Closing.",
            "create_folder": "Folder created.",
            "create_file": "File created.",
            "delete_file": "File deleted.",
            "delete_folder": "Folder deleted.",
            "lock_computer": "Locking screen.",
            "shutdown": "Shutting down.",
            "restart": "Restarting.",
            "take_screenshot": "Screenshot taken.",
            "minimize_window": "Minimized.",
            "maximize_window": "Maximized.",
            "close_window": "Window closed.",
        }
        msg = completions.get(intent_name, "Done.")
        self._speak(msg)

    # ------------------------------------------------------------------
    # Action registration
    # ------------------------------------------------------------------

    def _register_actions(self) -> None:
        """Register all built-in action handlers with the registry."""
        cfg = self.config

        self._registry.register_many(
            AppLauncherAction(app_aliases=cfg.apps.aliases),
            FileManagerAction(folder_aliases=cfg.folders.aliases),
            WindowManagerAction(),
            SystemAction(shell_whitelist=cfg.security.shell_command_whitelist),
        )

        if cfg.vscode.enabled:
            self._registry.register(
                VSCodeAction(
                    projects_dir=cfg.vscode.projects_dir,
                    code_binary=cfg.vscode.binary,
                )
            )

        logger.info(
            "Registered %d intent handlers", len(self._registry.registered_intents())
        )

    # ------------------------------------------------------------------
    # TTS / Feedback
    # ------------------------------------------------------------------

    def _build_tts(self):
        """Build the TTS engine (pyttsx3 or espeak fallback)."""
        if not self.config.feedback.tts_enabled:
            return None

        try:
            import pyttsx3  # type: ignore[import]

            engine = pyttsx3.init()
            engine.setProperty("rate", self.config.feedback.tts_rate)
            engine.setProperty("volume", self.config.feedback.tts_volume)
            return engine
        except Exception as exc:
            logger.warning("pyttsx3 unavailable (%s) — TTS disabled", exc)
            return None

    def _speak(self, message: str) -> None:
        """Speak a message via TTS (non-blocking)."""
        if not self.config.feedback.tts_enabled:
            return

        logger.debug("TTS: %r", message)

        bus.publish_type(
            EventType.UI_STATUS_UPDATE,
            data={"state": "IDLE", "message": message},
            source="app",
        )

        def _do_speak():
            try:
                if self._tts:
                    self._tts.say(message)
                    self._tts.runAndWait()
                    return

                # Fall back to a command-line speech synthesiser. espeak-ng is
                # what current Debian/Ubuntu/Mint releases ship; plain espeak
                # and spd-say cover older or differently-configured systems.
                import shutil
                import subprocess

                for binary in ("espeak-ng", "espeak", "spd-say"):
                    if shutil.which(binary):
                        subprocess.run(
                            [binary, message],
                            capture_output=True,
                            timeout=10,
                        )
                        return

                logger.debug("No TTS backend available — message not spoken: %r", message)
            except Exception as exc:
                logger.debug("TTS error: %s", exc)

        threading.Thread(target=_do_speak, daemon=True, name="vp-tts").start()

    # ------------------------------------------------------------------
    # Plugins
    # ------------------------------------------------------------------

    def _load_plugins(self) -> None:
        plugins = self._plugin_loader.load_all()
        for plugin in plugins:
            try:
                plugin.setup(self._interpreter, self._registry)
                logger.info("Plugin %r set up", plugin.name)
            except Exception:
                logger.exception("Plugin %r setup failed", plugin.name)

    # ------------------------------------------------------------------
    # Public properties (for UI integration)
    # ------------------------------------------------------------------

    @property
    def dictation_mode(self) -> DictationMode:
        return self._dictation_mode

    @property
    def speech_engine(self) -> SpeechEngine:
        return self._speech_engine

    @property
    def audit_log(self) -> AuditLog:
        return self._audit_log

    @property
    def settings_store(self) -> SettingsStore:
        return self._settings_store
