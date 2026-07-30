"""Unit tests for the risk classifier and confirmation manager."""

import time

import pytest

from voicepilot.confirmation.manager import ConfirmationManager
from voicepilot.confirmation.risk import RiskLevel, classify
from voicepilot.core.config import ConfirmationSection
from voicepilot.parser.interpreter import CommandInterpreter


@pytest.fixture
def interpreter():
    return CommandInterpreter()


@pytest.fixture
def conf_section():
    return ConfirmationSection(
        timeout_seconds=2,
        high_risk_phrase="confirm delete",
        medium_risk_phrase="confirm",
        cancel_phrase="cancel",
    )


def test_low_risk_executes_immediately(interpreter, conf_section):
    executed = []
    manager = ConfirmationManager(
        config=conf_section,
        on_execute=lambda cmd: executed.append(cmd.intent_name),
    )
    cmd = interpreter.parse("open firefox")
    assert classify(cmd) == RiskLevel.LOW
    manager.handle(cmd)
    assert "open_application" in executed


def test_medium_risk_requires_confirm(interpreter, conf_section):
    executed = []
    manager = ConfirmationManager(
        config=conf_section,
        on_execute=lambda cmd: executed.append(cmd.intent_name),
    )
    cmd = interpreter.parse("close firefox")
    manager.handle(cmd)

    assert manager.has_pending
    assert executed == []

    manager.receive_response("confirm")
    assert "close_application" in executed


def test_medium_risk_cancel(interpreter, conf_section):
    executed = []
    manager = ConfirmationManager(
        config=conf_section,
        on_execute=lambda cmd: executed.append(cmd.intent_name),
    )
    cmd = interpreter.parse("close firefox")
    manager.handle(cmd)
    manager.receive_response("cancel")

    assert not manager.has_pending
    assert executed == []


def test_high_risk_requires_full_phrase(interpreter, conf_section):
    executed = []
    manager = ConfirmationManager(
        config=conf_section,
        on_execute=lambda cmd: executed.append(cmd.intent_name),
    )
    cmd = interpreter.parse("delete folder old_projects")
    manager.handle(cmd)

    # Wrong phrase — should not execute
    manager.receive_response("confirm")
    assert executed == []
    assert manager.has_pending

    # Correct phrase
    manager.receive_response("confirm delete")
    assert "delete_folder" in executed


def test_confirmation_timeout(interpreter, conf_section):
    """After timeout_seconds, confirmation auto-cancels."""
    executed = []
    manager = ConfirmationManager(
        config=conf_section,
        on_execute=lambda cmd: executed.append(cmd.intent_name),
    )
    cmd = interpreter.parse("close firefox")
    manager.handle(cmd)

    # Wait for timeout (2 seconds in fixture)
    time.sleep(conf_section.timeout_seconds + 0.5)
    assert not manager.has_pending
    assert executed == []
