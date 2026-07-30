"""
Voice Activity Detection using silero-VAD.

silero-VAD is a compact, fast, fully local neural VAD model.
It emits SPEECH_START / SPEECH_END events through the VoicePilot event bus.

The ONNX build of the model ships inside the ``faster-whisper`` package and
runs on ``onnxruntime``, both of which VoicePilot already depends on for
transcription. That keeps VAD free of a PyTorch dependency and means the
model never has to be fetched from the network at runtime.

silero-VAD scores fixed-size windows (512 samples at 16 kHz, 256 at 8 kHz),
which do not line up with the listener's 30 ms frames. Incoming frames are
therefore buffered and scored a whole window at a time.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from voicepilot.core.events import EventType, bus
from voicepilot.core.exceptions import VADError
from voicepilot.speech.listener import AudioFrame

logger = logging.getLogger(__name__)

_SOURCE = "vad"

# silero-VAD scores audio in fixed-size windows. These are the only sizes the
# model accepts, and they are what the sample rate is validated against.
_WINDOW_SAMPLES = {16000: 512, 8000: 256}


@dataclass
class VADResult:
    is_speech: bool
    confidence: float
    frame_index: int


class VAD:
    """
    Wraps silero-VAD.

    Accumulates 30 ms frames; when speech is detected, buffers them so
    that upstream consumers (the transcriber) receive a complete speech
    segment rather than individual frames.

    Parameters
    ----------
    threshold:
        Probability threshold above which a frame is considered speech.
    silence_duration_s:
        How many consecutive seconds of silence before SPEECH_END fires.
    sample_rate:
        Must be 8000 or 16000 (silero-VAD constraint).
    pre_roll_frames:
        Number of silent frames prepended to each utterance (captures
        the onset of speech that occurs before VAD triggers).
    """

    def __init__(
        self,
        threshold: float = 0.5,
        silence_duration_s: float = 1.2,
        sample_rate: int = 16000,
        pre_roll_frames: int = 5,
        on_speech_start: Callable[[], None] | None = None,
        on_speech_end: Callable[[np.ndarray], None] | None = None,
    ) -> None:
        if sample_rate not in _WINDOW_SAMPLES:
            raise VADError(f"silero-VAD only supports 8000 or 16000 Hz, got {sample_rate}")

        self.threshold = threshold
        self.silence_duration_s = silence_duration_s
        self.sample_rate = sample_rate
        self.pre_roll_frames = pre_roll_frames
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end

        self._model = None       # lazy-loaded
        self._model_lock = threading.Lock()

        self._window_samples = _WINDOW_SAMPLES[sample_rate]
        # Incoming frames do not divide evenly into model windows, so leftover
        # samples carry over to the next call.
        self._carry = np.empty(0, dtype=np.float32)

        self._in_speech = False
        self._last_confidence = 0.0
        # Silence is tracked in samples rather than frames so it stays correct
        # regardless of the listener's frame size.
        self._silence_samples = 0
        self._silence_sample_limit = int(silence_duration_s * sample_rate)

        # Rolling pre-roll buffer of recent silent windows
        self._pre_roll: deque[np.ndarray] = deque(maxlen=pre_roll_frames)
        # Accumulates all windows of the current speech segment
        self._speech_buffer: list[np.ndarray] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load the bundled silero-VAD ONNX model (one-time operation)."""
        with self._model_lock:
            if self._model is not None:
                return
            try:
                # Ships inside faster-whisper; no network access required.
                from faster_whisper.vad import get_vad_model  # type: ignore[import]

                logger.info("Loading silero-VAD model …")
                self._model = get_vad_model()
                logger.info("silero-VAD model loaded")
            except ImportError as exc:
                raise VADError(
                    "silero-VAD requires faster-whisper and onnxruntime. "
                    "Run: pip install faster-whisper onnxruntime"
                ) from exc
            except Exception as exc:
                raise VADError(f"Failed to load silero-VAD: {exc}") from exc

    # ------------------------------------------------------------------
    # Frame processing
    # ------------------------------------------------------------------

    def process_frame(self, frame: AudioFrame) -> VADResult:
        """
        Process one audio frame.

        The frame is buffered and scored in whole model windows, so a single
        call may advance the state machine zero, one, or several times. The
        returned result reflects the last window scored; if the frame did not
        complete a window, the previous verdict is carried forward.

        Called from the AudioListener reader thread.
        Mutates internal state; thread-safety assumed by single caller.
        """
        if self._model is None:
            self.load()

        samples = np.concatenate([self._carry, frame.pcm.astype(np.float32)])
        n_windows = len(samples) // self._window_samples
        split = n_windows * self._window_samples
        self._carry = samples[split:]

        if n_windows == 0:
            # Not enough audio for a verdict yet — repeat the current state.
            return VADResult(
                is_speech=self._in_speech,
                confidence=self._last_confidence,
                frame_index=frame.frame_index,
            )

        scores = self._score(samples[:split])

        for i, confidence in enumerate(scores):
            window = samples[i * self._window_samples : (i + 1) * self._window_samples]
            self._advance(window, confidence)

        self._last_confidence = float(scores[-1])

        return VADResult(
            is_speech=self._in_speech,
            confidence=self._last_confidence,
            frame_index=frame.frame_index,
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _advance(self, window: np.ndarray, confidence: float) -> None:
        """Feed one scored window through the speech/silence state machine."""
        if confidence >= self.threshold:
            if not self._in_speech:
                # Transition: silence → speech
                self._in_speech = True
                # Prepend pre-roll so the onset of speech is not clipped
                self._speech_buffer = list(self._pre_roll)
                bus.publish_type(EventType.VAD_SPEECH_START, source=_SOURCE)
                if self.on_speech_start:
                    self.on_speech_start()
                logger.debug("VAD: speech start (confidence=%.2f)", confidence)
            self._speech_buffer.append(window)
            self._silence_samples = 0
            return

        self._pre_roll.append(window)
        if not self._in_speech:
            return

        self._speech_buffer.append(window)
        self._silence_samples += len(window)
        if self._silence_samples < self._silence_sample_limit:
            return

        # Transition: speech → silence
        self._in_speech = False
        self._silence_samples = 0
        audio = np.concatenate(self._speech_buffer)
        self._speech_buffer = []
        logger.debug(
            "VAD: speech end — %d ms of audio",
            len(audio) / self.sample_rate * 1000,
        )
        bus.publish_type(
            EventType.VAD_SPEECH_END,
            data={"audio": audio, "sample_rate": self.sample_rate},
            source=_SOURCE,
        )
        if self.on_speech_end:
            self.on_speech_end(audio)

    def _score(self, samples: np.ndarray) -> np.ndarray:
        """Score a whole number of windows, returning one probability each."""
        try:
            out = self._model(samples, num_samples=self._window_samples)
            return np.asarray(out, dtype=np.float32).reshape(-1)
        except Exception as exc:
            logger.warning("VAD scoring error: %s", exc)
            return np.zeros(len(samples) // self._window_samples, dtype=np.float32)

    def reset(self) -> None:
        """Reset VAD state (call between utterances if needed)."""
        self._in_speech = False
        self._silence_samples = 0
        self._last_confidence = 0.0
        self._carry = np.empty(0, dtype=np.float32)
        self._pre_roll.clear()
        self._speech_buffer = []
