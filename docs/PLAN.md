# Plan: översättning av VoicePilot till svenska

Nedbrytning av arbetet med att gå från engelska till svenska röstkommandon.
En task i taget, en subagent per task, en commit per task.

## Beslut

| Fråga | Val | Motivering |
|---|---|---|
| Aktivering | `hey jarvis` (engelskt wake word) | Det finns ingen färdigtränad svensk wake word-modell i openwakeword. De enda förtränade är `alexa`, `hey_jarvis`, `hey_mycroft`, `hey_rhasspy`. `hey_jarvis` är den mest träffsäkra och minst benägen att utlösas av vanligt tal. |
| Whisper-modell | `small` | `base.en` är **engelsk-only** och kan inte transkribera svenska alls. `small` är den minsta flerspråkiga modellen som klarar korta svenska kommandon tillförlitligt. |
| Språk | `language = "sv"` | Låser Whisper till svenska, vilket både snabbar upp och höjer träffsäkerheten. |

## Vad som **inte** ändras

Enligt önskemål behålls dessa oförändrade:

- Mappnamnet `voicepilot/`
- Alla filnamn som innehåller `voicepilot`
- Paketnamnet `voicepilot` i `pyproject.toml`
- Kommandot `voicepilot` i terminalen
- Intent-namn i koden (`open_application`, `delete_folder`, …) — dessa är interna
  identifierare, inte något användaren säger. Att översätta dem skulle bryta
  `registry.py`, `risk.py` och alla actions utan att ge något värde.

Det som översätts är det användaren **hör och säger**: mönster, synonymer,
talade svar och dokumentation.

## Tasks

### Task 1 — Grund: `.gitignore`, städning, baseline-commit
`.gitignore` saknas helt, vilket gör att `.venv/`, `__pycache__/` och
`voicepilot.egg-info/` riskerar att hamna på GitHub. Tomma mappar städas.
Allt befintligt arbete commit:as som utgångsläge.

- Skapa `.gitignore`
- Ta bort tomma mappar som inte fyller en funktion
- Baseline-commit av nuvarande (fungerande) tillstånd

### Task 2 — Konfiguration till svenska
- `config/default.toml`: `language`, `whisper_model`, `wake_word`
- Bekräftelsefraser: `bekräfta`, `avbryt`, `bekräfta radera`
- Motsvarande defaults i `voicepilot/core/config.py`

### Task 3 — Grammatik till svenska
`voicepilot/parser/grammar.py` — 32 intents, 118 mönster.
Alla `patterns`, `description` och `examples` till svenska.
Intent-namn och slot-namn lämnas orörda.

### Task 4 — Synonymer till svenska
`voicepilot/parser/synonyms.py` — verb-, app- och mappsynonymer.
Måste hantera svensk böjning (`öppna`/`öppnar`, `radera`/`ta bort`).

### Task 5 — Talade svar och wake word
- `voicepilot/app.py`: alla `_speak()`-meddelanden och dikteringsfraser
- `voicepilot/confirmation/risk.py`: `risk_message()`-prompter
- `voicepilot/speech/wake_word.py`: välj `hey_jarvis`-modellen explicit
- TTS: svensk röst i `espeak-ng` (`-v sv`)

### Task 6 — Tester till svenska
`test_interpreter.py` och `test_synonyms.py` testar engelska strängar och
går sönder när grammatiken byter språk. Uppdateras plus nya tester som
täcker svensk böjning.

### Task 7 — Dokumentation
- `README.md`: fullständig svensk kommandoreferens
- `docs/ROSTKOMMANDON.md`: uttömmande tabell över alla 32 kommandon

## Ordning och beroenden

```
Task 1 (grund)
   └─> Task 2 (config)
         └─> Task 3 (grammatik) ──> Task 4 (synonymer)
                                       └─> Task 5 (röstsvar)
                                             └─> Task 6 (tester)
                                                   └─> Task 7 (dokumentation)
```

Task 3, 4 och 6 hänger tätt ihop: grammatiken definierar mönstren, synonymerna
normaliserar mot dem, och testerna verifierar båda. De körs därför i ordning
och inte parallellt.
