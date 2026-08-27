#!/usr/bin/env bash
# =============================================================================
# VoicePilot Install Script
# Installs system-level dependencies on Debian-family systems
# (Ubuntu, Linux Mint, Pop!_OS, Debian, elementary, Zorin …)
# =============================================================================

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
RESET="\033[0m"

info()    { echo -e "${GREEN}[INFO]${RESET}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
heading() { echo -e "\n${BOLD}$*${RESET}"; }

# Run from the project root regardless of where the script was invoked.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# =============================================================================
# Pre-checks
# =============================================================================

heading "VoicePilot — System Dependency Installer"

if [[ "$EUID" -eq 0 ]]; then
    error "Do not run this script as root. It will use sudo when needed."
    exit 1
fi

if ! command -v apt-get &>/dev/null; then
    error "This script requires apt-get (Debian family). Other distributions require manual setup."
    exit 1
fi

# --- Distribution identification ---------------------------------------------
# Linux Mint reports its own codename (e.g. "xia"), which does not exist in
# Ubuntu's or third-party archives. UBUNTU_CODENAME in /etc/os-release carries
# the Ubuntu base ("noble") and is what any archive should be keyed on.
DISTRO_ID="unknown"
DISTRO_NAME="unknown"
APT_CODENAME=""    # Ubuntu/Debian base, e.g. "noble" — what archives are keyed on
LOCAL_CODENAME=""  # This distro's own codename, e.g. Mint's "xia"

if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    DISTRO_ID="${ID:-unknown}"
    DISTRO_NAME="${PRETTY_NAME:-$DISTRO_ID}"
    LOCAL_CODENAME="${VERSION_CODENAME:-}"
    APT_CODENAME="${UBUNTU_CODENAME:-${DEBIAN_CODENAME:-$LOCAL_CODENAME}}"
fi

info "Distribution: ${DISTRO_NAME}"
[[ -n "$APT_CODENAME" ]] && info "Package base: ${APT_CODENAME}"

# --- Python version ----------------------------------------------------------
if ! command -v python3 &>/dev/null; then
    error "python3 not found. Install it with: sudo apt install python3 python3-venv"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PYTHON_MAJOR=${PYTHON_VERSION%%.*}
PYTHON_MINOR=${PYTHON_VERSION##*.}

# Compare as a single number so 3.9 < 3.10 < 4.0 all order correctly.
if (( PYTHON_MAJOR * 100 + PYTHON_MINOR < 310 )); then
    error "Python 3.10+ is required. Found: Python ${PYTHON_VERSION}"
    info "Install with: sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt install python3.10"
    exit 1
fi

info "Python ${PYTHON_VERSION} ✓"

# =============================================================================
# System packages
# =============================================================================

heading "Installing system packages…"

# Packages required on every desktop.
PACKAGES=(
    # Audio capture (PortAudio backs the sounddevice module)
    portaudio19-dev
    libportaudio2
    # X11 keyboard/window control and clipboard
    xdotool
    wmctrl
    xclip
    # Text-to-speech
    espeak-ng
    # File search index
    plocate
    # Python build/runtime headers
    python3-dev
    python3-venv
    python3-pip
    # DBus
    libdbus-1-dev
    # Volume control — pactl covers PulseAudio and PipeWire, amixer covers ALSA
    pulseaudio-utils
    alsa-utils
    # Qt "xcb" platform plugin runtime libraries. PyQt6 wheels bundle Qt itself
    # but not these; without them the GUI aborts at startup with
    # "Could not load the Qt platform plugin xcb". libxcb-cursor0 in particular
    # became mandatory in Qt 6.5 and is not installed by default.
    libxcb-cursor0
    libxcb-xinerama0
    libxcb-icccm4
    libxcb-image0
    libxcb-keysyms1
    libxcb-randr0
    libxcb-render-util0
    libxcb-shape0
    libxkbcommon-x11-0
    libegl1
)

# Desktop-specific screenshot tool. VoicePilot falls back across several at
# runtime, but installing the native one keeps behaviour consistent.
case "${XDG_CURRENT_DESKTOP,,}" in
    *kde*|*plasma*) PACKAGES+=(spectacle) ;;
    *xfce*)         PACKAGES+=(xfce4-screenshooter) ;;
    *)              PACKAGES+=(gnome-screenshot) ;;
esac

# --- Refresh package lists ---------------------------------------------------
# A failure here is usually an unrelated third-party repository (VS Code,
# Docker, Microsoft …) that is misconfigured or offline. That must not abort
# the install: the Ubuntu/Mint archives VoicePilot needs are typically fine.
info "Updating package lists…"
APT_UPDATE_LOG=$(mktemp)
trap 'rm -f "$APT_UPDATE_LOG"' EXIT

sudo apt-get update 2>&1 | tee "$APT_UPDATE_LOG" || true

BROKEN_REPOS=$(grep -oP "The repository '\K[^']+" "$APT_UPDATE_LOG" | sort -u || true)

if [[ -n "$BROKEN_REPOS" ]]; then
    warn "Some third-party repositories could not be read and will be ignored:"
    while IFS= read -r repo; do
        echo "         • $repo"
    done <<< "$BROKEN_REPOS"

    # The classic cause on Linux Mint: a repo was added using Mint's own
    # codename (e.g. "xia") rather than the Ubuntu base it is built for
    # ("noble"), so the archive has no matching Release file.
    if [[ -n "$LOCAL_CODENAME" && "$LOCAL_CODENAME" != "$APT_CODENAME" ]] \
       && grep -q "$LOCAL_CODENAME" <<< "$BROKEN_REPOS"; then
        warn "These use this system's codename '${LOCAL_CODENAME}' instead of the Ubuntu base '${APT_CODENAME}'."
        warn "VoicePilot does not need them. To repair one:"
        echo "         sudo sed -i 's/${LOCAL_CODENAME}/${APT_CODENAME}/g' /etc/apt/sources.list.d/<file>.list"
        echo "         # …or disable it:  sudo mv /etc/apt/sources.list.d/<file>.list{,.disabled}"
    fi
    echo ""
fi

# --- Filter to packages this release actually has ----------------------------
# Package names drift between releases; one missing name must not prevent the
# rest from installing.
AVAILABLE=()
MISSING=()
for pkg in "${PACKAGES[@]}"; do
    if apt-cache show "$pkg" &>/dev/null; then
        AVAILABLE+=("$pkg")
    else
        MISSING+=("$pkg")
    fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    warn "Not available on this release, skipping: ${MISSING[*]}"
fi

if [[ ${#AVAILABLE[@]} -eq 0 ]]; then
    error "No required packages are available. Check your apt sources."
    exit 1
fi

info "Installing: ${AVAILABLE[*]}"
if ! sudo apt-get install -y --no-install-recommends "${AVAILABLE[@]}"; then
    error "Package installation failed."
    info "If the failure names a third-party repository, disable it and re-run:"
    info "  sudo mv /etc/apt/sources.list.d/<file>.list{,.disabled}"
    exit 1
fi

info "System packages installed ✓"

# =============================================================================
# Python virtual environment
# =============================================================================

heading "Setting up Python virtual environment…"

VENV_DIR="$PROJECT_ROOT/.venv"
VENV_PY="$VENV_DIR/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
    if [[ -e "$VENV_DIR" ]]; then
        warn "$VENV_DIR exists but has no usable interpreter — recreating it"
        rm -rf "$VENV_DIR"
    fi
    python3 -m venv "$VENV_DIR"
    info "Virtual environment created at $VENV_DIR"
else
    info "Virtual environment already exists ($("$VENV_PY" --version))"
fi

# Virtual environments created by `uv venv` ship without pip. Without this,
# `pip install` would silently fall through to the system pip, which on
# Ubuntu 24.04 / Mint 22 refuses to install into an externally-managed
# environment.
if ! "$VENV_PY" -m pip --version &>/dev/null; then
    info "pip is missing from the virtual environment — bootstrapping it"
    if ! "$VENV_PY" -m ensurepip --upgrade &>/dev/null; then
        warn "ensurepip is unavailable; falling back to get-pip.py"
        curl -fsSL https://bootstrap.pypa.io/get-pip.py | "$VENV_PY" - \
            || { error "Could not bootstrap pip into $VENV_DIR"; exit 1; }
    fi
fi

# Everything below installs through the venv's own interpreter, so no
# `activate` is needed and the correct environment is guaranteed.
PIP=("$VENV_PY" -m pip)

"${PIP[@]}" install --upgrade pip wheel setuptools --quiet

# =============================================================================
# Python dependencies
# =============================================================================

heading "Installing Python dependencies…"

if [[ ! -f "requirements.txt" ]]; then
    error "requirements.txt not found in $PROJECT_ROOT"
    exit 1
fi

"${PIP[@]}" install -r requirements.txt
info "Python dependencies installed ✓"

heading "Installing VoicePilot…"

"${PIP[@]}" install -e ".[dev]"
info "VoicePilot installed in editable mode ✓"

# =============================================================================
# User directories and config
# =============================================================================

heading "Creating user directories…"

CONFIG_DIR="$HOME/.config/voicepilot"
DATA_DIR="$HOME/.local/share/voicepilot"
LOG_DIR="$DATA_DIR/logs"
MODELS_DIR="$PROJECT_ROOT/models"

mkdir -p "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR" "$MODELS_DIR"
info "Config dir: $CONFIG_DIR"
info "Data dir:   $DATA_DIR"
info "Models dir: $MODELS_DIR"

if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
    cp "config/default.toml" "$CONFIG_DIR/config.toml"
    info "Default config copied to $CONFIG_DIR/config.toml"
else
    info "User config already exists — not overwriting"
fi

# =============================================================================
# File search index
# =============================================================================

heading "Updating file search index…"

if command -v updatedb &>/dev/null; then
    info "Running updatedb (this may take a moment)…"
    sudo updatedb || warn "updatedb failed — file search will fall back to 'find'"
else
    warn "updatedb not found — file search will fall back to 'find'"
fi

# =============================================================================
# Desktop entry
# =============================================================================

heading "Installing desktop entry…"

DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_DIR/voicepilot.desktop" <<DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=VoicePilot
Comment=Voice-controlled Linux desktop assistant
Exec=${VENV_DIR}/bin/voicepilot
Icon=audio-input-microphone
Terminal=false
Categories=Accessibility;Utility;
Keywords=voice;accessibility;speech;
StartupNotify=false
DESKTOP

info "Desktop entry created at $DESKTOP_DIR/voicepilot.desktop"

# =============================================================================
# Final checks
# =============================================================================

heading "Checking system tools…"

check_tool() {
    if command -v "$1" &>/dev/null; then
        info "$1 ✓"
    else
        warn "$1 not found — $2"
    fi
}

check_tool xdotool "dictation will fall back to clipboard paste"
check_tool wmctrl  "window focus/switch commands will be limited"
check_tool xclip   "clipboard fallback for dictation unavailable"
check_tool espeak-ng "spoken feedback unavailable"
check_tool locate  "file search will fall back to 'find'"
check_tool pactl   "volume control will fall back to amixer"

# Confirm the app imports and its dependencies resolve.
if "$VENV_PY" -c "import voicepilot, voicepilot.core.config as c; c.load_config()" &>/dev/null; then
    info "VoicePilot imports and config loads ✓"
else
    error "VoicePilot failed to import or load its config. Run for details:"
    error "  $VENV_PY -c 'import voicepilot.core.config as c; c.load_config()'"
    exit 1
fi

DESKTOP_ENV="${XDG_CURRENT_DESKTOP:-unknown}"
SESSION_TYPE="${XDG_SESSION_TYPE:-unknown}"
info "Desktop: ${DESKTOP_ENV} (${SESSION_TYPE} session)"

if [[ "${SESSION_TYPE,,}" == "wayland" ]]; then
    warn "Wayland detected. Keyboard injection and window control are limited;"
    warn "log in to an X11/Xorg session for full functionality."
fi

# =============================================================================
# Done
# =============================================================================

echo ""
echo -e "${GREEN}${BOLD}════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  VoicePilot installed successfully!${RESET}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════${RESET}"
echo ""
echo "  Activate the virtual environment:"
echo "    source .venv/bin/activate"
echo ""
echo "  Start VoicePilot:"
echo "    voicepilot"
echo ""
echo "  Debug mode (verbose output):"
echo "    voicepilot --debug"
echo ""
echo "  Headless mode (no GUI):"
echo "    voicepilot --no-ui"
echo ""
echo "  Config file:"
echo "    $CONFIG_DIR/config.toml"
echo ""
