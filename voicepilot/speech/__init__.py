"""Speech package."""

from voicepilot.speech.engine import EngineState, SpeechEngine
from voicepilot.speech.listener import AudioFrame, AudioListener
from voicepilot.speech.transcriber import Transcriber, TranscriptionResult
from voicepilot.speech.vad import VAD
from voicepilot.speech.wake_word import WakeWordDetector

__all__ = [
    "SpeechEngine",
    "EngineState",
    "AudioListener",
    "AudioFrame",
    "Transcriber",
    "TranscriptionResult",
    "VAD",
    "WakeWordDetector",
]
