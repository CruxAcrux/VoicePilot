"""Unit tests for the risk classifier and confirmation manager."""

import time

import pytest

from voicepilot.confirmation.manager import ConfirmationManager
from voicepilot.confirmation.risk import RiskLevel, classify, risk_message
from voicepilot.core.config import ConfirmationSection
from voicepilot.parser.interpreter import CommandInterpreter


@pytest.fixture
def interpreter():
    return CommandInterpreter()


@pytest.fixture
def conf_section():
    return ConfirmationSection(
        timeout_seconds=2,
        high_risk_phrase="bekräfta radera",
        medium_risk_phrase="bekräfta",
        cancel_phrase="avbryt",
    )


def test_low_risk_executes_immediately(interpreter, conf_section):
    executed = []
    manager = ConfirmationManager(
        config=conf_section,
        on_execute=lambda cmd: executed.append(cmd.intent_name),
    )
    cmd = interpreter.parse("öppna firefox")
    assert classify(cmd) == RiskLevel.LOW
    manager.handle(cmd)
    assert "open_application" in executed


def test_medium_risk_requires_confirm(interpreter, conf_section):
    executed = []
    manager = ConfirmationManager(
        config=conf_section,
        on_execute=lambda cmd: executed.append(cmd.intent_name),
    )
    cmd = interpreter.parse("stäng firefox")
    manager.handle(cmd)

    assert manager.has_pending
    assert executed == []

    manager.receive_response("bekräfta")
    assert "close_application" in executed


def test_medium_risk_cancel(interpreter, conf_section):
    executed = []
    manager = ConfirmationManager(
        config=conf_section,
        on_execute=lambda cmd: executed.append(cmd.intent_name),
    )
    cmd = interpreter.parse("stäng firefox")
    manager.handle(cmd)
    manager.receive_response("avbryt")

    assert not manager.has_pending
    assert executed == []


def test_high_risk_requires_full_phrase(interpreter, conf_section):
    executed = []
    manager = ConfirmationManager(
        config=conf_section,
        on_execute=lambda cmd: executed.append(cmd.intent_name),
    )
    cmd = interpreter.parse("ta bort mapp gamla_projekt")
    manager.handle(cmd)

    # Fel fras — ska inte utföras
    manager.receive_response("bekräfta")
    assert executed == []
    assert manager.has_pending

    # Korrekt fras
    manager.receive_response("bekräfta radera")
    assert "delete_folder" in executed


def test_confirmation_timeout(interpreter, conf_section):
    """Efter timeout_seconds avbryts bekräftelsen automatiskt."""
    executed = []
    manager = ConfirmationManager(
        config=conf_section,
        on_execute=lambda cmd: executed.append(cmd.intent_name),
    )
    cmd = interpreter.parse("stäng firefox")
    manager.handle(cmd)

    # Vänta ut timeouten (2 sekunder i fixturen)
    time.sleep(conf_section.timeout_seconds + 0.5)
    assert not manager.has_pending
    assert executed == []


# ---------------------------------------------------------------------------
# Svenska talade svar
# ---------------------------------------------------------------------------

def test_risk_message_uses_configured_swedish_phrases(interpreter, conf_section):
    cmd = interpreter.parse("stäng firefox")
    risk = classify(cmd)
    message = risk_message(cmd, risk, conf_section)

    assert conf_section.medium_risk_phrase in message
    assert conf_section.cancel_phrase in message
    # Inga kvarvarande engelska bekräftelsefraser
    assert "confirm" not in message.lower()
    assert "cancel" not in message.lower()


def test_risk_message_high_risk_uses_configured_swedish_phrases(interpreter, conf_section):
    cmd = interpreter.parse("ta bort mapp gamla_projekt")
    risk = classify(cmd)
    message = risk_message(cmd, risk, conf_section)

    assert conf_section.high_risk_phrase in message
    assert conf_section.cancel_phrase in message
    assert "confirm" not in message.lower()
    assert "cancel" not in message.lower()
