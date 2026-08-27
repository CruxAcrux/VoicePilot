"""Unit tests for the CommandInterpreter."""

import pytest

from voicepilot.core.exceptions import UnknownCommandError
from voicepilot.parser.intent import RiskLevel
from voicepilot.parser.interpreter import CommandInterpreter


@pytest.fixture
def interpreter() -> CommandInterpreter:
    return CommandInterpreter()


def test_open_application(interpreter):
    cmd = interpreter.parse("öppna firefox")
    assert cmd.intent_name == "open_application"
    assert cmd.slots.get("app") == "firefox"
    assert cmd.risk == RiskLevel.LOW


def test_open_application_synonym(interpreter):
    """'aktivera' ska mappas till 'öppna' via synonymexpansion."""
    cmd = interpreter.parse("aktivera terminalen")
    assert cmd.intent_name == "open_application"
    assert "terminal" in cmd.slots.get("app", "")


def test_close_application(interpreter):
    cmd = interpreter.parse("stäng firefox")
    assert cmd.intent_name == "close_application"
    assert cmd.risk == RiskLevel.MEDIUM


def test_create_folder(interpreter):
    cmd = interpreter.parse("skapa mapp Projekt")
    assert cmd.intent_name == "create_folder"
    assert cmd.slots.get("name", "").lower() == "projekt"


def test_create_file(interpreter):
    cmd = interpreter.parse("skapa fil anteckningar.txt")
    assert cmd.intent_name == "create_file"
    assert "anteckningar.txt" in cmd.slots.get("name", "")


def test_delete_folder_is_high_risk(interpreter):
    cmd = interpreter.parse("ta bort mapp gamla_projekt")
    assert cmd.intent_name == "delete_folder"
    assert cmd.risk == RiskLevel.HIGH


def test_shutdown_is_high_risk(interpreter):
    cmd = interpreter.parse("stäng av datorn")
    assert cmd.intent_name == "shutdown"
    assert cmd.risk == RiskLevel.HIGH


def test_start_dictation(interpreter):
    cmd = interpreter.parse("starta diktering")
    assert cmd.intent_name == "start_dictation"


def test_unknown_command_raises(interpreter):
    with pytest.raises(UnknownCommandError):
        interpreter.parse("xyzzy frobniculate the zorblax")


def test_go_to_line(interpreter):
    cmd = interpreter.parse("gå till rad 150")
    assert cmd.intent_name == "vscode_go_to_line"
    assert cmd.slots.get("line") == "150"


def test_confidence_is_reasonable(interpreter):
    cmd = interpreter.parse("öppna firefox")
    assert cmd.confidence >= 70


def test_fuzzy_match_typo(interpreter):
    """ASR-tolkningen kan innehålla små avvikelser — matchningen ska ändå gå igenom."""
    cmd = interpreter.parse("öppnaa firefox")
    assert cmd.intent_name == "open_application"


# ---------------------------------------------------------------------------
# Svenska kollisioner
#
# Dessa kommandon delar ord med ett annat, felaktigt intent (t.ex. "stäng av
# datorn" innehåller "stäng", som också är verbet för close_application och
# close_window). Grammatiken måste ge dem till rätt, mer specifika intent.
# ---------------------------------------------------------------------------

def test_shutdown_does_not_collide_with_close_application(interpreter):
    cmd = interpreter.parse("stäng av datorn")
    assert cmd.intent_name == "shutdown"


def test_restart_does_not_collide_with_open_application(interpreter):
    cmd = interpreter.parse("starta om datorn")
    assert cmd.intent_name == "restart"


def test_close_window_does_not_collide_with_close_application(interpreter):
    cmd = interpreter.parse("stäng fönstret")
    assert cmd.intent_name == "close_window"


def test_go_to_line_does_not_collide_with_switch_to_application(interpreter):
    cmd = interpreter.parse("gå till rad 150")
    assert cmd.intent_name == "vscode_go_to_line"


def test_open_folder_does_not_collide_with_open_application(interpreter):
    cmd = interpreter.parse("öppna mappen nedladdningar")
    assert cmd.intent_name == "open_folder"
    assert cmd.slots.get("folder") == "nedladdningar"


def test_delete_folder_does_not_collide_with_delete_file(interpreter):
    cmd = interpreter.parse("ta bort mapp gamla")
    assert cmd.intent_name == "delete_folder"


# ---------------------------------------------------------------------------
# Svensk böjning
# ---------------------------------------------------------------------------

def test_delete_file_accepts_both_radera_and_ta_bort(interpreter):
    for phrase in ("radera fil rapport.pdf", "ta bort fil rapport.pdf"):
        cmd = interpreter.parse(phrase)
        assert cmd.intent_name == "delete_file", phrase


def test_close_window_accepts_both_bestämd_and_obestämd_form(interpreter):
    for phrase in ("stäng fönster", "stäng fönstret"):
        cmd = interpreter.parse(phrase)
        assert cmd.intent_name == "close_window", phrase
