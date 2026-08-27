"""
Speech-to-text transcription using faster-whisper.

faster-whisper is a re-implementation of OpenAI Whisper using
CTranslate2, offering 2–4× speedup with the same accuracy.
All inference runs fully locally with no network access.

Receives audio segments (numpy arrays) from the VAD and produces
plain text transcriptions published via the event bus.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from voicepilot.core.events import EventType, bus
from voicepilot.core.exceptions import TranscriptionError

logger = logging.getLogger(__name__)

_SOURCE = "transcriber"

# Default model download cache
_CACHE_DIR = Path("~/.cache/voicepilot/whisper").expanduser()


@dataclass
class TranscriptionResult:
    """Result of a transcription pass."""

    text: str
    language: str
    duration_s: float           # Audio duration
    inference_ms: float         # Time taken for inference
    no_speech_prob: float       # Probability that no speech was present


class Transcriber:
    """
    Wraps faster-whisper for offline speech-to-text.

    Parameters
    ----------
    model_size:
        One of "tiny.en", "base.en", "small.en", "medium.en", "large-v3".
        "base.en" is recommended for the MVP (good accuracy, <1 GB RAM).
    device:
        "cpu" or "cuda".
    compute_type:
        "int8" (fastest on CPU), "float16" (GPU), "float32" (most accurate).
    language:
        ISO 639-1 code. "en" locks the model to English for speed.
    beam_size:
        Beam search width. 1 = greedy (fastest); 5 = default Whisper.
    """

    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "en",
        beam_size: int = 1,
        download_root: Path = _CACHE_DIR,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.download_root = download_root

        self._model = None
        self._model_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Download and load the Whisper model (one-time per model size)."""
        with self._model_lock:
            if self._model is not None:
                return
            try:
                from faster_whisper import WhisperModel  # type: ignore[import]

                self.download_root.mkdir(parents=True, exist_ok=True)

                logger.info(
                    "Loading Whisper model '%s' on %s (%s) …",
                    self.model_size,
                    self.device,
                    self.compute_type,
                )
                t0 = time.monotonic()
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=str(self.download_root),
                )
                elapsed = (time.monotonic() - t0) * 1000
                logger.info("Whisper model loaded in %.0f ms", elapsed)

            except ImportError as exc:
                raise TranscriptionError(
                    "faster-whisper is not installed. Run: pip install faster-whisper"
                ) from exc
            except Exception as exc:
                raise TranscriptionError(f"Failed to load Whisper model: {exc}") from exc

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        """
        Transcribe a speech segment.

        Parameters
        ----------
        audio:
            float32 numpy array, mono, at `sample_rate` Hz.
        sample_rate:
            Audio sample rate. Whisper expects 16000 Hz.

        Returns
        -------
        TranscriptionResult
            The cleaned transcription and metadata.
        """
        if self._model is None:
            self.load()

        if sample_rate != 16000:
            audio = self._resample(audio, sample_rate, 16000)

        audio_duration_s = len(audio) / 16000

        t0 = time.monotonic()
        try:
            segments, info = self._model.transcribe(
                audio,
                language=self.language if self.language else None,
                beam_size=self.beam_size,
                vad_filter=False,          # We do our own VAD
                word_timestamps=False,
            )

            # Consume the lazy generator
            text_parts: list[str] = []
            no_speech_prob: float = 0.0
            for seg in segments:
                text_parts.append(seg.text)
                no_speech_prob = max(no_speech_prob, seg.no_speech_prob)

            text = " ".join(text_parts).strip()

        except Exception as exc:
            raise TranscriptionError(f"Transcription failed: {exc}") from exc

        inference_ms = (time.monotonic() - t0) * 1000

        result = TranscriptionResult(
            text=text,
            language=info.language if info else self.language,
            duration_s=audio_duration_s,
            inference_ms=inference_ms,
            no_speech_prob=no_speech_prob,
        )

        logger.info(
            "Transcribed %.1f s audio in %.0f ms: %r (no_speech=%.2f)",
            audio_duration_s,
            inference_ms,
            text,
            no_speech_prob,
        )

        if text:
            bus.publish_type(
                EventType.TRANSCRIPTION_READY,
                data={
                    "text": text,
                    "language": result.language,
                    "duration_s": audio_duration_s,
                    "inference_ms": inference_ms,
                    "no_speech_prob": no_speech_prob,
                },
                source=_SOURCE,
            )
        else:
            logger.debug("Empty transcription — skipping event")
            bus.publish_type(EventType.TRANSCRIPTION_FAILED, source=_SOURCE)

        return result

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _resample(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
        """Simple linear resampling (adequate for 48kHz→16kHz)."""
        ratio = to_rate / from_rate
        new_length = int(len(audio) * ratio)
        indices = np.linspace(0, len(audio) - 1, new_length)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
