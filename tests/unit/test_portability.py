"""
Regression tests for cross-distribution portability.

These cover faults that only surfaced when the project moved from the machine
it was written on (Ubuntu/GNOME) to a different desktop (Linux Mint/Cinnamon),
plus two that were silently broken everywhere.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from voicepilot.core import desktop
from voicepilot.core.config import _default_config_path, load_config

# ---------------------------------------------------------------------------
# Bundled configuration
# ---------------------------------------------------------------------------

def test_bundled_default_config_is_parseable():
    """
    The bundled default.toml must be valid TOML.

    It previously used `microphone_index = null`, which TOML has no literal
    for. The loader caught the parse error and fell back to an empty dict, so
    every value in the file was silently ignored on every run.
    """
    path = _default_config_path()
    assert path.exists(), f"bundled default config missing at {path}"

    # Parse the file directly. Asserting on loaded values would not catch this:
    # the loader falls back to Pydantic defaults that happen to match the file,
    # so a discarded config looks identical to a working one.
    from voicepilot.core.config import _load_toml

    parsed = _load_toml(path, required=True)
    assert parsed, "default.toml parsed to an empty dict"
    assert "speech" in parsed and "app" in parsed

    config = load_config()
    assert config.speech.wake_word == "hey jarvis"
    assert config.app.name == "VoicePilot"


def test_bundled_default_config_loads_without_warning(caplog):
    """A parse failure must not be downgraded to a silent warning."""
    with caplog.at_level("WARNING"):
        load_config()

    assert not [
        r for r in caplog.records if "Could not load config" in r.getMessage()
    ], "bundled config failed to parse"


# ---------------------------------------------------------------------------
# Desktop detection
# ---------------------------------------------------------------------------

def test_detect_desktop_handles_vendor_prefixes(monkeypatch):
    """Mint reports 'X-Cinnamon'; Ubuntu reports 'ubuntu:GNOME'."""
    cases = {
        "X-Cinnamon": "cinnamon",
        "ubuntu:GNOME": "gnome",
        "GNOME": "gnome",
        "KDE": "kde",
        "plasma": "kde",
        "XFCE": "xfce",
        "MATE": "mate",
    }
    for value, expected in cases.items():
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", value)
        assert desktop.detect_desktop() == expected, f"{value!r} → {expected!r}"


def test_detect_desktop_falls_back_to_session(monkeypatch):
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    monkeypatch.setenv("DESKTOP_SESSION", "cinnamon")
    assert desktop.detect_desktop() == "cinnamon"


def test_detect_desktop_unknown(monkeypatch):
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    monkeypatch.delenv("DESKTOP_SESSION", raising=False)
    assert desktop.detect_desktop() == "unknown"


def test_resolve_app_prefers_desktop_native(monkeypatch):
    """
    On Cinnamon, "files" must resolve to nemo rather than nautilus — the bug
    that made file commands fail after the move to Mint.
    """
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "X-Cinnamon")
    monkeypatch.setattr(desktop.shutil, "which", lambda b: f"/usr/bin/{b}")
    assert desktop.resolve_app("files") == "nemo"
    assert desktop.resolve_app("text editor") == "xed"

    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    assert desktop.resolve_app("files") == "nautilus"
    assert desktop.resolve_app("text editor") == "gedit"


def test_resolve_app_skips_uninstalled(monkeypatch):
    """With nautilus absent, "files" falls through to whatever is installed."""
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    monkeypatch.setattr(
        desktop.shutil, "which", lambda b: "/usr/bin/nemo" if b == "nemo" else None
    )
    assert desktop.resolve_app("files") == "nemo"


def test_resolve_app_returns_none_when_nothing_installed(monkeypatch):
    monkeypatch.setattr(desktop.shutil, "which", lambda b: None)
    assert desktop.resolve_app("files") is None
    assert desktop.resolve_app("no-such-application") is None


def test_first_available_picks_installed_command(monkeypatch):
    commands = [("aaa", ["aaa", "--x"]), ("bbb", ["bbb", "--y"])]
    monkeypatch.setattr(
        desktop.shutil, "which", lambda b: "/usr/bin/bbb" if b == "bbb" else None
    )
    assert desktop.first_available(commands) == ["bbb", "--y"]

    monkeypatch.setattr(desktop.shutil, "which", lambda b: None)
    assert desktop.first_available(commands) is None


# ---------------------------------------------------------------------------
# App launcher fallback
# ---------------------------------------------------------------------------

def test_app_launcher_falls_back_when_configured_binary_missing(monkeypatch):
    """
    A config written on Ubuntu names nautilus. On a Mint box that ships nemo,
    the launcher must use nemo instead of failing.
    """
    from voicepilot.executor import app_launcher

    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "X-Cinnamon")
    installed = {"nemo", "firefox"}
    monkeypatch.setattr(
        app_launcher.shutil,
        "which",
        lambda b: f"/usr/bin/{b}" if b in installed else None,
    )
    monkeypatch.setattr(
        desktop.shutil,
        "which",
        lambda b: f"/usr/bin/{b}" if b in installed else None,
    )

    action = app_launcher.AppLauncherAction(
        app_aliases={"files": "nautilus", "firefox": "firefox"}
    )

    assert action._resolve("files") == "nemo"
    # An alias that *is* installed must be left alone.
    assert action._resolve("firefox") == "firefox"


def test_app_launcher_keeps_alias_when_nothing_installed(monkeypatch):
    """The error message should name what the user configured."""
    from voicepilot.executor import app_launcher

    monkeypatch.setattr(app_launcher.shutil, "which", lambda b: None)
    monkeypatch.setattr(desktop.shutil, "which", lambda b: None)

    action = app_launcher.AppLauncherAction(app_aliases={"files": "nautilus"})
    assert action._resolve("files") == "nautilus"


# ---------------------------------------------------------------------------
# Svenska alias
# ---------------------------------------------------------------------------

def test_swedish_alias_filhanteraren_resolves_to_installed_binary(monkeypatch):
    """
    "filhanteraren" är det uttalade svenska namnet som pekar mot nautilus i
    config-defaulten (AppsSection.aliases). Precis som "files" i den
    engelska motsvarigheten ovan måste den falla tillbaka till nemo på en
    Mint-burk där nautilus inte är installerat.
    """
    from voicepilot.core.config import AppsSection
    from voicepilot.executor import app_launcher

    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "X-Cinnamon")
    installed = {"nemo", "firefox"}
    monkeypatch.setattr(
        app_launcher.shutil,
        "which",
        lambda b: f"/usr/bin/{b}" if b in installed else None,
    )
    monkeypatch.setattr(
        desktop.shutil,
        "which",
        lambda b: f"/usr/bin/{b}" if b in installed else None,
    )

    action = app_launcher.AppLauncherAction(app_aliases=AppsSection().aliases)

    assert action._resolve("filhanteraren") == "nemo"
    assert action._resolve("firefox") == "firefox"


def test_folder_alias_nedladdningar_resolves_to_downloads_path():
    """Mappaliaset "nedladdningar" (default-config) ska peka på ~/Downloads."""
    from voicepilot.core.config import FoldersSection
    from voicepilot.executor.file_manager import FileManagerAction

    action = FileManagerAction(folder_aliases=FoldersSection().aliases)

    assert action.folder_aliases["nedladdningar"] == Path("~/Downloads").expanduser()


# ---------------------------------------------------------------------------
# Wake word
# ---------------------------------------------------------------------------

def test_wake_word_loads_only_one_model():
    """
    Regression: att skapa openwakeword.Model() utan argument laddar HELA det
    medföljande modellpaketet (alexa, hey_mycroft, hey_rhasspy, timer,
    weather, …), vilket gjorde att detektorn utlöstes av "Alexa" och andra
    ord som inte hade något med det konfigurerade wake word:et att göra.
    Bara modellen för det konfigurerade ordet ("hey jarvis") får laddas.

    Kräver att openwakeword och dess förtränade modeller finns nedladdade
    lokalt — hoppas över annars.
    """
    pytest.importorskip("openwakeword")

    from voicepilot.core.exceptions import WakeWordError
    from voicepilot.speech.wake_word import WakeWordDetector

    detector = WakeWordDetector(wake_word="hey jarvis")
    try:
        detector.load()
    except WakeWordError as exc:
        pytest.skip(f"openwakeword-modeller inte tillgängliga: {exc}")

    loaded_models = detector._model.models
    assert len(loaded_models) == 1, (
        f"exakt en modell ska vara laddad, fick: {list(loaded_models)}"
    )
    assert "hey_jarvis" in next(iter(loaded_models))


# ---------------------------------------------------------------------------
# Confirmation manager concurrency
# ---------------------------------------------------------------------------

def _high_risk_command():
    from voicepilot.parser.intent import (
        Intent,
        IntentCategory,
        ParsedCommand,
        RiskLevel,
    )

    intent = Intent(
        name="delete_file",
        category=IntentCategory.FILE_MANAGEMENT,
        patterns=["delete {name}"],
        risk=RiskLevel.HIGH,
    )
    return ParsedCommand(
        intent=intent,
        slots={"name": "notes.txt"},
        raw_text="delete notes.txt",
        confidence=95.0,
        pattern_matched="delete {name}",
    )


def test_superseding_pending_confirmation_does_not_deadlock():
    """
    handle() used to call _cancel_pending() while holding a non-reentrant lock,
    so a second risky command arriving while one was pending hung the thread
    that delivered it — wedging transcription handling for the whole session.
    """
    from voicepilot.confirmation.manager import ConfirmationManager
    from voicepilot.core.config import ConfirmationSection

    manager = ConfirmationManager(
        config=ConfirmationSection(timeout_seconds=30),
        on_execute=lambda cmd: None,
    )

    manager.handle(_high_risk_command())
    assert manager.has_pending

    finished = threading.Event()

    def supersede():
        manager.handle(_high_risk_command())
        finished.set()

    threading.Thread(target=supersede, daemon=True).start()

    assert finished.wait(timeout=5), "handle() deadlocked while superseding"
    assert manager.has_pending


def test_confirmation_requires_the_high_risk_phrase():
    from voicepilot.confirmation.manager import ConfirmationManager
    from voicepilot.core.config import ConfirmationSection

    executed = []
    manager = ConfirmationManager(
        config=ConfirmationSection(timeout_seconds=30),
        on_execute=executed.append,
    )

    manager.handle(_high_risk_command())

    # The medium-risk phrase alone must not clear a high-risk command.
    assert manager.receive_response("bekräfta") is True
    assert executed == []
    assert manager.has_pending

    assert manager.receive_response("bekräfta radera") is True
    assert len(executed) == 1
    assert not manager.has_pending


def test_cancel_clears_pending_confirmation():
    from voicepilot.confirmation.manager import ConfirmationManager
    from voicepilot.core.config import ConfirmationSection

    executed = []
    manager = ConfirmationManager(
        config=ConfirmationSection(timeout_seconds=30),
        on_execute=executed.append,
    )

    manager.handle(_high_risk_command())
    assert manager.receive_response("avbryt") is True
    assert executed == []
    assert not manager.has_pending


# ---------------------------------------------------------------------------
# VAD windowing
# ---------------------------------------------------------------------------

def test_vad_scores_30ms_frames_without_error():
    """
    silero-VAD only accepts 512-sample windows at 16 kHz, but the listener
    emits 480-sample frames. Feeding frames straight through made every
    inference throw, and the exception handler scored it 0.0 — so speech was
    never detected at all.
    """
    np = pytest.importorskip("numpy")
    from voicepilot.speech.listener import AudioFrame
    from voicepilot.speech.vad import VAD

    vad = VAD(sample_rate=16000, silence_duration_s=0.3)
    vad.load()

    rng = np.random.default_rng(0)
    scored = 0
    for index in range(40):
        pcm = (rng.standard_normal(480) * 0.1).astype(np.float32)
        result = vad.process_frame(AudioFrame(pcm=pcm, sample_rate=16000, frame_index=index))
        # A real score, not the 0.0 the old error path produced every time.
        assert 0.0 <= result.confidence <= 1.0
        scored += 1

    assert scored == 40
    # Leftover samples must be carried, never silently dropped.
    assert len(vad._carry) < 512


def test_vad_rejects_unsupported_sample_rate():
    from voicepilot.core.exceptions import VADError
    from voicepilot.speech.vad import VAD

    with pytest.raises(VADError):
        VAD(sample_rate=44100)


# ---------------------------------------------------------------------------
# Dictation injector
# ---------------------------------------------------------------------------

def test_injector_handles_every_method_it_can_resolve(monkeypatch):
    """
    _resolve_method() could return "ydotool", but inject() only handled
    xdotool and clipboard — so on Wayland with ydotool installed, dictation
    raised instead of typing.
    """
    from voicepilot.dictation.injector import TextInjector

    def record_dispatch(method: str) -> list[str]:
        """Return which strategy inject() dispatched to for *method*."""
        injector = TextInjector(method=method)
        assert injector._resolve_method() == method

        calls: list[str] = []
        for name in ("xdotool", "ydotool", "clipboard"):
            monkeypatch.setattr(
                injector,
                f"_inject_{name}",
                lambda _text, name=name: calls.append(name),
            )

        injector.inject("hello")
        return calls

    for method in ("xdotool", "ydotool", "clipboard"):
        assert record_dispatch(method) == [method]


def test_injector_auto_resolves_per_session_type(monkeypatch):
    from voicepilot.dictation import injector as injector_mod

    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.setattr(injector_mod.shutil, "which", lambda b: f"/usr/bin/{b}")
    assert injector_mod.TextInjector(method="auto")._resolve_method() == "xdotool"

    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    assert injector_mod.TextInjector(method="auto")._resolve_method() == "ydotool"

    # Wayland without ydotool falls back to clipboard paste.
    monkeypatch.setattr(injector_mod.shutil, "which", lambda b: None)
    assert injector_mod.TextInjector(method="auto")._resolve_method() == "clipboard"
