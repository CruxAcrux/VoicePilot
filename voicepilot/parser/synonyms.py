"""
Synonymexpansion för kommandotolkaren.

Mappar alternativa talade former → kanonisk form, så att grammatikens
mönster (`grammar.py`) kan hållas rena och inte behöver räkna upp varje
tänkbar formulering.

Exempel:
    "startar firefox"  → normaliseras till "starta firefox"
    "tar bort x.txt"    → normaliseras till "radera x.txt"

Viktigt — kanonisk form måste matcha grammatiken
--------------------------------------------------
De kanoniska formerna nedan är valda så att de är ord som `grammar.py`
faktiskt använder i sina mönster (t.ex. "öppna", "stäng", "radera",
"gå till"). En synonym får ALDRIG peka mot ett ord som grammatiken
använder i en annan, orelaterad exakt fras — annars förstörs den frasen
av normaliseringen innan den ens når mönstermatchningen.

Det tydligaste exemplet: "starta" och "kör" är redan giltiga, kanoniska
mönsterord för `open_application` (`starta {app}`, `kör {app}`), men de
används ÄVEN i egna, slot-lösa fraser som `starta om datorn` (restart)
och `kör projektet` (vscode_run_project). Om "starta" eller "kör" här
mappades till t.ex. "öppna" skulle "starta om datorn" bli
"öppna om datorn" och restart-kommandot skulle sluta fungera. Därför
förekommer "starta" och "kör" ALDRIG som synonym-källor i den här
filen — bara böjningsformer som "startar"/"köra" mappas, och de mappas
till sig själva ("starta"/"kör"), inte till ett annat verb. Samma
resonemang gäller "stäng av" (shutdown) och "stäng fönster"
(close_window): "stäng" är kanoniskt i sig och rörs aldrig som källa.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Verbsynonymer — mappa valfri form till det kanoniska verbet
# ---------------------------------------------------------------------------
#
# Kanonisk form (nyckel) = ordet som grammatikens mönster faktiskt
# innehåller. Källorna (listorna) är böjningsformer eller alternativa
# uttryck som INTE redan är ett eget mönsterord någon annanstans i
# grammatiken.

VERB_SYNONYMS: dict[str, list[str]] = {
    "öppna": [
        "öppnar", "öppnat", "öppna upp", "dra upp", "väck upp",
        "sätt igång", "aktivera",
    ],
    # OBS: "starta" och "kör" mappas INTE till "öppna" — se modulens
    # docstring. Här normaliseras bara böjningsformer av verben till
    # sig själva, vilket skyddar "starta om datorn" och "kör projektet".
    "starta": [
        "startar", "startat", "starta upp",
    ],
    "kör": [
        "köra", "kört",
    ],
    "exekvera": [
        "exekverar", "exekverat",
    ],
    "stäng": [
        "stänger", "stängde", "stängt",
    ],
    "avsluta": [
        "avslutar",
    ],
    "radera": [
        "raderar", "raderat", "kasta", "släng", "slänger", "avlägsna",
        "avlägsnar", "förstör", "förstöra",
        # Flerordsformer — måste stå här (inte som eget verb) eftersom
        # "ta bort {namn}" saknar en generell egen mönsterrad i
        # grammatiken (bara "ta bort fil/mapp {namn}" finns). Genom att
        # normalisera till "radera" fångas även t.ex. "ta bort x.txt".
        "ta bort", "tar bort", "tog bort",
    ],
    "skapa": [
        "skapar", "skapat", "generera", "genererar", "bygg", "bygger",
    ],
    "sök": [
        "söker", "sökte",
    ],
    "leta efter": [
        "letar efter", "letade efter",
    ],
    "hitta": [
        "hittar", "hittade",
    ],
    "gå till": [
        "navigera till", "navigerar till", "flytta till", "flyttar till",
        # "hoppa till" är redan ett eget mönsterord, men bara för
        # vscode_go_to_line ("hoppa till rad {line}"). Att normalisera
        # det till "gå till" är säkert: samma intent har även mönstret
        # "gå till rad {line}", så matchningen bevaras — och för andra
        # fraser (t.ex. "hoppa till firefox") vinner vi en generell
        # koppling till switch_to_application.
        "hoppa till", "hoppar till",
    ],
    "växla till": [
        "växlar till", "byt till", "byter till",
    ],
    "fokusera": [
        "fokuserar", "fokusera på", "fokusera dig på",
    ],
    "visa": [
        "visar",
    ],
    "minimera": [
        "minimerar", "förminska", "förminskar",
    ],
    "dölj": [
        "döljer",
    ],
    "maximera": [
        "maximerar", "förstora", "förstorar",
    ],
    "lås": [
        "låser",
    ],
    "höj": [
        "höjer",
    ],
    "öka": [
        "ökar",
    ],
    "sänk": [
        "sänker",
    ],
    "minska": [
        "minskar",
    ],
    "tysta": [
        "tystar",
    ],
    "spara": [
        "sparar", "sparade",
    ],
    "byt namn på": [
        "byter namn på",
        # OBS: "döp om" mappas medvetet INTE hit. Grammatiken har en
        # egen exakt fras "döp om detta" för vscode_rename_symbol som
        # inte innehåller "symbol"/"variabel"/"markerat". Om "döp om"
        # generellt normaliserades till "byt namn på" skulle
        # "döp om detta" bli "byt namn på detta", vilket INTE matchar
        # något av grammatikens "byt namn på …"-mönster.
    ],
    "kopiera": [
        "kopierar", "duplicera", "duplicerar", "klona", "klonar",
    ],
    "klistra in": [
        "klistrar in", "infoga", "infogar",
    ],
    "ångra": [
        "ångrar", "backa", "gå tillbaka",
    ],
    "gör om": [
        "gör om igen", "upprepa", "upprepar",
    ],
}

# ---------------------------------------------------------------------------
# Normalisering av applikationsnamn
# ---------------------------------------------------------------------------

APP_SYNONYMS: dict[str, list[str]] = {
    "firefox": ["fire fox", "mozilla firefox", "mozilla"],
    "chrome": ["google chrome", "google-chrome", "chromium"],
    "terminal": [
        "konsol", "konsolen", "terminalen", "kommandotolk",
        "kommandotolken", "skal", "skalet", "gnome-terminal", "term",
    ],
    "vs code": [
        "visual studio code", "vscode", "kodredigerare", "kodredigeraren",
    ],
    "filer": [
        "filhanteraren", "filhanterare", "nautilus", "filbläddrare",
    ],
    "slack": ["slack messenger", "slack-appen"],
    "discord": ["discord app", "discord-appen"],
}

# ---------------------------------------------------------------------------
# Normalisering av mappnamn
# ---------------------------------------------------------------------------

FOLDER_SYNONYMS: dict[str, list[str]] = {
    "nedladdningar": [
        "hämtade filer", "nedladdning", "nerladdningar", "nedladdningarna",
    ],
    "dokument": ["dokumenten", "dok"],
    "bilder": ["foton", "bilderna", "bild", "foto"],
    "skrivbord": ["skrivbordet", "mitt skrivbord"],
    "hem": [
        "hemmapp", "hemmappen", "hemkatalog", "hemkatalogen", "mitt hem",
    ],
    "projekt": ["projekten", "projects"],
}

# ---------------------------------------------------------------------------
# Bygg omvända uppslagstabeller
# ---------------------------------------------------------------------------

def _build_reverse(mapping: dict[str, list[str]]) -> dict[str, str]:
    """Bygg en omvänd uppslagstabell synonym → kanonisk form."""
    rev: dict[str, str] = {}
    for canonical, synonyms in mapping.items():
        for syn in synonyms:
            rev[syn.lower()] = canonical
    return rev


_VERB_REV = _build_reverse(VERB_SYNONYMS)
_APP_REV = _build_reverse(APP_SYNONYMS)
_FOLDER_REV = _build_reverse(FOLDER_SYNONYMS)


# ---------------------------------------------------------------------------
# Publikt API
# ---------------------------------------------------------------------------

def normalise_text(text: str) -> str:
    """
    Expandera synonymer i *text* till kanoniska former.

    Tillämpas i ordning: verb → appnamn → mappnamn.
    Texten görs till gemener och överflödigt whitespace slås ihop.
    """
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)

    # Verbnormalisering (längsta match först, se _replace_synonyms)
    text = _replace_synonyms(text, _VERB_REV)
    text = _replace_synonyms(text, _APP_REV)
    text = _replace_synonyms(text, _FOLDER_REV)

    return text


def _replace_synonyms(text: str, rev_map: dict[str, str]) -> str:
    """Ersätt alla förekomster av synonymfraser med deras kanoniska form."""
    # Sortera efter längd, fallande, så att längre fraser ersätts före
    # kortare delsträngar (t.ex. "ta bort" måste ersättas innan ett
    # ensamt "ta" hunnit tolkas — annars äts halva frasen upp).
    for synonym in sorted(rev_map, key=len, reverse=True):
        canonical = rev_map[synonym]
        # Ersättning med hänsyn till ordgränser
        pattern = r"\b" + re.escape(synonym) + r"\b"
        text = re.sub(pattern, canonical, text, flags=re.IGNORECASE)
    return text


def canonical_app(name: str) -> str:
    """Returnera det kanoniska appnamnet för ett givet talat namn."""
    return _APP_REV.get(name.lower(), name.lower())


def canonical_folder(name: str) -> str:
    """Returnera det kanoniska mappnamnet för ett givet talat mappnamn."""
    return _FOLDER_REV.get(name.lower(), name.lower())
