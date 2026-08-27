# Röstkommandon

Fullständig referens över alla 32 kommandon som VoicePilot förstår. Källan är
`voicepilot/parser/grammar.py` — varje rad i tabellerna nedan har verifierats
genom att köras genom `CommandInterpreter().parse()` och kontrollerats mot
det intent den ska matcha.

Platshållare i klamrar (`{app}`, `{mapp}`, `{namn}` …) är sådant du fyller i
själv när du säger kommandot, t.ex. `öppna firefox` eller `skapa mapp Projekt`.

## Innehåll

- [Risknivåer](#risknivåer)
- [Hur bekräftelse går till](#hur-bekräftelse-går-till)
- [Appstyrning](#appstyrning)
- [Filer och mappar](#filer-och-mappar)
- [Fönster](#fönster)
- [System](#system)
- [Diktering](#diktering)
- [VS Code](#vs-code)
- [Appalias](#appalias)
- [Mappalias](#mappalias)

---

## Risknivåer

Varje kommando har en risknivå som styr hur mycket bekräftelse som krävs
innan det körs. Källan är `voicepilot/confirmation/risk.py`.

| Nivå | Beteende |
|---|---|
| **Låg** | Körs direkt, ingen bekräftelse. |
| **Medel** | VoicePilot upprepar vad den uppfattat och väntar på att du säger `bekräfta` (eller `avbryt`). |
| **Hög** | Samma som Medel, men kräver hela frasen `bekräfta radera` — en enkel `bekräfta` räcker inte. Används för destruktiva och irreversibla kommandon. |

`risk.py` innehåller även en eskaleringsmekanism (`_ALWAYS_MEDIUM` /
`_ALWAYS_HIGH`) som kan höja risknivån för vissa intent-namn oavsett vad
grammatiken säger. I dagsläget är den ren defensiv dubblering — de intent
som listas där (`close_application`, `close_window`, `delete_file`,
`lock_computer`, `vscode_run_project`, `vscode_rename_symbol` för Medel;
`shutdown`, `restart`, `delete_folder` för Hög) har redan exakt samma
risknivå i grammatiken. Den faktiska risknivån för alla 32 kommandon nedan
har verifierats direkt mot `classify()` och stämmer med grammatikens
deklarerade nivå.

## Hur bekräftelse går till

Vid Medel eller Hög risk säger VoicePilot en muntlig sammanfattning och
väntar (`timeout_seconds`, standard 10 sekunder) på ditt svar. Säger du
`avbryt` avbryts kommandot. Svarar du inte alls inom tidsgränsen avbryts det
automatiskt också.

**Exempel, Medel-risk** (`radera fil rapport.pdf`):

```
Du:         "radera fil rapport.pdf"
VoicePilot: "Jag uppfattade: ta bort fil (name='rapport.pdf').
             Säg 'bekräfta' för att fortsätta eller 'avbryt' för att avbryta."
Du:         "bekräfta"
VoicePilot: "Fil borttagen."
```

**Exempel, Hög risk** (`stäng av datorn`):

```
Du:         "stäng av datorn"
VoicePilot: "Varning: stänga av datorn. Detta går inte att ångra.
             Säg 'bekräfta radera' för att fortsätta eller 'avbryt' för att avbryta."
Du:         "bekräfta radera"
VoicePilot: "Stänger av."
```

Fraserna `bekräfta`, `bekräfta radera` och `avbryt` är konfigurerbara i
`[confirmation]` i `config.toml` (se README).

---

## Appstyrning

| Säg | Gör | Risknivå |
|---|---|---|
| `öppna {app}`<br>`starta {app}`<br>`kör {app}` | Startar en app | Låg |
| `stäng {app}`<br>`avsluta {app}` | Avslutar en körande app | Medel |
| `växla till {app}`<br>`gå till {app}`<br>`fokusera {app}`<br>`visa {app}` | Växlar fokus till en körande app | Låg |

## Filer och mappar

| Säg | Gör | Risknivå |
|---|---|---|
| `öppna mappen {mapp}`<br>`öppna mapp {mapp}`<br>`visa mappen {mapp}`<br>`gå till mappen {mapp}` | Öppnar en mapp i filhanteraren | Låg |
| `skapa mapp {namn}`<br>`skapa en mapp som heter {namn}`<br>`skapa mappen {namn}`<br>`ny mapp {namn}` | Skapar en ny mapp | Låg |
| `skapa fil {namn}`<br>`skapa en fil som heter {namn}`<br>`skapa filen {namn}`<br>`ny fil {namn}`<br>`gör fil {namn}` | Skapar en ny tom fil | Låg |
| `radera fil {namn}`<br>`ta bort fil {namn}`<br>`radera filen {namn}`<br>`ta bort filen {namn}`<br>`radera {namn}` | Raderar en fil | Medel |
| `radera mapp {namn}`<br>`radera mappen {namn}`<br>`ta bort mapp {namn}`<br>`ta bort mappen {namn}` | Raderar en mapp **och allt dess innehåll** | Hög |
| `sök efter {namn}`<br>`sök {namn}`<br>`hitta filen {namn}`<br>`hitta {namn}`<br>`leta efter {namn}`<br>`var är {namn}` | Söker efter en fil eller mapp | Låg |

## Fönster

| Säg | Gör | Risknivå |
|---|---|---|
| `minimera fönster`<br>`minimera fönstret`<br>`minimera {app}`<br>`dölj fönster`<br>`minimera detta` | Minimerar det aktuella (eller angivna) fönstret | Låg |
| `maximera fönster`<br>`maximera fönstret`<br>`maximera {app}`<br>`helskärm`<br>`fullskärm` | Maximerar det aktuella (eller angivna) fönstret | Låg |
| `stäng fönster`<br>`stäng fönstret`<br>`stäng detta fönster`<br>`stäng aktuellt fönster`<br>`stäng nuvarande fönster` | Stänger det fönster som har fokus | Medel |
| `arbetsyta vänster`<br>`gå vänster`<br>`föregående arbetsyta` | Växlar till arbetsytan till vänster | Låg |
| `arbetsyta höger`<br>`gå höger`<br>`nästa arbetsyta` | Växlar till arbetsytan till höger | Låg |

## System

| Säg | Gör | Risknivå |
|---|---|---|
| `lås dator`<br>`lås datorn`<br>`lås skärmen`<br>`lås min dator` | Låser skärmen | Medel |
| `stäng av datorn`<br>`stäng av`<br>`stäng ner datorn`<br>`slå av datorn` | Stänger av datorn | Hög |
| `starta om datorn`<br>`starta om`<br>`starta om systemet`<br>`omstart` | Startar om datorn | Hög |
| `höj volymen`<br>`höj volym`<br>`öka volymen`<br>`volym upp`<br>`högre` | Höjer systemvolymen | Låg |
| `sänk volymen`<br>`sänk volym`<br>`minska volymen`<br>`volym ner`<br>`tystare` | Sänker systemvolymen | Låg |
| `ljud av`<br>`tysta`<br>`stäng ljud`<br>`mute` | Stänger av systemljudet | Låg |
| `ta en skärmdump`<br>`ta skärmdump`<br>`skärmdump`<br>`fånga skärmen` | Tar en skärmdump | Låg |

## Diktering

| Säg | Gör | Risknivå |
|---|---|---|
| `starta diktering`<br>`dikteringsläge`<br>`börja diktera`<br>`starta skrivläge` | Går in i dikteringsläget | Låg |
| `stoppa diktering`<br>`avsluta diktering`<br>`sluta diktera`<br>`stoppa skrivläge`<br>`kommandoläge` | Avslutar dikteringsläget, tillbaka till kommandoläge | Låg |

Se [Dikteringsläget](#dikteringsläget) nedan för hur det fungerar i praktiken.

## VS Code

Kräver att `[vscode].enabled = true` i konfigurationen (standard) och att
`code`-kommandot finns i `PATH`.

| Säg | Gör | Risknivå |
|---|---|---|
| `öppna projekt {projekt}`<br>`öppna projektet {projekt}`<br>`öppna {projekt} projekt` | Öppnar en projektmapp i VS Code | Låg |
| `öppna fil {fil}`<br>`redigera fil {fil}`<br>`visa fil {fil}` | Öppnar en fil i VS Code | Låg |
| `gå till rad {rad}`<br>`hoppa till rad {rad}`<br>`rad {rad}` | Navigerar till ett radnummer | Låg |
| `spara filen`<br>`spara fil`<br>`spara aktuell fil`<br>`spara` | Sparar aktuell fil | Låg |
| `kör projektet`<br>`kör projekt`<br>`kör koden`<br>`exekvera projekt`<br>`kör` | Kör det aktuella projektet | Medel |
| `öppna integrerad terminal`<br>`ny terminal i kod`<br>`vscode terminal` | Öppnar en integrerad terminal | Låg |
| `byt namn på symbol`<br>`byt namn på variabel`<br>`byt namn på markerat`<br>`döp om detta` | Utlöser byt namn-refaktorisering | Medel |
| `kopiera markerat`<br>`kopiera markering`<br>`kopiera kod`<br>`kopiera` | Kopierar markerad text | Låg |
| `klistra in nedanför`<br>`klistra in kod`<br>`klistra in` | Klistrar in urklipp | Låg |

---

## Dikteringsläget

Säg `starta diktering` (eller en av dess synonymer) för att gå in i
dikteringsläge. VoicePilot bekräftar med "Dikteringsläge på. Prata fritt."

I dikteringsläge tolkas **allt** du säger som text och skrivs in i det
program som har fokus, ord för ord — inget körs som kommando. Det enda
undantaget är stopp-frasen: säger du `stoppa diktering`, `avsluta
diktering`, `sluta diktera`, `stoppa skrivläge` eller `kommandoläge` avslutas
diktering omedelbart och du är tillbaka i kommandoläge ("Diktering
avstängd."). Dessa fem fraser fångas upp innan text skrivs in, så du kan
aldrig råka skriva in dem i dokumentet.

Text matas in via `xdotool`, urklipp eller automatiskt vald metod, beroende
på `[dictation].injection_method` i konfigurationen.

## Appalias

Alias mappar det uttalade namnet (nyckel) till den körbara filen (värde).
Källa: `[apps.aliases]` i `config/default.toml`. Produktnamn (firefox,
spotify, slack, discord, chrome, vs code) sägs likadant på svenska och
engelska och har därför engelska nycklar; generiska begrepp har svenska
nycklar eftersom det är dem man faktiskt säger.

| Du säger | Startar |
|---|---|
| `firefox` | firefox |
| `chrome` | google-chrome |
| `chromium` | chromium-browser |
| `terminalen` / `terminal` | gnome-terminal |
| `filhanteraren` / `filer` | nautilus |
| `vs code` / `vscode` / `code` | code |
| `slack` | slack |
| `discord` | discord |
| `spotify` | spotify |
| `inställningar` / `systeminställningar` | gnome-control-center |
| `kalkylator` / `miniräknare` | gnome-calculator |
| `textredigerare` / `textredigeraren` / `anteckningar` | gedit |
| `webbläsaren` / `webbläsare` | firefox |

Det körbara namnet ovan är bara startgissningen — `resolve_app()` i
`voicepilot/core/desktop.py` väljer rätt binär för din skrivbordsmiljö
(t.ex. `nemo` i stället för `nautilus` på Cinnamon) om den konfigurerade
binären inte finns installerad.

Utöver alias känner synonymtabellen (`voicepilot/parser/synonyms.py`) även
igen böjningsformer och alternativa uttryck, t.ex. `mozilla` → firefox,
`kodredigeraren` → vs code, `filbläddrare` → filer, `konsolen` → terminal.

## Mappalias

Källa: `[folders.aliases]` i `config/default.toml`. Sökvägarna ändras inte
bara för att nyckeln är svensk — de flesta Linux-installationer med engelsk
locale har fortfarande mappar som `~/Downloads`, `~/Documents` osv. på
disk. Har din maskin svenska mappnamn (t.ex. `~/Hämtningar` från en
sv_SE-installation) skriver du över dessa i
`~/.config/voicepilot/config.toml`.

| Du säger | Sökväg |
|---|---|
| `hem` / `hemmapp` | `~` |
| `skrivbord` / `skrivbordet` | `~/Desktop` |
| `nedladdningar` / `hämtade filer` / `hämtningar` | `~/Downloads` |
| `dokument` | `~/Documents` |
| `bilder` / `foton` | `~/Pictures` |
| `musik` | `~/Music` |
| `videor` / `filmer` | `~/Videos` |
| `projekt` | `~/Projects` |

Synonymtabellen normaliserar även böjningsformer, t.ex. `nedladdningarna` →
nedladdningar, `dokumenten` → dokument, `mitt skrivbord` → skrivbord.
