"""
Speech Engine — orchestrates the entire audio pipeline.

Pipeline
--------
AudioListener → VAD → [WakeWordDetector] → Transcriber → EventBus

Modes
-----
  wake_word   : Microphone always on → VAD detects speech → wake word
                must be present before speech is transcribed.
  push_to_talk: Transcription fires only while the hotkey is held.
                (Hotkey handled externally; engine exposes push/release.)
  always_on   : Every VAD-detected speech segment is transcribed.

State machine
-------------
  IDLE → (speech detected) → LISTENING_FOR_WAKE_WORD
       → (wake word confirmed) → CAPTURING
       → (silence after capture) → TRANSCRIBING
       → IDLE
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from enum import Enum, auto

import numpy as np

from voicepilot.core.config import SpeechSection
from voicepilot.core.events import Event, EventType, bus
from voicepilot.speech.listener import AudioFrame, AudioListener
from voicepilot.speech.transcriber import Transcriber
from voicepilot.speech.vad import VAD
from voicepilot.speech.wake_word import WakeWordDetector

logger = logging.getLogger(__name__)

_SOURCE = "speech_engine"


class EngineState(Enum):
    STOPPED = auto()
    IDLE = auto()                    # Microphone open, waiting for speech
    LISTENING_FOR_WAKE_WORD = auto() # Speech detected, checking for wake word
    CAPTURING = auto()               # Wake word confirmed, recording utterance
    TRANSCRIBING = auto()            # Sending audio to Whisper


class SpeechEngine:
    """
    Top-level coordinator for the speech pipeline.

    Parameters
    ----------
    config:
        SpeechSection from the loaded AppConfig.
    on_transcription:
        Optional callback invoked with the transcribed text string.
        The event bus also fires TRANSCRIPTION_READY simultaneously.
    """

    def __init__(
        self,
        config: SpeechSection,
        on_transcription: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.on_transcription = on_transcription

        self._state = EngineState.STOPPED
        self._state_lock = threading.Lock()

        # Sub-components
        self._listener = AudioListener(
            sample_rate=config.sample_rate,
            device_index=config.microphone_index,
        )
        self._vad = VAD(
            threshold=config.vad_threshold,
            silence_duration_s=config.silence_duration,
            sample_rate=config.sample_rate,
            on_speech_end=self._on_vad_speech_end,
        )
        self._wake_detector = WakeWordDetector(
            wake_word=config.wake_word,
            sample_rate=config.sample_rate,
            on_detected=self._on_wake_word,
        )
        self._transcriber = Transcriber(
            model_size=config.whisper_model,
            device=config.whisper_device,
            compute_type=config.whisper_compute_type,
            language=config.language,
        )

        # Audio accumulated after wake word until silence
        self._capture_buffer: list[np.ndarray] = []
        self._capturing = False

        # Subscribe to external push-to-talk events if needed
        bus.on(EventType.APP_READY, self._on_app_ready)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Preload models and begin listening."""
        if self._state != EngineState.STOPPED:
            logger.warning("SpeechEngine already running")
            return

        logger.info("SpeechEngine starting (mode=%s)", self.config.activation_mode)

        # Preload models in background to avoid blocking UI
        threading.Thread(target=self._preload_models, daemon=True, name="vp-model-load").start()

        self._listener.add_callback(self._on_audio_frame)
        self._listener.start()
        self._set_state(EngineState.IDLE)

        logger.info("SpeechEngine started")

    def stop(self) -> None:
        """Stop all audio processing."""
        self._listener.stop()
        self._set_state(EngineState.STOPPED)
        logger.info("SpeechEngine stopped")

    # ------------------------------------------------------------------
    # Push-to-talk external control
    # ------------------------------------------------------------------

    def push_to_talk_start(self) -> None:
        """Begin capturing (push-to-talk mode)."""
        self._capture_buffer = []
        self._capturing = True
        self._set_state(EngineState.CAPTURING)
        bus.publish_type(EventType.VAD_SPEECH_START, source=_SOURCE)

    def push_to_talk_stop(self) -> None:
        """Stop capturing and transcribe buffered audio (push-to-talk mode)."""
        self._capturing = False
        if self._capture_buffer:
            audio = np.concatenate(self._capture_buffer)
            self._capture_buffer = []
            self._set_state(EngineState.TRANSCRIBING)
            self._transcribe_async(audio)

    # ------------------------------------------------------------------
    # Audio frame handler
    # ------------------------------------------------------------------

    def _on_audio_frame(self, frame: AudioFrame) -> None:
        """Called for every 30 ms audio frame from the microphone."""
        mode = self.config.activation_mode

        if mode == "push_to_talk":
            if self._capturing:
                self._capture_buffer.append(frame.pcm)
            return

        # VAD runs on every frame regardless of mode. The verdict is consumed
        # via the on_speech_end callback rather than the return value.
        self._vad.process_frame(frame)

        if mode == "always_on":
            # VAD handles buffering; _on_vad_speech_end fires automatically
            return

        if mode == "wake_word":
            with self._state_lock:
                current = self._state

            if current == EngineState.IDLE:
                # Check for wake word in every frame
                self._wake_detector.process_frame(frame)

            elif current == EngineState.CAPTURING:
                self._capture_buffer.append(frame.pcm)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_wake_word(self) -> None:
        """Fired by WakeWordDetector when the wake word is confirmed."""
        logger.info("Wake word detected — switching to CAPTURING")
        self._capture_buffer = []
        self._capturing = True
        self._set_state(EngineState.CAPTURING)
        bus.publish_type(EventType.VAD_SPEECH_START, source=_SOURCE)

    def _on_vad_speech_end(self, audio: np.ndarray) -> None:
        """Fired by VAD when a speech segment ends."""
        with self._state_lock:
            current = self._state

        if self.config.activation_mode == "always_on":
            self._set_state(EngineState.TRANSCRIBING)
            self._transcribe_async(audio)
            return

        if current == EngineState.CAPTURING:
            # Merge captured frames with VAD's end segment
            if self._capture_buffer:
                full_audio = np.concatenate(self._capture_buffer + [audio])
            else:
                full_audio = audio
            self._capture_buffer = []
            self._capturing = False
            self._set_state(EngineState.TRANSCRIBING)
            self._transcribe_async(full_audio)

    def _on_app_ready(self, event: Event) -> None:
        logger.debug("App ready — speech engine continuing")

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def _transcribe_async(self, audio: np.ndarray) -> None:
        """Run transcription in a daemon thread so audio capture is not blocked."""
        t = threading.Thread(
            target=self._transcribe_worker,
            args=(audio,),
            daemon=True,
            name="vp-transcribe",
        )
        t.start()

    def _transcribe_worker(self, audio: np.ndarray) -> None:
        try:
            result = self._transcriber.transcribe(audio, sample_rate=self.config.sample_rate)
            if result.text and self.on_transcription:
                self.on_transcription(result.text)
        except Exception:
            logger.exception("Transcription worker failed")
            bus.publish_type(EventType.TRANSCRIPTION_FAILED, source=_SOURCE)
        finally:
            self._set_state(EngineState.IDLE)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _set_state(self, state: EngineState) -> None:
        with self._state_lock:
            old = self._state
            self._state = state
        if old != state:
            logger.debug("SpeechEngine state: %s → %s", old.name, state.name)
            bus.publish_type(
                EventType.UI_STATUS_UPDATE,
                data={"state": state.name},
                source=_SOURCE,
            )

    def _preload_models(self) -> None:
        """Load heavyweight models in the background."""
        try:
            logger.info("Pre-loading speech models …")
            self._vad.load()
            self._transcriber.load()
            if self.config.activation_mode == "wake_word":
                self._wake_detector.load()
            logger.info("All speech models ready")
            bus.publish_type(EventType.APP_READY, data={"source": "speech_engine"}, source=_SOURCE)
        except Exception:
            logger.exception("Model preloading failed")
            bus.publish_type(EventType.APP_ERROR, source=_SOURCE)

    @property
    def state(self) -> EngineState:
        with self._state_lock:
            return self._state
