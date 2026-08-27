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
                for phrase in [
                    "stoppa diktering",
                    "avsluta diktering",
                    "sluta diktera",
                    "stoppa skrivläge",
                    "kommandoläge",
                ]
            ):
                self._dictation_mode.stop()
                self._speak("Diktering avstängd.")
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
            self._speak("Förlåt, jag uppfattade inte det.")
            bus.publish_type(
                EventType.UI_STATUS_UPDATE,
                data={"state": "IDLE"},
                source="app",
            )
            return

        # Handle dictation toggle at parse level
        if command.intent_name == "start_dictation":
            self._dictation_mode.start()
            self._speak("Dikteringsläge på. Prata fritt.")
            return

        if command.intent_name == "stop_dictation":
            self._dictation_mode.stop()
            self._speak("Diktering avstängd.")
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
            "open_application": "Öppnar.",
            "close_application": "Stänger.",
            "create_folder": "Mapp skapad.",
            "create_file": "Fil skapad.",
            "delete_file": "Fil borttagen.",
            "delete_folder": "Mapp borttagen.",
            "lock_computer": "Låser skärmen.",
            "shutdown": "Stänger av.",
            "restart": "Startar om.",
            "take_screenshot": "Skärmbild tagen.",
            "minimize_window": "Minimerat.",
            "maximize_window": "Maximerat.",
            "close_window": "Fönster stängt.",
        }
        msg = completions.get(intent_name, "Klart.")
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

            try:
                voices = engine.getProperty("voices") or []
                swedish_voice = next(
                    (
                        v
                        for v in voices
                        if "sv" in (v.id or "").lower()
                        or "swedish" in (v.name or "").lower()
                        or "svenska" in (v.name or "").lower()
                    ),
                    None,
                )
                if swedish_voice:
                    engine.setProperty("voice", swedish_voice.id)
                    logger.info("Using Swedish TTS voice: %s", swedish_voice.id)
                else:
                    logger.warning(
                        "No Swedish pyttsx3 voice found — falling back to the "
                        "default voice. Spoken feedback will sound wrong for "
                        "Swedish text."
                    )
            except Exception as exc:
                logger.debug("Could not select a Swedish voice: %s", exc)

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
                # espeak-ng/espeak support "-v sv" for a Swedish voice; spd-say
                # has no equivalent per-call flag, so it speaks with whatever
                # voice speech-dispatcher is configured with.
                import shutil
                import subprocess

                commands = {
                    "espeak-ng": ["espeak-ng", "-v", "sv", message],
                    "espeak": ["espeak", "-v", "sv", message],
                    "spd-say": ["spd-say", message],
                }
                for binary, argv in commands.items():
                    if shutil.which(binary):
                        subprocess.run(
                            argv,
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
