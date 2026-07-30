# VoicePilot

Voice-controlled Linux desktop assistant. Hands-free computer interaction for developers, power users, and accessibility-focused users.

## Quick Start

```bash
# Install system and Python dependencies
./scripts/install.sh

# Activate virtual environment
source .venv/bin/activate

# Launch
voicepilot

# Debug mode
voicepilot --debug

# Headless (no GUI, useful for testing)
voicepilot --no-ui
```

## Features (Phase 1)

- **Wake word activation** — Say "Hey Pilot" to activate
- **Application control** — Open, close, switch applications by name
- **File management** — Create files/folders, open directories, search
- **Dictation mode** — Speak to type into any application
- **Safety system** — Three-tier risk classification with voice confirmation
- **VS Code integration** — Open projects, navigate, run code
- **System commands** — Lock, volume, screenshots, window management

## Architecture

```
Microphone
  ↓
AudioListener (sounddevice)
  ↓
VAD (silero-vad)
  ↓ speech detected
WakeWordDetector (openwakeword)       ← "Hey Pilot"
  ↓ wake word confirmed
Transcriber (faster-whisper)
  ↓ text
CommandInterpreter (rapidfuzz)        ← rule-based grammar
  ↓ ParsedCommand
ConfirmationManager                   ← LOW / MEDIUM / HIGH risk
  ↓ cleared
ActionRegistry → BaseAction.execute()
  ↓
Linux System (subprocess / pynput / xdotool)
```

## Configuration

User config: `~/.config/voicepilot/config.toml`

Key settings:

```toml
[speech]
activation_mode = "wake_word"   # "wake_word" | "push_to_talk" | "always_on"
wake_word = "hey pilot"
whisper_model = "base.en"       # "tiny.en" | "base.en" | "small.en"
whisper_device = "cpu"

[ui]
overlay_position = "top-right"
theme = "dark"

[feedback]
tts_enabled = true
tts_engine = "espeak"
```

## Development

```bash
# Set up dev environment
./scripts/dev_setup.sh

# Run tests
pytest

# Lint
ruff check voicepilot/
mypy voicepilot/
```

## Adding a Command

1. Add an `Intent` to `voicepilot/parser/grammar.py`
2. Add a `BaseAction` subclass to `voicepilot/executor/`
3. Register the action in `voicepilot/app.py` under `_register_actions()`

## Adding a Plugin

Create `~/.local/share/voicepilot/plugins/my_plugin.py`:

```python
from voicepilot.plugins.base import BasePlugin
from voicepilot.parser.intent import Intent, IntentCategory, RiskLevel

class MyPlugin(BasePlugin):
    name = "my_plugin"
    version = "1.0.0"
    description = "My custom commands"

    def setup(self, interpreter, registry):
        # Add intents and actions
        interpreter.intents.append(Intent(
            name="my_command",
            category=IntentCategory.APP_CONTROL,
            patterns=["do the thing"],
            risk=RiskLevel.LOW,
        ))
        # registry.register(MyAction())
```

## Requirements

- **OS**: Debian-family Linux — Ubuntu 22.04+, Linux Mint 21+, Pop!_OS, Debian 12+
- **Desktop**: GNOME, Cinnamon, MATE, XFCE, or KDE. **X11 session recommended** —
  on Wayland, keyboard injection and window control are limited.
- **Python**: 3.10+
- **RAM**: 2 GB minimum (4 GB recommended with the base.en model)
- **Disk**: ~1 GB for models

`install.sh` detects the desktop environment and installs the matching
screenshot tool. Application names are resolved at runtime, so "open files"
launches `nautilus` on GNOME and `nemo` on Cinnamon without any config change.

### First run

Two models are downloaded on first launch and cached afterwards:

- the Whisper model named in `config.toml` (`base.en` is ~150 MB)
- the openwakeword wake-word models (~10 MB)

### Troubleshooting

**`Could not load the Qt platform plugin "xcb"`** — the Qt runtime libraries
are missing. `install.sh` installs them; to do it by hand:

```bash
sudo apt install libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0
```

**`The repository '…' does not have a Release file`** during install — an
unrelated third-party apt repository is misconfigured. The installer reports
which one and continues; VoicePilot does not need it. On Linux Mint this is
usually a repo added with Mint's codename (e.g. `xia`) instead of the Ubuntu
base it is built for (`noble`).

## License

MIT
