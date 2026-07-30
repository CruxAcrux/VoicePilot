"""Shared test fixtures and configuration."""

import pytest

from voicepilot.core.config import AppConfig
from voicepilot.core.events import EventBus


@pytest.fixture
def config() -> AppConfig:
    """Return a default AppConfig for testing."""
    return AppConfig()


@pytest.fixture
def fresh_bus() -> EventBus:
    """Return a clean EventBus for each test."""
    from voicepilot.core.events import EventBus
    return EventBus()
