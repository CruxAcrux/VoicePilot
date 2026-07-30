"""
Wake word detector wrapping openwakeword.

openwakeword is a fully local, trainable wake-word detection library.
The bundled "hey_mycroft" model is used by default; a custom "hey_pilot"
model can be trained and placed in the models/ directory.

When a wake word is detected, EventType.WAKE_WORD_DETECTED is published
and the registered callback fires.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

import numpy as np

from voicepilot.core.events import EventType, bus
from voicepilot.core.exceptions import WakeWordError
from voicepilot.speech.listener import AudioFrame

logger = logging.getLogger(__name__)

_SOURCE = "wake_word"

# Path where custom wake word models are stored
_MODELS_DIR = Path(__file__).parent.parent.parent / "models"


class WakeWordDetector:
    """
    Listens for the configured wake word in the incoming audio stream.

    Parameters
    ----------
    wake_word:
        The wake word string (e.g. "hey pilot"). Used to select the
        appropriate openwakeword model.
    threshold:
        Activation score threshold (0–1). Higher = fewer false positives.
    on_detected:
        Optional callback invoked when the wake word is detected.
    cooldown_seconds:
        Minimum gap between consecutive detections.
    """

    def __init__(
        self,
        wake_word: str = "hey pilot",
        threshold: float = 0.5,
        on_detected: Callable[[], None] | None = None,
        cooldown_seconds: float = 2.0,
        sample_rate: int = 16000,
    ) -> None:
        self.wake_word = wake_word
        self.threshold = threshold
        self.on_detected = on_detected
        self.cooldown_seconds = cooldown_seconds
        self.sample_rate = sample_rate

        self._model = None
        self._model_lock = threading.Lock()
        self._last_detection: float = 0.0
        self._enabled = True

        # openwakeword expects 16 kHz mono int16 audio in 80 ms chunks
        # (1280 samples). We accumulate frames until we have enough.
        self._chunk_size = int(sample_rate * 0.08)   # 1280 @ 16kHz
        self._buffer: list[np.ndarray] = []
        self._buffered_samples = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load the openwakeword model. Called lazily on first frame."""
        with self._model_lock:
            if self._model is not None:
                return
            try:
                from openwakeword.model import Model  # type: ignore[import]

                # Look for a custom model matching the wake word name
                model_path = self._resolve_model_path()

                if model_path and model_path.exists():
                    logger.info("Loading custom wake word model: %s", model_path)
                    self._model = Model(
                        wakeword_models=[str(model_path)],
                        inference_framework="onnx",
                    )
                else:
                    # The bundled models are not shipped in the wheel; they are
                    # fetched once on first use.
                    self._ensure_pretrained_models()
                    # Fall back to a bundled openwakeword model
                    logger.info(
                        "No custom model found for %r — using 'alexa' as stand-in. "
                        "Train a custom 'hey_pilot' model for production.",
                        self.wake_word,
                    )
                    self._model = Model(inference_framework="onnx")

                logger.info("Wake word detector loaded (threshold=%.2f)", self.threshold)

            except ImportError as exc:
                raise WakeWordError(
                    "openwakeword is not installed. Run: pip install openwakeword"
                ) from exc
            except Exception as exc:
                raise WakeWordError(f"Failed to load wake word model: {exc}") from exc

    @staticmethod
    def _ensure_pretrained_models() -> None:
        """
        Download openwakeword's pretrained models if they are not present.

        The wheel ships only the code; the ONNX models are release assets that
        must be fetched once. Without them, model construction fails with a
        bare "NO_SUCHFILE" error, so this is done up front with a clear log
        line. Subsequent runs find the files and skip the download.
        """
        import openwakeword  # type: ignore[import]
        from openwakeword.utils import download_models  # type: ignore[import]

        models_dir = Path(openwakeword.__file__).parent / "resources" / "models"

        # The melspectrogram and embedding models are required by every
        # wakeword model, so their presence is a good readiness signal.
        required = ["melspectrogram.onnx", "embedding_model.onnx"]
        have_shared = models_dir.is_dir() and all(
            (models_dir / f).exists() for f in required
        )
        if have_shared and any(models_dir.glob("*_v0.1.onnx")):
            return

        logger.info(
            "Downloading openwakeword pretrained models to %s (one-time, ~10 MB)…",
            models_dir,
        )
        download_models()
        logger.info("Wake word models downloaded")

    def _resolve_model_path(self) -> Path | None:
        """Look for a custom .onnx model matching the wake word."""
        name = self.wake_word.replace(" ", "_")
        candidates = [
            _MODELS_DIR / f"{name}.onnx",
            _MODELS_DIR / f"{name}.tflite",
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process_frame(self, frame: AudioFrame) -> bool:
        """
        Process one audio frame. Returns True if wake word was just detected.
        Must be called from a single thread.
        """
        if not self._enabled:
            return False

        if self._model is None:
            self.load()

        # Accumulate into fixed 80 ms chunks. The listener's frames (30 ms) do
        # not divide evenly into them, so leftover samples carry over rather
        # than being padded into an oversized chunk.
        self._buffer.append(frame.pcm.astype(np.float32))
        self._buffered_samples += len(frame.pcm)

        if self._buffered_samples < self._chunk_size:
            return False

        samples = np.concatenate(self._buffer)
        chunk_f32 = samples[: self._chunk_size]
        leftover = samples[self._chunk_size :]

        self._buffer = [leftover] if len(leftover) else []
        self._buffered_samples = len(leftover)

        # openwakeword expects int16
        chunk_i16 = (chunk_f32 * 32767).astype(np.int16)

        return self._run_inference(chunk_i16)

    def _run_inference(self, chunk_i16: np.ndarray) -> bool:
        import time

        try:
            predictions = self._model.predict(chunk_i16)
        except Exception as exc:
            logger.warning("Wake word inference error: %s", exc)
            return False

        now = time.monotonic()
        if now - self._last_detection < self.cooldown_seconds:
            return False

        # predictions is a dict model_name → score
        for model_name, score in predictions.items():
            if score >= self.threshold:
                self._last_detection = now
                logger.info(
                    "Wake word detected! model=%s score=%.3f", model_name, score
                )
                bus.publish_type(
                    EventType.WAKE_WORD_DETECTED,
                    data={"model": model_name, "score": float(score)},
                    source=_SOURCE,
                )
                if self.on_detected:
                    self.on_detected()
                return True

        return False

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled
