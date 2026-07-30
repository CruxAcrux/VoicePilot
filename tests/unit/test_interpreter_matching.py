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

Uppföljning — regression från det första poängavdraget
--------------------------------------------------------
Det ursprungliga poängavdraget (proportionellt mot andel ignorerade ord)
straffade ALLA slot-lösa träffar med släpande text, oavsett om det fanns
någon konkurrerande slot-variant eller inte. Det gjorde att helt vanliga
tvåordsfraser som "kopiera texten" eller "lås datorn tack" — där det INTE
finns någon konkurrerande "kopiera {x}"/"lås datorn {x}" — föll under
konfidenströskeln och blev OKÄNT, trots att de tidigare fungerade.

Fixen delar upp _match()-poängen i en grindpoäng (ostraffad, avgör om
kandidaten alls kvalificerar över tröskeln) och en rangordningspoäng
(straffad, avgör vem som vinner NÄR flera kandidater konkurrerar om
samma text). Testerna nedan täcker båda sidorna: att grindpoängen
släpper igenom ensamma exaktfras-kandidater med släpande text, och att
rangordningspoängen fortfarande låter ett mer specifikt slot-mönster
vinna när ett sådant faktiskt konkurrerar.
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


def test_exact_phrase_with_trailing_word_matches_when_no_slot_pattern_competes():
    """
    'kopiera texten' ska fortfarande ge vscode_copy. Grammatiken har ingen
    'kopiera {x}'-variant, så det finns inget mer specifikt mönster som
    "kopiera" borde förlora mot — den släpande texten ("texten") ska då
    inte kunna knuffa poängen under konfidenströskeln.

    Detta är precis den regression som uppstod när poängavdraget för
    släpande text (avsett för fall som "kör firefox") av misstag också
    tillämpades på grindbeslutet (tröskeln), inte bara på rangordningen.
    """
    interpreter = CommandInterpreter()

    cmd = interpreter.parse("kopiera texten")

    assert cmd.intent_name == "vscode_copy"


def test_exact_phrase_with_trailing_word_matches_for_other_short_verbs():
    """
    Samma sak för fler korta svenska verb som exponerade den ursprungliga
    buggen: 'spara', 'klistra in' och flerordsfrasen 'lås datorn'.
    Inget av dessa har en konkurrerande slot-variant i grammatiken, så
    ett enstaka efterföljande ord ska inte döda matchningen.
    """
    interpreter = CommandInterpreter()

    cmd = interpreter.parse("spara dokumentet")
    assert cmd.intent_name == "vscode_save_file"

    cmd = interpreter.parse("klistra in texten")
    assert cmd.intent_name == "vscode_paste"

    cmd = interpreter.parse("lås datorn tack")
    assert cmd.intent_name == "lock_computer"
