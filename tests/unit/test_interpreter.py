"""Unit tests for the CommandInterpreter."""

import pytest

from voicepilot.core.exceptions import UnknownCommandError
from voicepilot.parser.intent import RiskLevel
from voicepilot.parser.interpreter import CommandInterpreter


@pytest.fixture
def interpreter() -> CommandInterpreter:
    return CommandInterpreter()


def test_open_application(interpreter):
    cmd = interpreter.parse("open firefox")
    assert cmd.intent_name == "open_application"
    assert cmd.slots.get("app") == "firefox"
    assert cmd.risk == RiskLevel.LOW


def test_open_application_synonym(interpreter):
    """'launch' should map to 'open' via synonym expansion."""
    cmd = interpreter.parse("launch terminal")
    assert cmd.intent_name == "open_application"
    assert "terminal" in cmd.slots.get("app", "")


def test_close_application(interpreter):
    cmd = interpreter.parse("close firefox")
    assert cmd.intent_name == "close_application"
    assert cmd.risk == RiskLevel.MEDIUM


def test_create_folder(interpreter):
    cmd = interpreter.parse("create folder Projects")
    assert cmd.intent_name == "create_folder"
    assert cmd.slots.get("name", "").lower() == "projects"


def test_create_file(interpreter):
    cmd = interpreter.parse("create file notes.txt")
    assert cmd.intent_name == "create_file"
    assert "notes.txt" in cmd.slots.get("name", "")


def test_delete_folder_is_high_risk(interpreter):
    cmd = interpreter.parse("delete folder old_projects")
    assert cmd.intent_name == "delete_folder"
    assert cmd.risk == RiskLevel.HIGH


def test_shutdown_is_high_risk(interpreter):
    cmd = interpreter.parse("shutdown")
    assert cmd.intent_name == "shutdown"
    assert cmd.risk == RiskLevel.HIGH


def test_start_dictation(interpreter):
    cmd = interpreter.parse("start dictation")
    assert cmd.intent_name == "start_dictation"


def test_unknown_command_raises(interpreter):
    with pytest.raises(UnknownCommandError):
        interpreter.parse("xyzzy frobniculate the zorblax")


def test_go_to_line(interpreter):
    cmd = interpreter.parse("go to line 150")
    assert cmd.intent_name == "vscode_go_to_line"
    assert cmd.slots.get("line") == "150"


def test_confidence_is_reasonable(interpreter):
    cmd = interpreter.parse("open firefox")
    assert cmd.confidence >= 70


def test_fuzzy_match_typo(interpreter):
    """ASR might produce slight variations — should still match."""
    cmd = interpreter.parse("openn firefox")
    assert cmd.intent_name == "open_application"
