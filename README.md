# VoicePilot

Röststyrd skrivbordsassistent för Linux, på svenska. Styr datorn utan att
röra tangentbord eller mus — för utvecklare, poweranvändare och alla som
vill ha en handsfree arbetsmiljö.

## Snabbstart

```bash
# Installera system- och Python-beroenden
./scripts/install.sh

# Aktivera den virtuella miljön
source .venv/bin/activate

# Starta
voicepilot

# Felsökningsläge
voicepilot --debug

# Utan gränssnitt (headless, praktiskt för test)
voicepilot --no-ui
```

Säg **"Hey Jarvis"** för att väcka assistenten, vänta på ljudsignalen och
säg sedan ett kommando på svenska, t.ex. `öppna firefox`.

## De vanligaste kommandona

| Säg | Gör |
|---|---|
| `öppna firefox` | Startar Firefox |
| `stäng terminalen` | Avslutar terminalen (kräver `bekräfta`) |
| `öppna mappen nedladdningar` | Öppnar mappen i filhanteraren |
| `skapa mapp Projekt` | Skapar en ny mapp |
| `radera fil rapport.pdf` | Raderar en fil (kräver `bekräfta`) |
| `ta en skärmdump` | Tar en skärmdump |
| `lås datorn` | Låser skärmen (kräver `bekräfta`) |
| `starta diktering` | Går in i dikteringsläge — allt du säger skrivs in |
| `öppna projekt voicepilot` | Öppnar en projektmapp i VS Code |

Detta är ett urval. Full referens över samtliga 32 kommandon, alla
talvarianter, risknivåer och alias finns i
**[docs/ROSTKOMMANDON.md](docs/ROSTKOMMANDON.md)**.

## Funktioner

- **Väckningsord** — säg "Hey Jarvis" för att aktivera
- **Appstyrning** — öppna, stäng och växla mellan applikationer med namn
- **Filhantering** — skapa filer/mappar, öppna kataloger, sök
- **Dikteringsläge** — prata och få texten inskriven i valfritt program
- **Säkerhetssystem** — tre risknivåer med muntlig bekräftelse innan
  destruktiva kommandon körs
- **VS Code-integration** — öppna projekt, navigera, kör kod
- **Systemkommandon** — lås, volym, skärmdumpar, fönsterhantering

## Arkitektur

```
Mikrofon
  ↓
AudioListener (sounddevice)
  ↓
VAD (silero-vad)
  ↓ tal upptäckt
WakeWordDetector (openwakeword)       ← "Hey Jarvis"
  ↓ väckningsord bekräftat
Transcriber (faster-whisper, svenska)
  ↓ text
CommandInterpreter (rapidfuzz)        ← regelbaserad grammatik
  ↓ ParsedCommand
ConfirmationManager                   ← risknivå LÅG / MEDEL / HÖG
  ↓ godkänd
ActionRegistry → BaseAction.execute()
  ↓
Linux-systemet (subprocess / pynput / xdotool)
```

## Varför "Hey Jarvis" och inte ett svenskt väckningsord?

Väckningsordsdetekteringen (openwakeword) har inga färdigtränade svenska
modeller. De enda förtränade modellerna som följer med är `alexa`,
`hey_jarvis`, `hey_mycroft` och `hey_rhasspy` — samtliga engelska. Av dessa
är `hey_jarvis` den mest träffsäkra och minst benägen att utlösas av
vanligt tal, så det är den som används här. Allt som sägs **efter**
väckningsordet — alltså själva kommandot — tolkas på svenska.

Vill du ha ett eget, svenskt väckningsord kan du träna en egen
openwakeword-modell (se
[openwakeword](https://github.com/dscripka/openWakeWord) för instruktioner)
och lägga den tränade filen i `models/` — VoicePilot letar där efter en
anpassad modell innan den faller tillbaka på den förtränade.

## Varför Whisper-modellen `small` och inte `base.en`?

`base.en` är **enbart engelsk** och kan inte transkribera svenska alls —
den skulle helt enkelt gissa engelska ord oavsett vad som sägs. `small` är
den minsta flerspråkiga Whisper-modellen som klarar korta svenska kommandon
tillförlitligt, och `language = "sv"` i konfigurationen låser den till
svenska för både högre hastighet och bättre träffsäkerhet.

## Konfiguration

Standardvärden ligger i `config/default.toml` (levereras med paketet).
Egna inställningar sparas i:

```
~/.config/voicepilot/config.toml
```

Filen skapas inte automatiskt — kopiera det du vill ändra från
`config/default.toml` dit. Bara de nycklar du anger används; resten faller
tillbaka på standardvärdena.

De vanligaste inställningarna att ändra:

```toml
[speech]
activation_mode = "wake_word"   # "wake_word" | "push_to_talk" | "always_on"
wake_word = "hey jarvis"
whisper_model = "small"         # "tiny" | "small" | "medium" — flerspråkiga
whisper_device = "cpu"          # "cpu" | "cuda"
language = "sv"

[confirmation]
medium_risk_phrase = "bekräfta"
high_risk_phrase = "bekräfta radera"
cancel_phrase = "avbryt"

[ui]
overlay_position = "top-right"
theme = "dark"

[feedback]
tts_enabled = true
tts_engine = "espeak"           # "espeak" | "pyttsx3"
```

Egna appalias och mappalias (t.ex. om din maskin har svenska mappnamn som
`~/Hämtningar`) skrivs under `[apps.aliases]` respektive
`[folders.aliases]` — se `config/default.toml` för fullständig lista och
`docs/ROSTKOMMANDON.md` för vad som redan är fördefinierat.

## Utveckling

```bash
# Sätt upp utvecklingsmiljö
./scripts/dev_setup.sh

# Kör tester
pytest

# Linting
ruff check voicepilot/
mypy voicepilot/
```

## Lägga till ett nytt kommando

1. Lägg till en `Intent` i `voicepilot/parser/grammar.py`
2. Lägg till en `BaseAction`-subklass i `voicepilot/executor/`
3. Registrera actionen i `voicepilot/app.py` under `_register_actions()`

## Lägga till ett plugin

Skapa `~/.local/share/voicepilot/plugins/my_plugin.py`:

```python
from voicepilot.plugins.base import BasePlugin
from voicepilot.parser.intent import Intent, IntentCategory, RiskLevel

class MyPlugin(BasePlugin):
    name = "my_plugin"
    version = "1.0.0"
    description = "Mina egna kommandon"

    def setup(self, interpreter, registry):
        # Lägg till intents och actions
        interpreter.intents.append(Intent(
            name="my_command",
            category=IntentCategory.APP_CONTROL,
            patterns=["gör grejen"],
            risk=RiskLevel.LOW,
        ))
        # registry.register(MyAction())
```

## Systemkrav

- **OS**: Debian-baserad Linux — Ubuntu 22.04+, Linux Mint 21+, Pop!_OS,
  Debian 12+
- **Skrivbordsmiljö**: GNOME, Cinnamon, MATE, XFCE eller KDE.
  **X11-session rekommenderas** — på Wayland är tangentbordsinjicering och
  fönsterstyrning begränsade.
- **Python**: 3.10+
- **RAM**: 2 GB minimum (4 GB rekommenderas med `small`-modellen)
- **Disk**: ~1 GB för modeller

`install.sh` känner av skrivbordsmiljön och installerar rätt
skärmdumpsverktyg. Applikationsnamn slås upp vid körning, så `öppna filer`
startar `nautilus` på GNOME och `nemo` på Cinnamon utan att du behöver
ändra något i konfigurationen.

### Första körningen

Två modeller laddas ned vid första start och cachas därefter:

- Whisper-modellen som anges i `config.toml` (`small` är ~500 MB)
- openwakeword-modellerna för väckningsordet (~10 MB)

### Felsökning

**`Could not load the Qt platform plugin "xcb"`** — Qt-biblioteken saknas.
`install.sh` installerar dem; för att göra det manuellt:

```bash
sudo apt install libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0
```

Utan `libxcb-cursor0` kraschar Qt direkt vid start.

**`The repository '…' does not have a Release file`** vid installation — ett
orelaterat tredjeparts-apt-repo är felkonfigurerat. Installationsskriptet
rapporterar vilket och fortsätter ändå; VoicePilot behöver inte det repot.
På Linux Mint beror detta oftast på ett repo som lagts till med Mints eget
kodnamn (t.ex. `xia`) i stället för den Ubuntu-bas det faktiskt bygger på
(`noble`).

## Licens

MIT
