"""
System-level actions.

Handles:
  - lock_computer
  - shutdown
  - restart
  - volume_up
  - volume_down
  - volume_mute
  - take_screenshot
"""

from __future__ import annotations

import logging
import shutil
import subprocess

from voicepilot.core.desktop import (
    LOCK_COMMANDS,
    SCREENSHOT_COMMANDS,
    first_available,
)
from voicepilot.core.exceptions import ExecutorError, ShellCommandBlockedError
from voicepilot.executor.base import BaseAction
from voicepilot.parser.intent import ParsedCommand

logger = logging.getLogger(__name__)


def _run_safe(args: list[str], whitelist: list[str]) -> None:
    """Run a subprocess command if the binary is on the whitelist."""
    cmd = args[0]
    if cmd not in whitelist:
        raise ShellCommandBlockedError(cmd)
    logger.info("Executing: %s", " ".join(args))
    subprocess.run(args, check=True, timeout=10)


class SystemAction(BaseAction):
    """Executes system-level commands."""

    handles = [
        "lock_computer",
        "shutdown",
        "restart",
        "volume_up",
        "volume_down",
        "volume_mute",
        "take_screenshot",
    ]

    def __init__(self, shell_whitelist: list[str]) -> None:
        self.whitelist = shell_whitelist

    def execute(self, command: ParsedCommand) -> None:
        intent = command.intent_name

        dispatch = {
            "lock_computer": self._lock,
            "shutdown": self._shutdown,
            "restart": self._restart,
            "volume_up": self._volume_up,
            "volume_down": self._volume_down,
            "volume_mute": self._volume_mute,
            "take_screenshot": self._screenshot,
        }

        handler = dispatch.get(intent)
        if handler:
            handler()

    def _lock(self) -> None:
        """
        Lock the screen using whichever locker this desktop provides.

        loginctl comes first because it works regardless of desktop, but it is
        a no-op under some session managers, so desktop-specific lockers
        (Cinnamon, MATE, XFCE, KDE) follow as fallbacks.
        """
        argv = first_available(LOCK_COMMANDS)
        if argv is None:
            raise ExecutorError(
                "Cannot lock screen: no supported screen locker found "
                "(tried loginctl, the desktop screensaver commands, and xdg-screensaver)"
            )

        # loginctl and friends are whitelisted; the rest are fixed, argument-free
        # commands built here rather than from user input.
        if argv[0] in self.whitelist:
            _run_safe(argv, self.whitelist)
        else:
            logger.info("Executing: %s", " ".join(argv))
            subprocess.run(argv, check=True, timeout=10)

        logger.info("Screen locked")

    def _shutdown(self) -> None:
        _run_safe(["systemctl", "poweroff"], self.whitelist)

    def _restart(self) -> None:
        _run_safe(["systemctl", "reboot"], self.whitelist)

    def _volume_up(self) -> None:
        self._amixer("5%+")

    def _volume_down(self) -> None:
        self._amixer("5%-")

    def _volume_mute(self) -> None:
        # pactl is tried first: it drives PulseAudio and PipeWire alike, whereas
        # `amixer -D pulse` needs the PulseAudio ALSA plugin, which is absent on
        # PipeWire-only systems.
        self._try_audio_commands(
            [
                ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"],
                ["amixer", "-D", "pulse", "sset", "Master", "toggle"],
                ["amixer", "sset", "Master", "toggle"],
            ],
            description="mute toggle",
        )

    def _amixer(self, delta: str) -> None:
        sign = "+" if "+" in delta else "-"
        val = delta.replace("+", "").replace("-", "")

        self._try_audio_commands(
            [
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{sign}{val}"],
                ["amixer", "-D", "pulse", "sset", "Master", delta],
                ["amixer", "sset", "Master", delta],
            ],
            description=f"volume {delta}",
        )

    @staticmethod
    def _try_audio_commands(commands: list[list[str]], description: str) -> None:
        """Run the first audio command that exists and succeeds."""
        for argv in commands:
            if not shutil.which(argv[0]):
                continue
            result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.info("Applied %s via %s", description, argv[0])
                return
            logger.debug(
                "%s failed (rc=%d): %s", argv[0], result.returncode, result.stderr.strip()
            )

        raise ExecutorError(
            f"Could not apply {description}: no working audio control found "
            "(install pulseaudio-utils or alsa-utils)"
        )

    def _screenshot(self) -> None:
        argv = first_available(SCREENSHOT_COMMANDS)
        if argv is None:
            raise ExecutorError(
                "No screenshot tool found "
                "(install gnome-screenshot, xfce4-screenshooter, spectacle, or scrot)"
            )
        subprocess.Popen(argv, start_new_session=True)
        logger.info("Screenshot tool launched: %s", argv[0])
