"""Unit tests for the DictationMode state manager."""

from voicepilot.dictation.mode import DictationMode


def test_initial_state():
    mode = DictationMode()
    assert not mode.is_active


def test_start():
    mode = DictationMode()
    mode.start()
    assert mode.is_active


def test_stop():
    mode = DictationMode()
    mode.start()
    mode.stop()
    assert not mode.is_active


def test_toggle():
    mode = DictationMode()
    assert mode.toggle() is True
    assert mode.is_active
    assert mode.toggle() is False
    assert not mode.is_active


def test_idempotent_start():
    mode = DictationMode()
    mode.start()
    mode.start()  # Second start should not raise
    assert mode.is_active


def test_idempotent_stop():
    mode = DictationMode()
    mode.stop()  # Stop when already stopped should not raise
    assert not mode.is_active
