"""
Kommandogrammatik — definierar varje intent som VoicePilot förstår.

Varje Intent har en eller flera mönstermallar.  Slot-namn står i
{klamrar}.  Interpretern extraherar slot-värden ur den matchade delen
av transkriptionen.

Att lägga till ett nytt kommando är lika enkelt som att lägga till en
ny Intent-post här.
"""

from __future__ import annotations

from voicepilot.parser.intent import Intent, IntentCategory, RiskLevel

# ---------------------------------------------------------------------------
# Applikationsstyrning
# ---------------------------------------------------------------------------

INTENT_OPEN_APP = Intent(
    name="open_application",
    category=IntentCategory.APP_CONTROL,
    patterns=[
        "öppna {app}",
        "starta {app}",
        "kör {app}",
    ],
    required_slots=["app"],
    risk=RiskLevel.LOW,
    description="Öppna en applikation med namn.",
    examples=["öppna firefox", "starta terminalen", "kör vs code"],
)

INTENT_CLOSE_APP = Intent(
    name="close_application",
    category=IntentCategory.APP_CONTROL,
    patterns=[
        "stäng {app}",
        "avsluta {app}",
    ],
    required_slots=["app"],
    risk=RiskLevel.MEDIUM,
    description="Stäng en körande applikation.",
    examples=["stäng firefox", "avsluta terminalen"],
)

INTENT_SWITCH_APP = Intent(
    name="switch_to_application",
    category=IntentCategory.APP_CONTROL,
    patterns=[
        "växla till {app}",
        "gå till {app}",
        "fokusera {app}",
        "visa {app}",
    ],
    required_slots=["app"],
    risk=RiskLevel.LOW,
    description="Växla fokus till en körande applikation.",
    examples=["växla till terminalen", "fokusera vs code"],
)

# ---------------------------------------------------------------------------
# Filhantering
# ---------------------------------------------------------------------------

INTENT_OPEN_FOLDER = Intent(
    name="open_folder",
    category=IntentCategory.FILE_MANAGEMENT,
    patterns=[
        "öppna mappen {folder}",
        "öppna mapp {folder}",
        "visa mappen {folder}",
        "gå till mappen {folder}",
    ],
    required_slots=["folder"],
    risk=RiskLevel.LOW,
    description="Öppna en mapp i filhanteraren.",
    examples=["öppna mappen nedladdningar", "visa mappen dokument"],
)

INTENT_CREATE_FOLDER = Intent(
    name="create_folder",
    category=IntentCategory.FILE_MANAGEMENT,
    patterns=[
        "skapa mapp {name}",
        "skapa en mapp som heter {name}",
        "skapa mappen {name}",
        "ny mapp {name}",
    ],
    required_slots=["name"],
    risk=RiskLevel.LOW,
    description="Skapa en ny mapp.",
    examples=["skapa mapp Projekt", "ny mapp säkerhetskopior"],
)

INTENT_CREATE_FILE = Intent(
    name="create_file",
    category=IntentCategory.FILE_MANAGEMENT,
    patterns=[
        "skapa fil {name}",
        "skapa en fil som heter {name}",
        "skapa filen {name}",
        "ny fil {name}",
        "gör fil {name}",
    ],
    required_slots=["name"],
    risk=RiskLevel.LOW,
    description="Skapa en ny tom fil.",
    examples=["skapa fil anteckningar.txt", "ny fil readme.md"],
)

INTENT_DELETE_FILE = Intent(
    name="delete_file",
    category=IntentCategory.FILE_MANAGEMENT,
    patterns=[
        "radera fil {name}",
        "ta bort fil {name}",
        "radera filen {name}",
        "ta bort filen {name}",
        "radera {name}",
    ],
    required_slots=["name"],
    risk=RiskLevel.MEDIUM,
    description="Radera en fil.",
    examples=["radera fil anteckningar.txt", "ta bort filen rapport.pdf"],
)

INTENT_DELETE_FOLDER = Intent(
    name="delete_folder",
    category=IntentCategory.FILE_MANAGEMENT,
    patterns=[
        "radera mapp {name}",
        "radera mappen {name}",
        "ta bort mapp {name}",
        "ta bort mappen {name}",
    ],
    required_slots=["name"],
    risk=RiskLevel.HIGH,
    description="Radera en mapp och allt dess innehåll.",
    examples=["radera mapp gamla_projekt", "ta bort mappen gamla"],
)

INTENT_SEARCH_FILE = Intent(
    name="search_file",
    category=IntentCategory.FILE_MANAGEMENT,
    patterns=[
        "sök efter {name}",
        "sök {name}",
        "hitta filen {name}",
        "hitta {name}",
        "leta efter {name}",
        "var är {name}",
    ],
    required_slots=["name"],
    risk=RiskLevel.LOW,
    description="Sök efter en fil eller mapp.",
    examples=["sök efter rapport.pdf", "hitta anteckningar.txt"],
)

# ---------------------------------------------------------------------------
# Fönsterstyrning
# ---------------------------------------------------------------------------

INTENT_MINIMIZE_WINDOW = Intent(
    name="minimize_window",
    category=IntentCategory.WINDOW_CONTROL,
    patterns=[
        "minimera fönster",
        "minimera fönstret",
        "minimera {app}",
        "dölj fönster",
        "minimera detta",
    ],
    optional_slots=["app"],
    risk=RiskLevel.LOW,
    description="Minimera det aktuella eller angivna fönstret.",
    examples=["minimera fönster", "minimera firefox"],
)

INTENT_MAXIMIZE_WINDOW = Intent(
    name="maximize_window",
    category=IntentCategory.WINDOW_CONTROL,
    patterns=[
        "maximera fönster",
        "maximera fönstret",
        "maximera {app}",
        "helskärm",
        "fullskärm",
    ],
    optional_slots=["app"],
    risk=RiskLevel.LOW,
    description="Maximera det aktuella eller angivna fönstret.",
    examples=["maximera fönster", "fullskärm"],
)

INTENT_CLOSE_WINDOW = Intent(
    name="close_window",
    category=IntentCategory.WINDOW_CONTROL,
    patterns=[
        "stäng fönster",
        "stäng fönstret",
        "stäng detta fönster",
        "stäng aktuellt fönster",
        "stäng nuvarande fönster",
    ],
    risk=RiskLevel.MEDIUM,
    description="Stäng det fönster som har fokus.",
    examples=["stäng fönster", "stäng fönstret"],
)

INTENT_MOVE_WORKSPACE_LEFT = Intent(
    name="move_workspace_left",
    category=IntentCategory.WINDOW_CONTROL,
    patterns=["arbetsyta vänster", "gå vänster", "föregående arbetsyta"],
    risk=RiskLevel.LOW,
    description="Växla till arbetsytan till vänster.",
    examples=["arbetsyta vänster"],
)

INTENT_MOVE_WORKSPACE_RIGHT = Intent(
    name="move_workspace_right",
    category=IntentCategory.WINDOW_CONTROL,
    patterns=["arbetsyta höger", "gå höger", "nästa arbetsyta"],
    risk=RiskLevel.LOW,
    description="Växla till arbetsytan till höger.",
    examples=["arbetsyta höger"],
)

# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

INTENT_LOCK_COMPUTER = Intent(
    name="lock_computer",
    category=IntentCategory.SYSTEM,
    patterns=[
        "lås dator",
        "lås datorn",
        "lås skärmen",
        "lås min dator",
    ],
    risk=RiskLevel.MEDIUM,
    description="Lås datorns skärm.",
    examples=["lås datorn", "lås skärmen"],
)

INTENT_SHUTDOWN = Intent(
    name="shutdown",
    category=IntentCategory.SYSTEM,
    patterns=[
        "stäng av datorn",
        "stäng av",
        "stäng ner datorn",
        "slå av datorn",
    ],
    risk=RiskLevel.HIGH,
    description="Stäng av datorn.",
    examples=["stäng av datorn", "stäng av"],
)

INTENT_RESTART = Intent(
    name="restart",
    category=IntentCategory.SYSTEM,
    patterns=[
        "starta om datorn",
        "starta om",
        "starta om systemet",
        "omstart",
    ],
    risk=RiskLevel.HIGH,
    description="Starta om datorn.",
    examples=["starta om datorn", "omstart"],
)

INTENT_VOLUME_UP = Intent(
    name="volume_up",
    category=IntentCategory.SYSTEM,
    patterns=["höj volymen", "höj volym", "öka volymen", "volym upp", "högre"],
    risk=RiskLevel.LOW,
    description="Höj systemvolymen.",
    examples=["höj volymen", "högre"],
)

INTENT_VOLUME_DOWN = Intent(
    name="volume_down",
    category=IntentCategory.SYSTEM,
    patterns=["sänk volymen", "sänk volym", "minska volymen", "volym ner", "tystare"],
    risk=RiskLevel.LOW,
    description="Sänk systemvolymen.",
    examples=["sänk volymen", "tystare"],
)

INTENT_VOLUME_MUTE = Intent(
    name="volume_mute",
    category=IntentCategory.SYSTEM,
    patterns=["ljud av", "tysta", "stäng ljud", "mute"],
    risk=RiskLevel.LOW,
    description="Stäng av systemljudet.",
    examples=["ljud av", "tysta"],
)

INTENT_TAKE_SCREENSHOT = Intent(
    name="take_screenshot",
    category=IntentCategory.SYSTEM,
    patterns=[
        "ta en skärmdump",
        "ta skärmdump",
        "skärmdump",
        "fånga skärmen",
    ],
    risk=RiskLevel.LOW,
    description="Ta en skärmdump.",
    examples=["ta en skärmdump", "skärmdump"],
)

# ---------------------------------------------------------------------------
# Diktering
# ---------------------------------------------------------------------------

INTENT_START_DICTATION = Intent(
    name="start_dictation",
    category=IntentCategory.DICTATION,
    patterns=[
        "starta diktering",
        "dikteringsläge",
        "börja diktera",
        "starta skrivläge",
    ],
    risk=RiskLevel.LOW,
    description="Gå in i dikteringsläge — talade ord skrivs in i det aktiva programmet.",
    examples=["starta diktering", "dikteringsläge"],
)

INTENT_STOP_DICTATION = Intent(
    name="stop_dictation",
    category=IntentCategory.DICTATION,
    patterns=[
        "stoppa diktering",
        "avsluta diktering",
        "sluta diktera",
        "stoppa skrivläge",
        "kommandoläge",
    ],
    risk=RiskLevel.LOW,
    description="Avsluta dikteringsläget och återgå till kommandoläge.",
    examples=["stoppa diktering", "kommandoläge"],
)

# ---------------------------------------------------------------------------
# VS Code
# ---------------------------------------------------------------------------

INTENT_VSCODE_OPEN_PROJECT = Intent(
    name="vscode_open_project",
    category=IntentCategory.VSCODE,
    patterns=[
        "öppna projekt {project}",
        "öppna projektet {project}",
        "öppna {project} projekt",
    ],
    required_slots=["project"],
    risk=RiskLevel.LOW,
    description="Öppna en projektmapp i VS Code.",
    examples=["öppna projekt voicepilot"],
)

INTENT_VSCODE_OPEN_FILE = Intent(
    name="vscode_open_file",
    category=IntentCategory.VSCODE,
    patterns=[
        "öppna fil {file}",
        "redigera fil {file}",
        "visa fil {file}",
    ],
    required_slots=["file"],
    risk=RiskLevel.LOW,
    description="Öppna en fil i VS Code.",
    examples=["öppna fil main.py", "redigera fil readme.md"],
)

INTENT_VSCODE_GO_TO_LINE = Intent(
    name="vscode_go_to_line",
    category=IntentCategory.VSCODE,
    patterns=[
        "gå till rad {line}",
        "hoppa till rad {line}",
        "rad {line}",
    ],
    required_slots=["line"],
    risk=RiskLevel.LOW,
    description="Navigera till ett specifikt radnummer i VS Code.",
    examples=["gå till rad 150", "rad 42"],
)

INTENT_VSCODE_SAVE_FILE = Intent(
    name="vscode_save_file",
    category=IntentCategory.VSCODE,
    patterns=["spara filen", "spara fil", "spara aktuell fil", "spara"],
    risk=RiskLevel.LOW,
    description="Spara den aktuella filen i VS Code.",
    examples=["spara filen"],
)

INTENT_VSCODE_RUN_PROJECT = Intent(
    name="vscode_run_project",
    category=IntentCategory.VSCODE,
    patterns=["kör projektet", "kör projekt", "kör koden", "exekvera projekt", "kör"],
    risk=RiskLevel.MEDIUM,
    description="Kör det aktuella projektet i VS Code.",
    examples=["kör projektet"],
)

INTENT_VSCODE_OPEN_TERMINAL = Intent(
    name="vscode_open_terminal",
    category=IntentCategory.VSCODE,
    patterns=["öppna integrerad terminal", "ny terminal i kod", "vscode terminal"],
    risk=RiskLevel.LOW,
    description="Öppna en integrerad terminal i VS Code.",
    examples=["öppna integrerad terminal", "ny terminal i kod"],
)

INTENT_VSCODE_RENAME_SYMBOL = Intent(
    name="vscode_rename_symbol",
    category=IntentCategory.VSCODE,
    patterns=[
        "byt namn på symbol",
        "byt namn på variabel",
        "byt namn på markerat",
        "döp om detta",
    ],
    risk=RiskLevel.MEDIUM,
    description="Utlös byt namn-refaktorisering i VS Code.",
    examples=["byt namn på variabel", "byt namn på symbol"],
)

INTENT_VSCODE_COPY = Intent(
    name="vscode_copy",
    category=IntentCategory.VSCODE,
    patterns=["kopiera markerat", "kopiera markering", "kopiera kod", "kopiera"],
    risk=RiskLevel.LOW,
    description="Kopiera markerad text i VS Code.",
    examples=["kopiera", "kopiera markerat"],
)

INTENT_VSCODE_PASTE = Intent(
    name="vscode_paste",
    category=IntentCategory.VSCODE,
    patterns=["klistra in nedanför", "klistra in kod", "klistra in"],
    risk=RiskLevel.LOW,
    description="Klistra in urklipp i VS Code.",
    examples=["klistra in", "klistra in nedanför"],
)

# ---------------------------------------------------------------------------
# Huvudregister — interpretern itererar över denna lista
# ---------------------------------------------------------------------------

ALL_INTENTS: list[Intent] = [
    # Diktering först — dessa måste matchas innan något tvetydigt kommando
    INTENT_START_DICTATION,
    INTENT_STOP_DICTATION,
    # Applikationsstyrning
    INTENT_OPEN_APP,
    INTENT_CLOSE_APP,
    INTENT_SWITCH_APP,
    # Filhantering
    INTENT_OPEN_FOLDER,
    INTENT_CREATE_FOLDER,
    INTENT_CREATE_FILE,
    INTENT_DELETE_FILE,
    INTENT_DELETE_FOLDER,
    INTENT_SEARCH_FILE,
    # Fönsterstyrning
    INTENT_MINIMIZE_WINDOW,
    INTENT_MAXIMIZE_WINDOW,
    INTENT_CLOSE_WINDOW,
    INTENT_MOVE_WORKSPACE_LEFT,
    INTENT_MOVE_WORKSPACE_RIGHT,
    # System
    INTENT_LOCK_COMPUTER,
    INTENT_SHUTDOWN,
    INTENT_RESTART,
    INTENT_VOLUME_UP,
    INTENT_VOLUME_DOWN,
    INTENT_VOLUME_MUTE,
    INTENT_TAKE_SCREENSHOT,
    # VS Code
    INTENT_VSCODE_OPEN_PROJECT,
    INTENT_VSCODE_OPEN_FILE,
    INTENT_VSCODE_GO_TO_LINE,
    INTENT_VSCODE_SAVE_FILE,
    INTENT_VSCODE_RUN_PROJECT,
    INTENT_VSCODE_OPEN_TERMINAL,
    INTENT_VSCODE_RENAME_SYMBOL,
    INTENT_VSCODE_COPY,
    INTENT_VSCODE_PASTE,
]
