"""
Audio listener — continuous microphone capture using sounddevice.

Captures raw PCM frames from the system microphone and feeds them
into a thread-safe ring buffer for downstream processing (VAD, ASR).
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

from voicepilot.core.exceptions import MicrophoneError

logger = logging.getLogger(__name__)

# Each frame is FRAME_DURATION_MS milliseconds of audio at the configured sample rate.
FRAME_DURATION_MS = 30  # ms — compatible with silero-VAD (30/60/100 ms)


@dataclass
class AudioFrame:
    """A single audio frame from the microphone."""

    pcm: np.ndarray          # float32, shape (samples,)
    sample_rate: int
    frame_index: int


class AudioListener:
    """
    Continuously reads from the microphone and delivers AudioFrames
    to registered callbacks.

    Thread model
    ------------
    sounddevice runs its own audio callback thread. Frames are put
    into an internal queue; a separate reader thread calls the
    registered on_frame callbacks so the audio thread is never blocked.

    Usage
    -----
        def handle(frame: AudioFrame) -> None:
            ...

        listener = AudioListener(sample_rate=16000, device_index=None)
        listener.add_callback(handle)
        listener.start()
        ...
        listener.stop()
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        device_index: int | None = None,
        frame_duration_ms: int = FRAME_DURATION_MS,
    ) -> None:
        self.sample_rate = sample_rate
        self.device_index = device_index
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)

        self._callbacks: list[Callable[[AudioFrame], None]] = []
        self._queue: queue.Queue[AudioFrame] = queue.Queue(maxsize=200)
        self._frame_index = 0
        self._running = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._stream: sd.InputStream | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_callback(self, fn: Callable[[AudioFrame], None]) -> None:
        """Register a callable that will receive every AudioFrame."""
        self._callbacks.append(fn)

    def remove_callback(self, fn: Callable[[AudioFrame], None]) -> None:
        try:
            self._callbacks.remove(fn)
        except ValueError:
            pass

    def start(self) -> None:
        """Open the microphone stream and begin delivering frames."""
        if self._running.is_set():
            logger.warning("AudioListener already running")
            return

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self.frame_size,
                device=self.device_index,
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as exc:
            raise MicrophoneError(f"Cannot open microphone: {exc}") from exc

        self._running.set()
        self._reader_thread = threading.Thread(
            target=self._reader_loop, name="vp-audio-reader", daemon=True
        )
        self._reader_thread.start()
        logger.info(
            "AudioListener started — device=%s sr=%d frame=%dms",
            self.device_index,
            self.sample_rate,
            self.frame_duration_ms,
        )

    def stop(self) -> None:
        """Stop the microphone stream and clean up threads."""
        self._running.clear()

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None

        logger.info("AudioListener stopped")

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        """sounddevice audio thread callback — must be non-blocking."""
        if status:
            logger.debug("Audio callback status: %s", status)

        frame = AudioFrame(
            pcm=indata[:, 0].copy(),   # mono channel
            sample_rate=self.sample_rate,
            frame_index=self._frame_index,
        )
        self._frame_index += 1

        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            logger.warning("Audio frame queue full — dropping frame %d", frame.frame_index)

    def _reader_loop(self) -> None:
        """Dedicated thread: drain the queue and call registered callbacks."""
        while self._running.is_set() or not self._queue.empty():
            try:
                frame = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue

            for cb in self._callbacks:
                try:
                    cb(frame)
                except Exception:
                    logger.exception("Callback %s raised in reader loop", cb)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def list_devices() -> list[dict]:
        """Return a list of available audio input devices."""
        devices = []
        for idx, info in enumerate(sd.query_devices()):
            if info["max_input_channels"] > 0:
                devices.append(
                    {
                        "index": idx,
                        "name": info["name"],
                        "sample_rates": info.get("default_samplerate"),
                        "channels": info["max_input_channels"],
                    }
                )
        return devices
