"""
Regressionstest för matchningsbuggen i CommandInterpreter._match().

Buggen: _pattern_to_regex() bygger regexet "^mönster(\\s+.*)?$", vilket
tillåter valfri efterföljande text. För slot-mönster (t.ex. "kör {app}")
är det rimligt — men för slot-lösa exaktfraser (t.ex. "kör") gjorde det
att de svalde efterföljande ord gratis och ändå behöll full specificitet
(1.0). Det gjorde att en kort exaktfras som "kör" kunde vinna över det
mer specifika slot-mönstret "kör {app}" när användaren sa "kör firefox",
trots att slot-mönstret är det korrekta valet.

Detta test säkerställer att en slot-lös exaktfras inte sväljer
efterföljande ord som borde landa i ett slot på ett konkurrerande mönster.
"""

from voicepilot.parser.interpreter import CommandInterpreter


def test_bare_verb_does_not_swallow_slot_value():
    """
    'kör' (slot-lös, vscode_run_project) ska INTE slå ut 'kör {app}'
    (open_application) bara för att den släpande gruppen i regexet
    tillåter efterföljande text.
    """
    interpreter = CommandInterpreter()

    cmd = interpreter.parse("kör firefox")

    assert cmd.intent_name == "open_application"
    assert cmd.slots.get("app") == "firefox"


def test_exact_phrase_still_matches_without_trailing_text():
    """Sanity check: den slot-lösa exaktfrasen ska fortfarande matcha rent."""
    interpreter = CommandInterpreter()

    cmd = interpreter.parse("kör projektet")

    assert cmd.intent_name == "vscode_run_project"


def test_exact_phrase_survives_a_single_filler_word():
    """
    Poängavdraget ska vara proportionellt — ett enstaka utfyllnadsord
    (typiskt för Whisper-transkription) ska inte automatiskt döda en
    annars korrekt exaktfras-matchning när inget mer specifikt mönster
    konkurrerar om samma text.
    """
    interpreter = CommandInterpreter()

    cmd = interpreter.parse("ta en skärmdump nu")

    assert cmd.intent_name == "take_screenshot"
