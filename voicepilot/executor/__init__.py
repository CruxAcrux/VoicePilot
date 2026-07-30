"""Executor package."""

from voicepilot.executor.app_launcher import AppLauncherAction
from voicepilot.executor.base import BaseAction
from voicepilot.executor.file_manager import FileManagerAction
from voicepilot.executor.keyboard import KeyboardAction, keyboard
from voicepilot.executor.registry import ActionRegistry
from voicepilot.executor.shell import SystemAction
from voicepilot.executor.window_manager import WindowManagerAction

__all__ = [
    "BaseAction",
    "ActionRegistry",
    "AppLauncherAction",
    "FileManagerAction",
    "WindowManagerAction",
    "KeyboardAction",
    "keyboard",
    "SystemAction",
]
