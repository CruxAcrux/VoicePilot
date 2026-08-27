"""
Plugin loader — discovers and loads BasePlugin subclasses.

Search paths (in order):
  1. User plugins: ~/.local/share/voicepilot/plugins/
  2. System plugins: /usr/share/voicepilot/plugins/
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path

from voicepilot.core.exceptions import PluginError, PluginNotFoundError
from voicepilot.plugins.base import BasePlugin

logger = logging.getLogger(__name__)

_SEARCH_PATHS = [
    Path("~/.local/share/voicepilot/plugins").expanduser(),
    Path("/usr/share/voicepilot/plugins"),
]


class PluginLoader:
    """Discovers, loads, and manages VoicePilot plugins."""

    def __init__(self, extra_paths: list[Path] | None = None) -> None:
        self._search_paths: list[Path] = list(_SEARCH_PATHS)
        if extra_paths:
            self._search_paths = list(extra_paths) + self._search_paths

        self._loaded: dict[str, BasePlugin] = {}

    def discover(self) -> list[str]:
        """
        Scan search paths for plugin modules.

        Returns a list of discovered plugin names (module stem names).
        """
        found: list[str] = []
        for path in self._search_paths:
            if not path.exists():
                continue
            for item in sorted(path.iterdir()):
                if item.suffix == ".py" and not item.name.startswith("_"):
                    found.append(item.stem)
                elif item.is_dir() and (item / "__init__.py").exists():
                    found.append(item.name)
        logger.info("Discovered %d plugin(s): %s", len(found), found)
        return found

    def load(self, name: str) -> BasePlugin:
        """
        Load and instantiate a plugin by name.

        Raises
        ------
        PluginNotFoundError
            If no module matching *name* is found.
        PluginError
            If the module cannot be imported or contains no BasePlugin subclass.
        """
        if name in self._loaded:
            return self._loaded[name]

        module_path = self._find_module(name)
        if module_path is None:
            raise PluginNotFoundError(name)

        try:
            spec = importlib.util.spec_from_file_location(f"vp_plugin_{name}", module_path)
            if spec is None or spec.loader is None:
                raise PluginError(f"Cannot create module spec for {module_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[f"vp_plugin_{name}"] = module
            spec.loader.exec_module(module)  # type: ignore[union-attr]

        except Exception as exc:
            raise PluginError(f"Failed to import plugin {name!r}: {exc}") from exc

        # Find BasePlugin subclass in the module
        plugin_class: type[BasePlugin] | None = None
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, BasePlugin)
                and obj is not BasePlugin
            ):
                plugin_class = obj
                break

        if plugin_class is None:
            raise PluginError(f"No BasePlugin subclass found in plugin {name!r}")

        instance = plugin_class()
        self._loaded[name] = instance
        logger.info("Loaded plugin: %r", instance)
        return instance

    def load_all(self) -> list[BasePlugin]:
        """Load all discovered plugins."""
        plugins: list[BasePlugin] = []
        for name in self.discover():
            try:
                plugins.append(self.load(name))
            except PluginError:
                logger.exception("Failed to load plugin %r — skipping", name)
        return plugins

    def unload(self, name: str) -> None:
        """Unload a plugin, calling its teardown method."""
        plugin = self._loaded.pop(name, None)
        if plugin:
            try:
                plugin.teardown()
            except Exception:
                logger.exception("Error in teardown of plugin %r", name)

    def _find_module(self, name: str) -> Path | None:
        for search_path in self._search_paths:
            candidates = [
                search_path / f"{name}.py",
                search_path / name / "__init__.py",
            ]
            for candidate in candidates:
                if candidate.exists():
                    return candidate
        return None

    @property
    def loaded_plugins(self) -> dict[str, BasePlugin]:
        return dict(self._loaded)
