# Precon-Decks: gemessener Stand

Fortlaufend geführt: jeder Abschnitt nennt den Pin, an dem er gemessen wurde (Import- und
Sweep-Zahlen unten zuerst am Pin `043579bb`, XMage 1.4.62, Repin v9, 2026-10-20; spätere
Sweeps an den Pins `769e6ebb`, `456b0e22` und danach). Der aktuelle Pin steht allein in
`config/rules_engines.json`. Evidenzklassen nach `AGENTS.md` §4.
Alle Läufe sind lokal (`LOCAL_OBSERVED`), kein CI-Kredit.

## Bestand

`data/decks/precons/` enthält **174** Decks (2011–2026, je 100 Karten). Drei Decks mit gebannten
Karten wurden entfernt (195 Decks), danach am 2026-10-25 21 schwache Precons aussortiert (externe
Spielbarkeits-Einschätzungen, #1014). Frühere Texte nannten 198 oder 195 Decks; die Messungen
weiter unten tragen den Pool-Stand, auf dem sie entstanden sind (195).

Der Pool (174 Decks seit dem Aussortieren, vorher 195) teilt sich in **165 echte** (am Pin `90f5c4d3f8` importierbar, vorher 186) und
**9 SYNTHETIC** (`data/decks/precon_variants/`, Abschnitt „SYNTHETIC-Proxies“). Aussagen über
echte Decks zählen nur die 165; ein Deck der 9 steht in keiner Zahl, ohne dass es als SYNTHETIC
genannt ist. Bis zum Pin `4da83f62` waren es 182 echte und 13 SYNTHETIC; die Zahlen und
Messungen weiter unten tragen den Pin, auf dem sie entstanden sind.

**Stand seit Repin v13 (2026-10-23, #979):** Der Fork baut die Karten der Decks `2024_death_toll`
(Winter), `2024_family_matters` (Zinnia), `2024_miracle_worker` (Aminatou) und
`2026_multiverse_reforged` (Jace, Dack Fayden, Jhoira, Tamiyo, Teferi's Reproach, The Ur-Sphinx,
Venser). Importmessung auf dem Bridge-JAR `2e65e12e…` (Pin `90f5c4d3f8`, `LOCAL_OBSERVED`, ohne
CI-Anrechnung): **186 von 195** importieren, 9 nicht (Liste unten ohne die vier Decks;
`docs/performance/PRECON_IMPORT_V13_2026-10-23.md`). Die vier Proxies sind entfernt, die echten
Decks zählen. Die Commander-Proxies (Carth, Fury, Jin Sakai, Breya) entfallen damit.

## Import über den produktiven Pfad (`DIRECTLY_VERIFIED`)

Gemessen mit `scripts/measure_precon_imports.py`: jedes Deck läuft über
`ExternalRulesAdapter.import_deck()` in den Java-`XmageDeckImporter` (Kartenauflösung und
Commander-Validierung). **Es wird kein Spiel gespielt.** Frische Card-DB je Lauf.

| Stand | Import OK | Blockiert |
|---|---|---|
| Alter Pin `348b37db` (1.4.61), Daten wie vorgefunden | 173/195 | 18 Decks wegen 53 fehlender Kartennamen, 4 Decks wegen Commander-Namen |
| Neuer Pin `043579bb` (1.4.62), nach Daten-Fix der Commander-Namen | **182/195** | 13 Decks wegen 31 verschiedener fehlender Kartennamen (33 Einträge, zwei Namen fehlen in je zwei Decks) |

Daten-Fix: Vier Decks führten in `commander.commanders` den Namen in der Form „A // B“
(`2022_heads_i_win__tails_you_lose`, `2023_angels__they_re_just_like_us_but_cooler_and_with_wings`,
`2023_from_cute_to_brute`, `2024_raining_cats_and_dogs`). Der Importer löst nur die Vorderseite
auf (`CARD_IDENTITY_MISMATCH`). Die Karten selbst stehen mit Vordernamen im Deck; nur das
Commander-Feld wurde auf die Vorderseite gesetzt.

Fehlende Kartennamen am Pin `043579bb` (der Importer meldet pro Aufruf nur die erste Karte;
`measure_precon_imports.py --enumerate-missing` ersetzt jede gemeldete Karte in einer Kopie des
Decks durch einen Platzhalter und wiederholt, bis keine mehr gemeldet wird. Die Deckdatei bleibt
unverändert. Lauf auf dem Bridge-JAR `3f6531d7…` (Engine 1.4.62): dieselben 13 Decks und
dieselbe Liste wie die frühere Handover-Messung, jetzt mit einem Befehl reproduzierbar):

| Deck | Fehlende Kartennamen |
|---|---|
| `2023_blast_from_the_past` | Susan Foreman |
| `2023_masters_of_evil` | Missy, Cyber Conversion, Doomsday Confluence, Death in Heaven, Rassilon, the War President, The Cyber-Controller, Cybership, Don't Blink |
| `2023_paradox_power` | The Foretold Soldier, River Song's Diary, Psychic Paper |
| `2023_timey_wimey` | The Pandorica, The War Doctor, The Moment, Psychic Paper |
| `2024_blame_game` | Feather, Radiant Arbiter; Immortal Obligation |
| `2024_death_toll` | Winter, Cynical Opportunist (Commander) |
| `2024_family_matters` | Zinnia, Valley's Voice (Commander) |
| `2024_miracle_worker` | Aminatou, Veil Piercer (Commander) |
| `2024_revenant_recon` | Eye of Duskmantle |
| `2024_tricky_terrain` | Desert Warfare |
| `2024_tricky_terrain_collector_s_edition` | Desert Warfare |
| `2026_multiverse_reforged` | Dack Fayden, Helping Hand; Teferi's Reproach; Jhoira, Weatherlight Corsair; Venser, Fervent Forger; Tamiyo, Upriser Crowned; The Ur-Sphinx; Jace, Multiverse Architect (Commander) |
| `2026_odds_and_ends` | Exchange of Words, Space Beleren |

Vereinfachte Ersatzkarten (`SYNTHETIC`) aus den früheren Fork-Patches schließen diese Lücke nur
beim Import. Sie spielen nicht wie gedruckt und sind keine Regelevidenz.

## SYNTHETIC-Proxies (9 Decks seit Repin v13, vorher 13; `data/decks/precon_variants/`)

Owner-Entscheidung (2026-10-23, #920 Punkt 1): die 13 nicht importierbaren Precons bekommen
SYNTHETIC-Proxies, jetzt; der echte Nachbau der fehlenden Karten im Fork löst sie später ab
(#979, Fork-Push nur mit Owner-Go). Ein Proxy ist ein Testdeck, kein gedrucktes Precon, und hat
die Evidenzklasse `SYNTHETIC` (`AGENTS.md` §4): keine Regelevidenz, keine Qualifikationsevidenz,
kein Eintrag in einem Ranking neben echten Decks ohne die Kennzeichnung. Die Originale in
`data/decks/precons/` bleiben unverändert.

**Was ersetzt wird** (`scripts/build_precon_variants.py`, `--check` prüft, dass die eingecheckten
Dateien dem Generator entsprechen):

- 29 Hauptdeck-Slots in 10 Decks: eine echte, am Pin importierbare Karte statt der unbekannten,
  Commander-legal, in der Farbidentität des Decks, noch nicht im Deck. Quelle ist Satz 1 der
  Muse-Vorlage M2 (Branch `muse/claude-handover`, Commit `5138666f`, Ordner
  `handover/2026-10-20/ersatzkarten-vorlage/`; je Slot drei geprüfte Kandidaten, 30 von 30
  Ersatz-Sätzen importierten dort mit Status OK).
- 4 Decks mit unbekanntem Commander (`2024_death_toll`, `2024_family_matters`,
  `2024_miracle_worker`, `2026_multiverse_reforged`): ein Proxy-Commander. Die Vorlage liefert
  dafür nur das Importgerüst Breya; die Wahl folgt hier einer festen Regel (eine Entscheidung
  dieses Repos, nicht der Vorlage): legendäre Kreatur mit genau der Farbidentität des Originals
  (die übrigen 99 Karten bleiben legal), Commander-legal, am Pin importierbar und nicht schon im
  Deck; unter diesen zuerst Karten, die kein anderes Precon anführen, dann der nächste Manawert,
  dann die nächste Summe aus Kraft und Zähigkeit, dann der Name (Scryfall-Abfrage 2026-10-23,
  `EXTERNAL_DATA`; der erste Treffer jeder Rangliste importierte).

| Deck | Original-Commander | Proxy-Commander | Hauptdeck-Slots ersetzt |
|---|---|---|---|
| `2024_death_toll` | Winter, Cynical Opportunist (BG) | Carth the Lion | 0 |
| `2024_family_matters` | Zinnia, Valley's Voice (URW) | Director Nick Fury | 0 |
| `2024_miracle_worker` | Aminatou, Veil Piercer (WUB) | Jin Sakai, Ghost of Tsushima | 0 |
| `2026_multiverse_reforged` | Jace, Multiverse Architect (WUBR) | Breya, Etherium Shaper | 6 |

Bei `2026_multiverse_reforged` gibt es keine Karte, die die Regel ganz erfüllt: genau WUBR haben nur
Breya, Etherium Shaper und Nissa, Leyline Tamer, und Nissa steht schon im Deck (Import: „Too many:
2“). Breya führt außerdem `2016_invent_superiority` an; beide Decks können im selben Pod sitzen.
Der Commander-Proxy ist die am stärksten abweichende Ersetzung (ein anderes Deck führt an), die
Slot-Ersetzung die kleinste (1 % je Slot). Eine andere Wahl ist ein Eintrag in
`COMMANDER_PROXIES`; der Neubau ändert nur dieses Deck.

**Kennzeichnung** (alles vom Generator erzeugt, ein Test prüft jede Stelle):

- Deck-Daten: Tag `SYNTHETIC` (und `precon-proxy`), `deck_id` beginnt mit `precon-synthetic/`,
  Name endet auf „(SYNTHETIC proxy)“, Deck-Notiz „SYNTHETIC proxy of …“, jede ersetzte Karte und
  jeder ersetzte Commander trägt die Notiz „SYNTHETIC: replaces … / stands in for …“.
- Liste: `data/decks/precon_synthetic_proxies.json` nennt je Deck, was für was steht, die Quelle
  der Ersatzkarten, die Commander-Regel und die Pool-Aufteilung (195 = 186 echt + 9 SYNTHETIC).
- Auswertung (`scripts/precon_provenance.py`, Marker ist das `deck_id`-Präfix):
  `measure_precon_imports.py` schreibt je Deck `provenance` (`REAL` oder `SYNTHETIC`) und
  `decks_by_provenance`; `precon_pod_sweep.py` schreibt `decks_by_provenance`, je Pod
  `synthetic_decks` und im Bericht `pods_with_synthetic_decks` und
  `pods_failed_with_synthetic_decks`. Zahlen über gedruckte Precons und über Proxies werden getrennt
  genannt. Ein Sweep über 186 echte plus 9 Proxies:
  `--import-report imports.json --synthetic-proxies` (der Import-Report enthält nur die 186
  Originale; wer ohne ihn alle 195 Originale wählt, bekommt keinen Proxy daneben, der Aufruf
  bricht mit Exit-Code 2 ab).

**Import** (Bridge-JAR `c5c019a2…`, Engine 1.4.62, Pin `4da83f62`, `LOCAL_OBSERVED`,
`measure_precon_imports.py --deck-dir data/decks/precon_variants`): **13 von 13 importieren**.
Das beweist die Existenz der Karten am Pin, nicht ihre Funktion im Spiel; die Ersatzkarten sind
nicht einzeln auf Funktion geprüft.

**Nicht belegt:** wie nah ein Proxy am gedruckten Deck spielt. Die Ersetzung ändert 0 bis 8 von 99
Karten und bei vier Decks den Commander; Stärkevergleiche zwischen einem Proxy und dem Original
oder einem echten Deck sind damit keine Aussage über das Precon. Stand der Sweeps mit Proxies:
siehe „Spielbarkeit“. Der formale Import- und Pod-Lauf der Varianten liegt in #978 (Muse, nach M4),
der Fork-Nachbau in #979.

## Spielbarkeit

**Import ist nicht Spielbarkeit.** Der Import beweist nur, dass Kartennamen und Commander
aufgelöst werden. Ob ein Deck in einem echten 4er-Pod durchspielt, zeigt `scripts/precon_pod_sweep.py`:
Pods aus vier verschiedenen Decks (derselbe Aufbau wie ein echtes Spiel; ein Deck auf mehreren
Plätzen lehnt der Validator vor dem Start ab).

**Stand 2026-10-23 (maßgeblich; die Chronologie darunter bleibt als Nachweis).**

Zählung auf den 182 echten Decks: drei frische Pläne, die vorher nie gespielt wurden (Plan-Seed
gleich Spiel-Seed 41, 42, 43), je alle 182 importierbaren Decks in 46 Pods, Pin `4da83f62`
(Engine 1.4.62), Pilot und Lab von `main` `b9936e94`, sechs Pods je Bridge-JVM, serieller GC,
`LOCAL_OBSERVED`, ein Lauf je Plan:

| Plan-Seed | Pods | liefen durch | Abbrüche | Entscheidungen je Pod (min / Median / max) | Pods ohne Sieger |
|---|---:|---:|---:|---|---:|
| 41 | 46 | 46 | 0 | 1565 / 3169 / 7200 | 0 |
| 42 | 46 | 46 | 0 | 1849 / 2982 / 6295 | 1 (Pod 043) |
| 43 | 46 | 46 | 0 | 1650 / 2873 / 4793 | 0 |

Das sind 138 Pods ohne Abbruch; jedes der 182 Decks sass in jedem Plan mindestens einmal an einem
Tisch. Das ist eine Zählung und keine Passquote: ein Spiel je Pod, drei Pläne, und die Pods sind
keine unabhängigen Ziehungen (jedes Deck kommt in jedem Plan vor). Als Größenordnung bei null
Abbrüchen in 138 Pods liegt die Obergrenze der Abbruchrate je Pod für Pläne dieser Art bei rund
2,2 % (Dreisatz-Regel, 95 %). Das verwendete Bridge-JAR (`c5c019a2…`) ist aus der ersten Fassung von
#977 gebaut; die gemergte Bridge unterscheidet sich davon nur darin, welche Deck-Handles sie
zwischen Spielen freigibt (`retainOnly` statt `forget`), nicht im Spielablauf.

Pod 043 des Plans 42 (`2024_scrappy_survivors`, `2026_silverquill_influence`,
`2017_evasive_maneuvers`, `2018_devour_for_power`) endete ohne Sieger: Status `ok`, 3269 Entscheidungen,
`terminal`, kein Engine-Fehler, Zug 46. Allein nachgespielt kommt dasselbe heraus (gleicher
Semantic-Hash). Ob es ein Remis oder ein gleichzeitiges Ausscheiden war, unterscheidet das Ergebnis
nicht.

**Stopp-Kriterium für die Familiensuche in #920.** Drei aufeinanderfolgende frische Pläne ohne Abbruch
über alle 182 echten Decks beenden die Suche nach Abbruchfamilien in den echten Decks. Das ist hier
mit den Plänen 41 bis 43 erreicht. Ein später gefundener Abbruch ist ein eigenes Issue mit eigener
Familie und setzt die Zählung nicht zurück. Das Kriterium ist eine Festlegung dieses Repos, nicht
des Owners; er kann eine größere Zahl verlangen.

**Mit den 13 SYNTHETIC-Proxies** (Plan-Seed 44, Spiel-Seed 44, 182 echte plus 13 Proxies = 195 Decks
in 49 Pods; `--import-report … --synthetic-proxies`, dasselbe JAR, `LOCAL_OBSERVED`, ein Lauf):
**48 von 49 Pods liefen durch**, ein Abbruch. Alle 13 Proxies saßen in je einem Pod
(`pods_with_synthetic_decks` 13), der Abbruch ist ein Pod mit einem Proxy
(`pods_failed_with_synthetic_decks` 1): `2024_tricky_terrain_collector_s_edition` mit
`2023_eldrazi_unbound`, `2023_angels__they_re_just_like_us_but_cooler_and_with_wings` und
`2025_mardu_surge`, `XMAGE_ACTION_EXECUTION_FAILED`, allein in einer JVM reproduziert (3 von 3).
Ursache (lokal nachgespielt mit einem nicht eingecheckten Debug-JAR, `LOCAL_OBSERVED`): Sage of the
Maze, „Tap an untapped Gate you control: Untap {this}“. Die Engine-Implementierung der Karte
(`SageOfTheMaze.java` im Fork) nutzt für die Kosten einen Filter ohne Gate- und ohne
Untapped-Prädikat (`new FilterControlledPermanent("untapped Gate you control")`, nur Text). Die
Engine bietet die Aktivierung deshalb auch an, wenn alles Getappte ist, fragt „Select an untapped
Gate you control“ mit lauter getappten Permanenten (Zug 31: Omo, Queen of Vesuva macht jedes Land
zum Gate), der Pilot wählt eine, `tap()` liefert false, die Kosten bleiben unbezahlt, die Engine
spult zurück und die Bridge bricht fail-closed ab. Das ist ein Kartenfehler der Engine, kein Fehler
des Proxys (Sage steht im Original und ist nicht ersetzt) und keiner des Piloten oder der Bridge.
Die Karte steht nur in den beiden Tricky-Terrain-Decks, also in keinem der 182 echten Decks. Behebung:
zwei Prädikate an der Karte im Fork (nächster Fork-Push, Owner-Go); bis dahin bricht ein Spiel mit
diesen zwei Proxies ab, sobald der Pilot die Aktivierung bei lauter getappten Permanenten wählt.
Das steht als Punkt in #979.

Stand der Messung:

- Neuer Pin `043579bb`, Sweep über die 182 importierbaren Decks (`LOCAL_OBSERVED`, ein Lauf,
  Plan-Seed 1, Spiel-Seed 1, Bridge-JAR `3f6531d7…`): **46 Pods, 37 liefen durch, 9 scheiterten**,
  alle neun mit `XMAGE_ACTION_EXECUTION_FAILED`. 146 der 182 Decks standen in mindestens einem
  durchgespielten Pod; 36 Decks standen nur in Pods, die scheiterten. Das ist ein Spiel pro Pod
  und keine Passquote: ein Deck in einem durchgespielten Pod hat ein Spiel überstanden, nicht
  „funktioniert“.
- Ursache der neun Ausfälle (lokal nachgespielt, `LOCAL_OBSERVED`; der öffentliche Fehler nennt
  absichtlich nur den Code und einen Schlüssel-Digest, die Karte steht nur im Prozess): in
  jedem Pod bot die Engine eine Aktion an, deren Kosten eine Wahl oder ein X enthalten, und
  konnte sie nach der Wahl nicht ausführen. Die Engine bricht eine solche Aktion selbst ab und
  stellt den Zustand davor wieder her (CR 601.2e / 727); die Bridge kannte bis #920 dafür nur
  andere Umkehr-Prädikate und beendete das Spiel. Die zuerst unbezahlten Kosten je Pod stammen aus
  einem lokalen Nachspielen mit instrumentierter `AbilityImpl` (nicht eingecheckt):

| Pod | Karte | Aktion | Zuerst unbezahlte Kosten | Mit #920 |
|---|---|---|---|---|
| 005 | Osgir, the Reconstructor | Aktivierung: {X}, {T}, Artefaktkarte mit Manawert X aus dem Friedhof exilieren | Exil-Kosten (Ziel leer) | läuft durch |
| 008, 035 | Grim Hireling | Aktivierung: {B}, X Schätze opfern | Opfer-Kosten (nach dem Mana ein Schatz zu wenig) | 035 läuft durch; 008 kommt weiter und bricht später an Crew 2 ab (mit dem Crew-Fix durch) |
| 011 | Collective Effort | Zauber (Escalate) | zweites „Kreatur tappen“ | läuft durch |
| 027 | Ruthless Radrat | Zauber (Squad) | zweites „vier Karten aus dem Friedhof exilieren“ | läuft durch |
| 028 | Skeletal Scrying | Zauber | „X Karten aus dem Friedhof exilieren“ | läuft durch |
| 037 | Peerless Recycling | Zauber (Gift) | Ziel „zwei Permanent-Karten im Friedhof“ nicht wählbar | läuft durch |
| 040 | Imposter Mech | Aktivierung: Crew 3 | Crew-Kosten (gewählte Kreaturen zu schwach) | bricht ab; mit dem Crew-/Marath-Fix durch |
| 042 | Marath, Will of the Wild | Aktivierung: {X}, X +1/+1-Marken entfernen | Marken-Kosten (X größer als die Marken) | bricht ab; mit dem Crew-/Marath-Fix durch |

Grim Hireling und Collective Effort sind dieselben Karten wie in der Stichprobe am alten Pin;
die anderen sechs Karten sind neu.

- **Bridge-Fix #920** (`XmageFullGamePlayer.reversedUnchoosableCostTarget` und
  `reversedUnchoosableAbilityTarget`): die Bridge erkennt die Umkehr, wenn (1) die Engine die
  Fähigkeit der gewählten Karte benutzt hat, (2) die ersten unbezahlten Kosten ein Pflichtziel
  haben, das leer blieb und dem Piloten nie vorgelegt wurde (bei Zielen der Fähigkeit selbst: ein
  leeres, nie vorgelegtes Pflichtziel) und (3) der Spielzustand nach dem Fehlschlag Bit für Bit
  dem davor entspricht (`XmageStateFingerprint`, SHA-256 über Ids und Zähler, bleibt im Prozess).
  Crew und Marath sind keine Zielkosten; ein Crew-Mangel nach einer Wahl scheitert in der Bridge
  weiter geschlossen (`XmageFullGameCrewUnpayableCostTest`). Sie werden im Piloten behoben (unten).
- **Crew und Marath (Pilot)**. Crew: die Engine bietet Crew an, wenn die Power des Vehicles selbst
  die Kosten decken würde (`CrewCost.canPay` wertet seinen Filter ohne Quelle aus, siehe #715), die
  gewählten anderen Kreaturen reichen dann nicht. Die Bridge meldet auf dem Angebot
  `crew_payable_without_source`: die Antwort der Engine auf `canPay` in einer Berechnungskopie des
  Spiels, in der das Vehicle getappt ist (ein getapptes Vehicle zählt dort nicht mit). Der Pilot
  lässt ein Crew-Angebot mit `false` liegen (`_priority_action_affordable`), ohne Kartenname und
  ohne Power-Rechnung. Marath: die Marken-Kosten sind eine Karten-eigene Kostenklasse, die Engine
  begrenzt X nicht durch die Marken. Der Pilot liest die gedruckte Kostenzeile des gewählten
  Angebots („Remove X +1/+1 counters from …“) und die öffentlichen Marken der Quelle und hält sein
  angesagtes X darin (`option_x_counter_cap`); die Domäne der Engine bleibt unverändert.
- Sweep mit dem Fix (gleiche Pods, Plan-Seed 1, Spiel-Seed 1, `LOCAL_OBSERVED`, ein Lauf, JAR
  `7d082d8d…`, vor der letzten Härtung des Zustandsabdrucks gebaut; die neun betroffenen Pods mit
  dem endgültigen JAR `888ee822…` nachgespielt: sechs laufen mit gleichem Hash und gleicher
  Entscheidungszahl durch, 008, 040 und 042 brechen wie zuvor ab): **43 von 46 Pods laufen durch** (vorher 37), 6 Pods wurden repariert (005, 011,
  027, 028, 035, 037), kein Pod ist neu abgebrochen, 3 brechen weiter ab (008, 040, 042; alle in
  Crew oder Marath). 170 von 182 Decks stehen jetzt in mindestens einem durchgespielten Pod, 12
  stehen nur in Pods, die scheiterten. 35 der 37 vorher durchgelaufenen Pods haben denselben
  Semantic-Hash und dieselbe Entscheidungszahl. Bei 029 und 033 ist die Entscheidungszahl gleich,
  der Hash anders. Beide Pods liefern mit demselben JAR und Seed wechselnd zwei Hashes
  (029: `ff71f5b7…` und `6144e8fe…`, zehn Läufe; 033: `1b23f691…` und `1908ba32…`, vier Läufe;
  jeweils mit dem Basis- und dem Fix-JAR, bei 029 auch mit einem Vergleichs-JAR ohne
  Zustandsabdruck). Der Unterschied kommt also nicht von der Änderung. Ursache (später
  gefunden, `LOCAL_OBSERVED`): die Engine sammelt `Card`, `Permanent` und Enums in `HashSet`s, die
  keinen eigenen `hashCode` haben, die Iterationsreihenfolge wechselt mit jedem JVM-Start. Bei 029
  fragt Kathril, Aspect Warper je Zählermarken-Art nach einem Ziel (`Collectors.toSet()` von
  `CounterType`), bei 033 sammelt Wave Goodbye die Kreaturen in einem `HashSet<Card>`, wodurch die
  Commander-Ersatzfragen („Move X to command zone instead of your hand?“) in Zug 32 mal von
  Sitz 1, mal von Sitz 2 zuerst gestellt werden. Der erste abweichende Eintrag steht in beiden
  Fällen im Entscheidungs-Trace (Object-IDs normalisiert); mit `EnumSet` für die zwei Karten und
  `LinkedHashSet` für 113 Dateien liefert Pod 029 in 4 von 4 und Pod 033 in 12 von 12 Läufen
  denselben Hash. Die Patches stehen auf dem Fork-Branch `claude/project-thread-nik5ho`
  (Perf-Port, Rules-RNG-Einzeiler und diese Patches); die Kandidatenlinie und der Pin sind
  unverändert. Der Perf-Port im selben Branch ist nicht ausgabegleich: mit ihm liefert Pod 033
  einen dritten, ebenfalls stabilen Hash (`07364fb0…` statt `1908ba32…`, 3 von 3 Läufen). Erste
  Abweichung ist ein Optionstext: `AddManaChosenColorEffect` merkt sich beim Berechnen der Mana
  die gewählte Farbe in einem Feld und hängt sie danach an den Regeltext an („… chosen color
  {U}“), und der Port spart Spielkopien, sodass dieses Feld auf einem anderen Objekt gesetzt
  wird. Der Text ist Teil des Optionsnamens und des Sortierschlüssels der Bridge (`abilitySortKey`),
  die Spiele laufen danach verschieden weiter. Ein Spiel pro Pod ist weiter keine Passquote.
- Sweep mit #928 und dem Crew-/Marath-Fix (gleiche Pods, Plan-Seed 1, Spiel-Seed 1, `LOCAL_OBSERVED`, ein Lauf,
  JAR `b85faccb…`, Import-Report des Pins als Deckliste): **46 von 46 Pods laufen durch**, alle 182
  importierbaren Decks stehen in mindestens einem durchgespielten Pod. 36 der 43 vorher
  durchgelaufenen Pods haben denselben Semantic-Hash. Bei sieben Pods (004, 006, 010, 011, 024,
  032, 039) ändern sich Hash und Entscheidungszahl, weil der Pilot das unbezahlbare Crew-Angebot
  nicht mehr wählt; pod-004 wiederholt mit demselben JAR zweimal den neuen Hash, und mit dem JAR
  ohne den Crew-Fakt auf dem neuen Pilotcode den alten. Die 36-Seed-Hashes der Abnahme sind gegen
  diesen Stand neu zu kalibrieren. Ein Spiel pro Pod ist weiter keine Passquote.
- Zweiter Sweep (Plan-Seed 2, Spiel-Seed 2, gleiche 182 Decks, JAR `b85faccb…`, `LOCAL_OBSERVED`,
  ein Lauf): **45 von 46 Pods laufen durch**, ein Abbruch: pod-004, `BRIDGE_PROTOCOL_ERROR: numeric
  bounds reversed: 1..0`. Ursache: Pia Nalaar, Chief Mechanic fragt am Ende des Zuges
  `getAmount(1, Energie)` auch dann, wenn der Spieler keine Energie hat, also einen leeren Bereich
  (die anderen Energie-Karten fragen ab 0 oder prüfen vorher). Die Bridge bleibt dort absichtlich
  fail-closed. Mit einer Prüfung an der Karte (Fork-Patch, siehe oben) läuft der Pod durch
  (2673 Entscheidungen, Hash `c2aeceed…`). Pilot und Bridge sehen die Energie nicht im
  Spielzustand; eine Pilot-Umgehung hätte den Zustandsabdruck des Replays geändert.

- Familiensuche mit weiteren Plänen (Spiel-Seed 1, `LOCAL_OBSERVED`, je Plan ein Lauf, die 182 Decks aus dem
  Import-Report des Pins):
  - **Plan-Seed 2:** 40 von 46 Pods liefen durch (JAR `d7f55047…`), sechs brachen ab
    (fünfmal `XMAGE_ACTION_EXECUTION_FAILED`, einmal `ENGINE_FAILURE`). Vier Familien, behoben in
    #932: (1) ein Ziel, das eine Regelmodifikation nicht wählbar macht (Ground Seal gegen den
    Seer), wurde der Pilotseite als Kostenziel angeboten; (2) "Remove a counter"-Kosten wurden für
    Objekte ohne Marke angeboten (Scholar ohne Marke); (3) zweite Phyrexian-Lebenszahlung bei zu
    wenig Leben (Lashwrithe), wo die Engine zurückspult; (4) die Kopier-Wirkung "Continue to
    choose copies and cast?" (Mizzix's Mastery) wurde nach abgelehntem Zauber erneut
    gestellt und bejaht. Mit #932 (JAR `6ffcd616…`): **46 von 46**, alle 182 Decks in einem durchgespielten Pod.
    Welcher Pod zu welcher Familie gehört, habe ich nicht einzeln aufgeschlüsselt.
  - **Plan-Seed 3:** 45 von 46 Pods liefen durch (JAR `6ffcd616…`, 178 Decks in durchgelaufenen Pods;
    zusammen mit Plan-Seed 2 alle 182). Ein Abbruch, `PLAYER_LEFT_GAME_UNSUPPORTED_DECISION:
    choose_use`: Willie Lumpkin, Postman trifft einen Gegner, der an diesem Schaden ausscheidet,
    und der Effekt fragt ihn beim Auflösen trotzdem "darf ziehen?". Behoben in #934 (kein Frame
    für einen ausgeschiedenen Spieler, XMage bekommt seine eigene Nicht-Antwort); der Pod läuft
    danach zu Ende (3534 Entscheidungen).
  - Das sind Funde pro Plan, kein Passanteil: ein Spiel pro Pod, eine Handvoll Pläne, und ein
    sauberer Lauf beweist nicht, dass andere Pläne oder Seeds sauber laufen.
- Familiensuche Plan-Seed 4 (Spiel-Seed 4, gleiche 182 Decks, `LOCAL_OBSERVED`, ein Lauf, Stand
  `1b5e542`): **41 von 46 Pods laufen durch**, fünf brechen ab (012, 021, 022, 029, 032). Mit dem
  Stand von `f5eecc7` (#931–#933) laufen 012, 022 und 029 durch (nicht je bis zur Karte
  verfolgt); 021 und 032 brachen dort weiter ab und werden im Piloten behoben:
  - Pod 021, Vault 112: Sadistic Simulation, Kapitel III. „Pay any amount of {E}“ (Aktion
    `amount`) führt bei Energie über den Land-oder-Zauber-Aufrufer (ADR Abschnitt 28,
    `UNSUPPORTED_DECISION_CLASS`), und die Bridge beendet das Spiel dort absichtlich. Der Pilot
    zahlt für diese Quelle keine Energie (`_UNSUPPORTED_ENERGY_PAYMENT_SOURCES`); null ist eine
    legale Antwort und überspringt das Exil. Das ist eine Umgehung, keine Unterstützung der Karte:
    der Pfad selbst bleibt geschlossen. Ihn in der Bridge zu öffnen wäre eine Freeze-Entscheidung
    des Owners.
  - Pod 032, Izzet Chemister: Die Wahl „Select up to one card to cast“ (Outcome `playforfree`)
    bewertete jede Karte negativ (der Pilot hatte die drei Zauber selbst gewirkt, siehe
    `target_object_bonus`), wählte nichts und beantwortete „Continue casting?“ 50000 Mal mit Ja.
    `playforfree` zählt jetzt wie ein Vorteil für den Wählenden und wählt bis zum Maximum.
  Mit dem Stand von `f5eecc7` und diesen zwei Pilot-Änderungen laufen alle drei Pods durch (012:
  3133 Entscheidungen, 021: 2402, 032: 3662; ein Spiel je Pod, keine Passquote). Die Bridge
  ändert sich dabei nicht.
- Familiensuche Plan-Seed 5 (Spiel-Seed 5, gleiche 182 Decks, `LOCAL_OBSERVED`, ein Lauf, Stand
  `d59d0cd`, Jar und Pilot von `main`): vier der 46 Pods brechen ab, alle vier im Piloten und
  ohne Änderung der Bridge. Der Lauf wurde in drei Teilen gespielt, weil der erste Prozess nach 23
  Pods abbrach; die Abbrüche wurden einzeln auf `d59d0cd` nachgespielt:
  - Pod 007, Slaughter the Strong: Die Karte fragt Kreatur für Kreatur („already selected total
    power N“) und nimmt eine erneut gewählte Kreatur wieder heraus, bis nichts mehr gewählt wird,
    und fragt dann „End the selection“ oder „Continue the selection“. Der Pilot wählte die eine
    sichtbare Kreatur jedes Mal und erreichte `max_decisions=50000`. Er wählt jede Kreatur jetzt
    einmal, wählt nichts, wenn keine neue mehr da ist, und beendet die Auswahl.
  - Pod 017, Timely Ward: „You may cast this spell as though it had flash if it targets a
    commander.“ Die Engine bietet den Zauber zu jeder Zeit an und prüft das Ziel erst nach der
    Wahl; außerhalb eines Sorcery-Fensters (hier ein eigener Zauber auf dem Stapel) scheitert der
    Zauber an einem Token. Der Pilot bietet ihn dort ohne Commander-Kreatur auf dem Tisch nicht
    an und zielt sonst auf den Commander.
  - Pod 035, Tekuthal, Inquiry Dominus: „Remove three counters from among other artifacts,
    creatures, and planeswalkers you control“ wird angeboten, sobald ein solches Objekt existiert,
    und scheitert, wenn die Marken aller zusammen unter drei liegen (hier Inspirit mit zwei
    Ladungsmarken; die Engine prüft in `RemoveCounterCost.canPay` nur, ob ein Ziel wählbar ist).
    Der Pilot aktiviert solche Kosten nur, wenn die Marken auf seinen Permanenten reichen (zählt
    ohne Typfilter, findet also nur einen Mangel, den keine Wahl beheben kann).
  - Pod 018, Lim-Dûl's Vault: „As many times as you choose, you may pay 1 life ... look at the top
    five cards“ fragt „Pay 1 life and look at the next 5 cards?“ bei jedem Durchgang neu. Der Pilot
    kann die fünf Karten nicht bewerten und antwortete jedes Mal Ja (über 10000 Entscheidungen, das
    Spiel lief fast eine Stunde bis `ENGINE_FAILURE`). Er zahlt jetzt höchstens dreimal hintereinander
    (`_LIFE_DIG_CAP`); ein Prioritätsfenster beendet die Zählung.
  Mit Jar von `d59d0cd` und diesen Änderungen laufen 007, 017, 018 und 035 durch (1818, 3294, 6562 und 2225
  Entscheidungen; ein Spiel je Pod, keine Passquote). Pilotvergleich vorher/nachher auf zehn Seeds (1–10, gleiches Jar):
  alle Zähler identisch.
- Familiensuche Plan-Seeds 6 bis 8 auf dem neuen Pin `769e6ebb` (Repin v10, Spiel-Seed gleich dem
  Plan-Seed, gleiche 182 Decks, `LOCAL_OBSERVED`, Jar aus `main` `d74dd708` gegen den Pin gebaut,
  Pilot von `main`): Seed 6 und Seed 8 laufen mit 46 von 46 Pods durch, Seed 7 mit 44 von 46. Die
  beiden Abbrüche liegen im Piloten, die Bridge bleibt unverändert (keine Requalifizierung):
  - Pod 023, Gift of Doom: Die Aura mit Morph wird als „Cast Gift of Doom using Morph“ angeboten.
    Die verdeckt gewirkte Karte löst beim Eintritt den Aura-Test der Engine aus („found etb aura
    with empty spell ability or without any targets“, `PlayerImpl.moveCards`), jeder Versuch endet
    in einem internen Fehler und das Spiel in `ENGINE_FAILURE`. Der Pilot wirkt sie nicht
    verdeckt (`_FACE_DOWN_AURAS`); der normale Zauber bleibt möglich.
  - Pod 045, Yuriko, the Tiger's Shadow: Commander ninjutsu ist in XMage eine `Zone.ALL`-Fähigkeit
    und wird angeboten, auch wenn die Karte schon im Spiel liegt (der Pilot hatte Yuriko normal
    gewirkt). Die Kosten „reveal ninjutsu card“ zahlen nur aus Hand oder Befehlszone, die Aktivierung
    scheitert nach dem Bezahlen des Manas (`XMAGE_ACTION_EXECUTION_FAILED`). Der Pilot aktiviert
    Ninjutsu nicht für eine Karte, die auf dem Schlachtfeld liegt.
  Mit diesen Änderungen laufen 023 und 045 durch (2268 und 4301 Entscheidungen; ein Spiel je Pod,
  keine Passquote). Seed 8 wurde zusätzlich auf unverändertem `main` gespielt. Pilotvergleich
  vorher/nachher auf zehn Seeds (1–10, gleiches Jar): alle Zähler identisch.
- Familiensuche Plan-Seeds 9 und 10 auf dem Pin `769e6ebb` (Spiel-Seed gleich dem Plan-Seed, gleiche 182
  Decks, `LOCAL_OBSERVED`, Jar aus `main` `d74dd708`, Pilot von `main` `16a4de4`): Seed 10 läuft
  mit 46 von 46 Pods durch, Seed 9 mit 43 von 46. Die drei Abbrüche liegen im Piloten, die Bridge
  bleibt unverändert (keine Requalifizierung):
  - Pod 007, Yuriko, the Tiger's Shadow: wie Pod 045 aus Seed 7, nur lag die Karte im Friedhof. Commander
    ninjutsu ist `Zone.ALL`, das Aufdecken zahlt nur aus Hand oder Befehlszone. Der Pilot aktiviert
    Ninjutsu jetzt nicht für Karten auf dem Schlachtfeld, im Friedhof oder im Exil
    (`ninjutsu_card_outside_hand`).
  - Pod 018, Timely Ward: Zwei Karten „Wyleth, Soul of Steel“ lagen auf dem Tisch, nur eine ist der
    Commander des Spielers. Die Zielwahl nahm nach dem Namen (`commander_creature_names`) die falsche und
    der Zauber scheiterte. Der Pilot erkennt Commander jetzt an Name und Besitzer
    (`commander_creature_ids`) und wählt per Objekt-ID.
  - Pod 021, Jaspera Sentinel: „{T}, Tap an untapped creature you control: Add one mana of any
    color.“ wird angeboten, wenn der Sentinel die einzige Kreatur ist; die Aktivierung scheitert
    („mana activation failed“), weil das eigene {T} sie schon getappt hat. Der Pilot zahlt nicht mit
    solchen Kosten, wenn keine weitere ungetappte Kreatur da ist (`tap_creature_cost_unpayable`).
  Mit diesen Änderungen laufen 007, 018 und 021 durch (6019, 2228 und 4674 Entscheidungen; ein Spiel
  je Pod, keine Passquote). Pilotvergleich vorher/nachher auf zehn Seeds (1–10, gleiches Jar):
  alle Zähler identisch.
- Familiensuche Plan-Seeds 11 und 12 auf dem Pin `769e6ebb` (Spiel-Seed gleich dem Plan-Seed, gleiche 182
  Decks, `LOCAL_OBSERVED`, Jar aus `main` `d74dd708`, Pilot von `main` `8f4665b`): Seed 11 läuft mit
  45 von 46 Pods durch, Seed 12 mit 40 von 46 im Sweep und 45 von 46 nach den Einzelläufen unten. Zwei
  Abbrüche liegen im Piloten (die Bridge bleibt unverändert, keine Requalifizierung), einer ist ein
  gültiges Spiel, das nicht endet:
  - Seed 11, Pod 013, Numa, Joraga Chieftain: Numa zahlt `{X}{X}`, fragt X aber mit „Announce the value
    for {X} (pay to distribute counters)“ ab. Der Pilot las das nicht als Mana-X und nannte die
    Obergrenze der Engine; doppelt gezählt läuft sie über, die Zahlung kostete nichts und zwei
    Milliarden Marken wurden verteilt. Der Pilot liest die Ansage jetzt als Mana-X mit zwei Symbolen
    (`_PAID_X_PROMPT` in `common.py`) und bleibt in dem Band, das die Quellen bezahlen.
  - Seed 12, Pod 006, Tayam, Luminous Enigma: „{3}, Remove three counters from creatures you control“
    ist bei `769e6ebb` eine `RemoveCounterCost` mit bis zu drei Kreaturen. Die Engine nimmt von jeder
    gewählten Kreatur Marken einer einzigen Art und fragt nur dann nach der Menge, wenn noch mehr als
    eine fehlt und der Stapel größer als eins ist. Der Pilot prüfte nur die Summe aller Marken
    (und las Tayams Wortlaut ohne „among“ gar nicht), wählte Kreaturen mit je einer Marke und eine
    beliebige Markenart; die Kosten kamen nicht zusammen (`XMAGE_ACTION_EXECUTION_FAILED`). Der Pilot
    prüft jetzt, ob die größten Stapel je Kreatur zusammen die Zahl ergeben
    (`spread_counter_cost_unpayable`), wählt die Kreaturen nach dem größten Stapel zuerst und hört auf,
    sobald die Zahl gedeckt ist, nimmt von der Kreatur die Markenart mit dem größten Stapel und
    antwortet auf „Choose how many counters“ mit dem Höchstwert (`_decide_counter_cost_objects`,
    `_counter_type_for_cost`).
  - Seed 12, Pod 016: kein Pilotfehler. Ashaya, Soul of the Wild, Scute Swarm, Zimone und Retreat to
    Coralhelm lassen die Landfall-Trigger exponentiell wachsen (9 Insekten in Zug 42, 243 in Zug 44, 498
    in Zug 46, etwa 1000 Trigger gleichzeitig auf dem Stapel). Jedes Land erzeugt dann tausende
    Reihenfolge-Entscheidungen mit einem Zustand von 500 Permanenten, das Spiel braucht über zehn
    Minuten und endet nicht. Das Spiel ist regelkonform und bleibt unbehoben (Familie „Trigger-Explosion“).
    Die Pods 012 bis 015 desselben Batches meldeten „shutdown not
    graceful“, weil die JVM beim Abbruch des hängenden Spiels starb; einzeln laufen sie durch (3020,
    2847, 3556 und 5401 Entscheidungen).
  Mit den Änderungen laufen Seed 11 Pod 013 (2046 Entscheidungen) und Seed 12 Pod 006 (2611
  Entscheidungen) durch; ein Spiel je Pod, keine Passquote. Pilotvergleich vorher/nachher auf zehn
  Seeds (1–10, gleiches Jar): alle Zähler identisch.
- Familiensuche Plan-Seeds 13 bis 16 auf dem Pin `769e6ebb` (Spiel-Seed gleich dem Plan-Seed, gleiche 182
  Decks, `LOCAL_OBSERVED`, Jar aus `main` `d74dd708`, Pilot von `main` `1531f5f`): Seed 14 läuft mit
  46 von 46 Pods durch, die Seeds 13, 15 und 16 mit je 45 von 46. Ein Abbruch liegt in der Bridge,
  zwei im Piloten (die Bridge bleibt unverändert, keine Requalifizierung):
  - Seed 13, Pod 040: `PLAYER_LEFT_GAME_UNSUPPORTED_DECISION: replacement_effect`. Ein Spieler
    scheidet im Kampfschaden aus, die Engine fragt ihn danach noch nach einem Ersatzeffekt. Die Bridge
    beendet das Spiel für diese Klasse absichtlich (deklarierte Fail-closed-Klasse, auch der Zwillingstest
    kennt sie); eine Lösung wäre eine Bridge-Änderung mit Requalifizierung und bleibt offen.
  - Seed 15, Pod 018, Ion Storm: „{1}{R}, Remove a +1/+1 counter or a charge counter from a permanent
    you control“ ist eine `OrCost` aus zwei `RemoveCounterCost` mit einem unfiltrierten
    `TargetControlledPermanent`. Die Engine bietet jede eigene Permanente an und scheitert, wenn die
    gewählte keine Marke der Art trägt (`XMAGE_ACTION_EXECUTION_FAILED`); der Pilot hatte ein Land
    gewählt. Der Pilot aktiviert Ion Storm nur noch, wenn eine der genannten Markenarten auf dem Tisch
    liegt (`single_counter_cost_unpayable`), antwortet auf die Frage nach der Art mit der Art, die er
    hat, und wählt die Permanente mit dem größten Stapel dieser Art (`_decide_kind_cost_object`).
  - Seed 16, Pod 018, Encore: `XMAGE_INTERNAL_ERRORS` mit `NoSuchElementException` in `EncoreEffect`.
    Encore erzeugt eine Spielfigur je Gegner im Spiel (`getOpponentsInGame`) und läuft dann über die
    Gegner des Rundenstart-Schnappschusses (`getOpponents`), der einen in dieser Runde ausgeschiedenen
    Spieler noch nennt: eine Figur zu wenig. Das ist ein Fehler der Engine, den der Pilot umgeht: er
    aktiviert Encore nicht mehr, sobald ein Gegner ausgeschieden ist (`_ENCORE_LABEL`). Den
    Schnappschuss sieht der Pilot nicht, deshalb gilt das ab dem ersten Ausscheiden.
  Mit den Änderungen laufen Seed 15 Pod 018 (4228 Entscheidungen) und Seed 16 Pod 018 (2808
  Entscheidungen) durch; ein Spiel je Pod, keine Passquote. Pilotvergleich vorher/nachher auf zehn
  Seeds (1–10, gleiches Jar): alle Entscheidungszähler identisch; nur die Laufzeiten liegen auf
  dieser Maschine beide um etwa 12 % höher (`wall_s` und `pilot_s`, bei gleichen Entscheidungen
  also Maschinenrauschen, nicht der Pilot).
- Familiensuche Plan-Seeds 17 bis 20 auf dem Pin `769e6ebb` (Spiel-Seed gleich dem Plan-Seed, gleiche 182
  Decks, `LOCAL_OBSERVED`, Jar aus `main` `d74dd708`, Pilot von `main` `4501d6e`): Die Seeds 17 und 18
  laufen mit 46 von 46 Pods durch, die Seeds 19 und 20 mit je 45 von 46. Ein Abbruch liegt im Piloten,
  einer in der Engine (die Bridge bleibt unverändert, keine Requalifizierung):
  - Seed 19, Pod 019 (Prosperous Bandit): `priority cast failed`, bevor irgendeine Zahlung beginnt.
    Ein Gegner hat Bruna und Gisela zu Brisela, Voice of Nightmares verschmolzen („Your opponents
    can't cast spells with mana value 3 or less“). Die Sperre ist ein `CAST_SPELL_LATE`-Ersatzeffekt,
    der den Zauber über `game.getStack().getSpell(...)` liest, also erst, wenn er schon auf dem Stack
    liegt. Die
    Spielbar-Liste der Engine fragt davor, findet keinen Zauber und bietet den Cast an; der echte Cast
    wird nach der ersten Frage (hier die Offspring-Frage) in `AbilityImpl.activate` verworfen, und die
    Bridge hat keinen Beleg für eine Rückabwicklung. Der Pilot hält Zauber zurück, die Brisela
    (Manawert 3 oder weniger) oder Void Winnower (gerade Manawerte, X-Zauber) eines Gegners sperrt
    (`cast_locked_by_mana_value`). Void Winnower (Deck `2026_odds_and_ends`) liest den Zauber im
    Quelltext auf dieselbe Weise, ist aber noch in keinem Sweep zum Abbruch geworden und nur durch Tests
    belegt; Sanctum Prelate gleicht in der Form, nennt eine gewählte Zahl, die der Pilot nicht sieht,
    und steht in keinem Precon-Deck.
    Seed 19 Pod 019 läuft jetzt durch (2258 Entscheidungen).
  - Seed 20, Pod 008: `XMAGE_INTERNAL_ERRORS` mit `NullPointerException` in
    `ProtectorOfTheWastesTriggeredAbility.checkTrigger` (`event.getSourceId().equals(...)`). Kehrt eine
    Aura aus dem Friedhof auf das Schlachtfeld zurück (hier Screams from Within nach Tip the Scales),
    läuft das über `AuraReplacementEffect` ohne Quelle, und das Eintreten-Ereignis hat keine
    `sourceId`; Protector of the Wastes (im selben Spiel) liest sie ohne Nullprüfung. Das ist ein
    Fehler der Engine (im neueren Fork-Checkout unverändert), den der Pilot nicht umgehen kann, ohne
    einen Massenentferner oder Gegner-Auren zu meiden. Eine Lösung wäre eine Fork-Änderung (nullsichere
    Prüfung in `ProtectorOfTheWastes`: das Eintreten-Ereignis nennt das eintretende Objekt als Ziel,
    nicht als Quelle). Vier ähnlich gebaute Karten (`IvoraInsatiableHeir`, `JadeOrbOfDragonkind`,
    `MisfortuneTeller`, `TomeboundLich`) lesen für das Eintreten die Ziel-ID und sind nicht betroffen.
    Die Änderung liegt als Patch vor (`/mnt/project-files/fork-fixes-2026-10-21/`); ein Fork-Push
    braucht Hans' Go.
  Ein Spiel je Pod, keine Passquote. Pilotvergleich vorher/nachher auf zehn Seeds (1–10, gleiches Jar):
  alle Entscheidungs- und Verhaltenszähler identisch; nur `wall_s` liegt im zweiten Lauf um etwa 12 %
  höher (`pilot_s` innerhalb des Konfidenzintervalls gleich), also Maschinenrauschen, nicht der Pilot.
- Familiensuche Plan-Seeds 1 bis 3 mit Spiel-Seed +100 (101 bis 103) auf dem Pin `769e6ebb` (gleiche 182
  Decks, `LOCAL_OBSERVED`, Jar aus `main` `d74dd708`, Pilot von `main` `e1b873c`): Seed 102 läuft mit 46 von
  46 Pods durch, die Seeds 101 und 103 mit je 45 von 46. Beide Abbrüche lagen im Piloten (die Bridge
  und die Engine bleiben unverändert):
  - Seed 101, Pod 024 (Necron Overlord, Illuminor Szeras): `XMAGE_ACTION_EXECUTION_FAILED: priority
    activation failed` in Zug 48. Zwei Ursachen hintereinander. Erstens kündigte der Pilot für Necron
    Overlords „{X}, {T}, Tap X untapped artifacts you control" X = 14 an (so viel Mana seine 13 Sümpfe
    und Szeras hergeben); die Engine begrenzt dieses X nicht, und die Tap-Kosten fanden nur wenige
    Artefakte (`option_x_tap_cap`: X bleibt bei den ungetappten Artefakten, die ein Kartenkatalog als
    Artefakt kennt, ohne die Quelle selbst; unbekannte Karten und Spielsteine zählen nicht, was den
    Deckel nur senkt). Zweitens zahlte der Pilot das Mana mit Szeras' Fähigkeit („{T}, Sacrifice
    another creature: Add {B}…") und opferte dafür Necron Overlord selbst: dessen eigene {T}-Kosten
    fanden danach keine Quelle, die Aktivierung wurde zurückgenommen. Das Opfer innerhalb einer Zahlung
    nimmt jetzt nie die Quelle der bezahlten Aktivierung (`_without_payment_source`), solange eine
    andere Wahl da ist. Die frühere Beobachtung auf dem alten Pin („Kosten mit Auswahl: Ghave, Necron
    Overlord, Grim Hireling, die Engine bietet die Aktivierung an, kann sie aber nicht ausführen") hat
    für Necron Overlord damit ihre Ursache. Pod 024 läuft jetzt durch (4563 Entscheidungen).
  - Seed 103, Pod 002 (Sinister Concierge): `XMAGE_INTERNAL_ERRORS` mit `IllegalArgumentException: Card
    must be in exile zone: Vampire Token`. Sinister Concierge exiliert „up to one target creature" und
    gibt der exilierten Karte dann Suspend; ein Spielstein bleibt nicht im Exil, und
    `SuspendAbility.addTimeCountersAndSuspend` wirft. Der Pilot zielte auf den Vampire Token des
    Gegners. Die Karte kennt der Katalog nicht als Sonderfall, also steht sie in
    `_EXILE_AND_SUSPEND_TARGETERS`, und ein Ziel, dessen Name auf „ Token" endet, wird für sie nicht
    angeboten („up to one" bleibt offen, der Pilot darf auch niemanden wählen). Eine Fork-Änderung
    (`instanceof PermanentToken` in `SinisterConciergeEffect`) wäre die Engine-Seite und ist nicht
    nötig. Pod 002 läuft jetzt durch (4774 Entscheidungen).
  Ein Spiel je Pod, keine Passquote. Pilotvergleich vorher/nachher auf zehn Seeds (1–10, gleiches
  Jar): alle Entscheidungs- und Verhaltenszähler identisch; nur `wall_s` liegt im zweiten Lauf um
  etwa 21 % niedriger (`pilot_s` innerhalb des Konfidenzintervalls gleich), also Maschinenrauschen,
  nicht der Pilot.
- Familiensuche Plan-Seeds 4 bis 6 mit Spiel-Seed +100 (104 bis 106) auf dem Pin `769e6ebb` (gleiche 182
  Decks, `LOCAL_OBSERVED`, Jar aus `main` `d74dd708`): Seed 105 läuft mit 46 von 46 Pods durch. Mit dem
  Piloten von `main` `5991d9d` (nach #952) fielen Seed 104 zwei Pods (014, 022) und Seed 106 vier Pods
  (026, 040, 043, 044) aus. Alle Abbrüche lagen im Piloten (Bridge und Engine bleiben unverändert); mit
  den Fixes läuft jeder Seed mit 46 von 46 Pods durch (Wiederholungslauf der Seeds 104 und 106).
  - Seed 104, Pods 014 und 022, Seed 106, Pod 026: „policy produced 1 selections outside 2..2 for
    choose_object" (Breya, Etherium Shaper: „Sacrifice two artifacts" mit Breya und einem Thopter) und
    der gleiche Fall mit „3..3". Das war eine Regression aus #952: `_without_payment_source` nahm die
    Quelle der bezahlten Aktivierung aus *jeder* Opferwahl, auch aus der eigenen Opferkosten-Wahl der
    Aktivierung und aus Wahlen, die ohne die Quelle weniger Optionen als die Mindestzahl hätten. Jetzt
    bleibt die Quelle im Angebot, wenn der Rest die Mindestzahl nicht füllt, und die Opferwahl, die die
    Aktivierung selbst stellt (gleiche Quelle), wird nicht gefiltert. Zwei neue Tests in
    `test_full_game_pilot_mana_and_may.py` (rot ohne, grün mit der Änderung). Pod 026 war nur im
    JVM-Stapel des Sweeps rot und lief einzeln mit dem alten Piloten ebenfalls in den Fehler; mit dem
    Fix läuft er durch.
  - Seed 106, Pod 040 (Moxite Refinery): `XMAGE_ACTION_EXECUTION_FAILED: priority activation failed`
    (AbilityImpl-Zeile 472, Nicht-Mana-Kosten) in Zug 43. „{2}, {T}, Remove X counters from an artifact
    or creature you control" bekam X = 40 (Obergrenze des Bereichs); die Engine begrenzt weder X noch
    die Wahl von Karte und Zählerart und kehrt die Aktivierung um, wenn der gewählte Stapel kleiner
    ist. `x_counter_pile_cap` hält X beim größten Zählerstapel einer Karte der genannten Typen
    (Kartenkatalog; unbekannte Karten zählen nicht, was den Deckel nur senkt); Karte und Zählerart
    folgen der Stapelwahl für feste Zahlen (`_decide_counter_cost_objects`,
    `_counter_type_for_cost`) mit dem angesagten X. Die Pods 043 und 044 desselben JVM-Stapels fielen mit
    derselben Diagnose-Prüfsumme nach dem Abbruch von Pod 040 mit aus und liefen einzeln durch. Neue
    Datei `test_x_counter_pile_920.py` (rot ohne, grün mit der Änderung).
  Ein Spiel je Pod, keine Passquote. Pilotvergleich vorher/nachher auf zehn Seeds (1–10, gleiches Jar,
  Pilot von `main` `5991d9d` gegen diesen Stand): alle Entscheidungs- und Verhaltenszähler identisch
  (36268 Entscheidungen); `wall_s` und `pilot_s` unterscheiden sich nur durch Maschinenrauschen.
- Familiensuche Plan-Seeds 7 bis 17 mit Spiel-Seed +100 (107 bis 117) auf dem Pin `769e6ebb` (gleiche 182
  Decks, `LOCAL_OBSERVED`, Jar aus `main` `d74dd708`): die Seeds 107 bis 113, 116 und 117 laufen mit 46 von
  46 Pods durch (Piloten von `main` `b010543` bis `d2d8f15`, je ein Spiel je Pod, 414 Spiele). Seed 114 und
  115 verlieren je einen Pod, beide im Piloten (Bridge und Engine unverändert):
  - Seed 114, Pod 004 (Hazel of the Rootbloom): `XMAGE_ACTION_EXECUTION_FAILED: mana activation failed`.
    „{T}, Pay 2 life, Tap X untapped tokens you control: Add X mana" fragt „Announce the value for {X}
    (untapped tokens you control to tap)". Hazel war selbst eine Token-Kopie, die Engine zählt sie in der
    Obergrenze (`numeric_max` 1) mit, ihr eigenes `{T}` tappt sie zuerst, die Tap-Kosten finden nichts und die
    Mana-Fähigkeit wird umgekehrt. Der Prompt ist kein Mana-X, die Mana-Obergrenze griff also nicht.
    `x_tap_prompt_cap` (`full_game_pilot/common.py`) liest die Tap-X-Form des Prompts und zählt die
    ungetappten Token neben der Quelle (Token = Name endet auf „ Token", die Sicht hat kein Token-Feld; eine
    Quelle ohne eigenes `{T}` zählt sich selbst), `option_x_tap_cap` kennt dieselben Token, und
    `_priority_action_affordable` hält eine Mana-Fähigkeit mit Tap-X ohne Ziel zurück, statt 2 Leben für kein
    Mana zu zahlen. Neue Datei `test_tap_x_tokens_920.py` (drei Tests rot ohne, grün mit der Änderung).
  - Seed 115, Pod 026 (Alchemist's Refuge): `priority activation failed`. Für „{G}{U}, {T}: You may cast spells
    this turn as though they had flash" zahlte der Pilot einen Teil der {G}{U} mit dem Refuge selbst
    („{T}: Add {C}"); die Mana-Kosten werden zuerst bezahlt, das `{T}` der Aktivierung findet die Quelle
    getappt. Gleiche Ursache wie die Opferkosten in #952. `_last_priority_source` merkt die Quelle der
    gewählten Aktion, `_spends_the_activations_own_source` hält deren Mana-Fähigkeiten aus der Zahlung
    zurück, wenn der Kostenteil des Labels `{T}` enthält. Neue Datei `test_own_source_payment_920.py`
    (rot ohne, grün mit der Änderung; Gegenproben: andere Quelle, Aktivierung ohne `{T}`).
  Beide Pods laufen mit den Fixes durch (einzeln auf demselben Jar).
  Pod 044 des Seeds 6 (Plan- und Spiel-Seed 6) wechselt auf Live-Pin zwischen zwei Hashes, weil Wurmcoil
  Engine seine zwei Wurm-Token in zufälliger Reihenfolge anlegt (`CreateTokenEvent`-`HashMap`,
  `TokenImpl`-`HashSet`, Token ohne `hashCode`); das ist eine Fork-Änderung und steht nicht in diesem PR.
  Ein Spiel je Pod, keine Passquote. Pilotvergleich vorher/nachher auf zehn Seeds (1–10, gleiches Jar, aus dem
  Tempt-Jar und den Klassen des Pins `456b0e22` zusammengesetzt, Pilot von `main` `f14a191` gegen diesen Stand): alle Entscheidungs- und
  Verhaltenszähler identisch (36268 Entscheidungen); `wall_s` und `pilot_s` unterscheiden sich nur durch
  Maschinenrauschen (`pilot_s` +0,29 s je Spiel bei vier parallel laufenden Sweeps; die neuen Prüfungen
  kosten unter einer Mikrosekunde je Aufruf).
- Familiensuche Plan-Seeds 18 und 19 mit Spiel-Seed +100 (118, 119) auf dem Live-Pin `456b0e22` (Repin v11,
  `LOCAL_OBSERVED`, Jar aus dem Tempt-Jar, den Klassen des Pins und den Bridge-Klassen von `main` `f14a191`,
  Pilot von `main` `84e245a`): Seed 118 läuft mit 46 von 46 Pods durch, Seed 119 mit 45 von 46. Der Abbruch
  liegt im Piloten (Bridge und Engine unverändert):
  - Seed 119, Pod 013 (Necron Overlord): `XMAGE_ACTION_EXECUTION_FAILED`. „{X}, {T}, Tap an artifact you
    control" bezahlte der Pilot zuerst mit dem Sceptre of Eternal Glory; danach fragt die Engine „Select an
    artifact you control" (Kontext `outcome` `tap`) und bietet auch die schon getappten Artefakte an (das
    Sceptre, dazu das Overlord selbst, das sein eigenes `{T}` getappt hat). Der Pilot wählte das Sceptre, die
    Tap-Kosten schlugen fehl und die Aktivierung wurde umgekehrt. `_without_tapped_objects`
    (`full_game_pilot/state.py`) nimmt bei `outcome` `tap` die Permanents aus der Auswahl, die in der Sicht
    des Spielers getappt sind; bleibt keines übrig oder weniger als das Minimum, bleibt die Liste unverändert.
    Neue Datei `test_tap_cost_untapped_920.py` (ein Test rot ohne, grün mit der Änderung; Gegenproben: nichts
    getappt, alles getappt, Minimum zwei, anderer Ausgang). Pod 013 läuft mit der Änderung durch (4714
    Entscheidungen, Gewinner Sitz 1). Pilotvergleich auf zehn Seeds (1–10, gleiches Jar, Pilot von `main`
    `84e245a` gegen diesen Stand): alle Entscheidungs- und Verhaltenszähler identisch (4095 Entscheidungen im
    ersten Spiel, 36268 insgesamt), nur `wall_s` und `pilot_s` unterscheiden sich durch Maschinenrauschen.
- Familiensuche Plan-Seeds 1 bis 6 und 20 mit Spiel-Seed +200 (201 bis 206) und +100 (120) auf dem Live-Pin
  `456b0e22` (gleiches Jar wie oben, Pilot von `main` `8b74950`, `LOCAL_OBSERVED`, je ein Spiel je Pod):
  Seed 120, 204 und 205 laufen mit 46 von 46 Pods durch, Seed 201, 202, 203 und 206 mit je 45 von 46. Bridge
  und Engine unverändert; drei der vier Abbrüche liegen im Piloten, einer ist ein Lastflake:
  - Seed 201, Pod 024: `BRIDGE_ERROR` nach 245 s, während vier Sweeps und mehrere Replays gleichzeitig
    liefen. Einzeln auf demselben Jar läuft der Pod durch (4603 Entscheidungen); nicht reproduzierbar, kein
    Pilotfall.
  - Seed 202, Pod 037 (Capricopian): `ENGINE_FAILURE`, drei `NullPointerException` in
    `PlayerIdPredicate` (`CapricopianEffect.apply`). „{2}: Put a +1/+1 counter on Capricopian, then you may
    reselect which player it is attacking" darf nur der angegriffene Spieler aktivieren; der Pilot tat es
    als Verteidiger, sechs Mal in drei Paaren mit der ersten Aktivierung noch auf dem Stapel. Die Karte baut
    ihren Spielerfilter mit `game.getCombat().getDefenderId(...)`, und das ist null, sobald die Kreatur nicht
    (mehr) im Kampf ist (vermutlich nach der ersten Auflösung, die sie verlegt). `_turn_action_cap`
    (`full_game_pilot/state.py`) lässt Fähigkeiten eines Permanents, das ein Gegner kontrolliert, nur einmal je
    Zug zu (die Fähigkeit dient dem Angreifer wie dem Aktivierenden). Neue Datei
    `test_opposing_ability_cap_920.py` (ein Test rot ohne, grün mit der Änderung; Gegenproben: einmal erlaubt,
    eigenes Permanent behält die normale Obergrenze). Die Null-Prüfung in der Karte selbst wäre eine
    Fork-Änderung und steht nicht in diesem PR.
  - Seed 203, Pod 026 (Trazyn the Infinite): `XMAGE_ACTION_EXECUTION_FAILED`. „{X}, {T}, Tap X untapped
    artifacts you control" wurde mit X = 1 für das einzige ungetappte Artefakt neben Trazyn angesagt; den
    {X}-Teil bezahlte der Pilot danach mit eben diesem Artefakt (Sol Ring), die Tap-Kosten fanden nichts.
    `tap_cost_needs_permanent` (`full_game_pilot/common.py`) liest „Tap X/an/zwei untapped … you control" aus
    dem Label der gewählten Aktion (X aus der eigenen Ansage) und `_spends_a_permanent_the_tap_cost_needs`
    (`payment.py`) hält Mana-Fähigkeiten zurück, deren Quelle die Kosten sonst unterdeckt. Neue Datei
    `test_tap_cost_reserve_920.py` (ein Zahlungstest rot ohne, grün mit der Änderung; Lesetests und
    Gegenproben: zweites Artefakt, X = 2, Nicht-Artefakt, Kosten ohnehin nicht deckbar).
  - Seed 206, Pod 039 (Slaughter the Strong): `ENGINE_FAILURE` durch das Limit von 50000 Entscheidungen.
    Passt nach den Wahlen des Piloten kein Geschöpf mehr in die restliche Gesamtstärke, überspringt die
    Engine die Wahl und fragt „End the selection" oder „Continue the selection" erneut; der Pilot antwortete
    jedes Mal „Continue". `_selection_reopened` (`state.py`, `choices.py`) merkt ein „Continue" und beantwortet
    dieselbe Frage ohne Wahl dazwischen mit „End". Neue Datei `test_selection_reopened_920.py` (zwei Tests
    rot ohne, grün mit der Änderung; Gegenproben: erste Frage unverändert, eine Wahl dazwischen löscht die
    Merkung).
  Die drei Pods laufen mit den Fixes durch (Pod 037: 1940, Pod 026: 3595, Pod 039: 4109 Entscheidungen, einzeln
  auf demselben Jar). Pilotvergleich auf zehn Seeds (1–10, gleiches Jar, `main` `8b74950` gegen diesen Stand):
  alle Entscheidungs- und Verhaltenszähler identisch (36268 Entscheidungen); `wall_s` und `pilot_s`
  unterscheiden sich nur durch Maschinenrauschen.
- Familiensuche Plan-Seeds 1 bis 4 mit Spiel-Seed +400 (401 bis 404) und +500 (501 bis 504) auf dem Live-Pin
  `456b0e22` (gleiches Jar wie oben, Pilot von `main` `981a4f8`, `LOCAL_OBSERVED`, je ein Spiel je Pod): Seed 402,
  403, 404, 406, 502, 503 und 504 laufen mit 46 von 46 Pods durch, Seed 401, 405 und 501 mit je 45 von 46. Bridge
  und Engine unverändert; zwei der drei Abbrüche liegen im Piloten, einer ist ein Lastflake:
  - Seed 405, Pod 012: `INVALID_RESPONSE` unter mehreren gleichzeitigen Sweeps; einzeln läuft der Pod durch,
    nicht reproduzierbar, kein Pilotfall.
  - Seed 501, Pod 010 (Yuriko, the Tiger's Shadow): `XMAGE_ACTION_EXECUTION_FAILED`. Das Commander ninjutsu
    wurde für eine Yuriko angeboten, die weder in der Hand noch in der Befehlszone lag (Aminatou war der
    Commander des Spielers, Yuriko lag in der Bibliothek). Die Fähigkeit ist in XMage eine `Zone.ALL`-Fähigkeit,
    die Aufdeckkosten scheitern nach dem Bezahlen des Manas. `ninjutsu_card_outside_hand`
    (`full_game_pilot_views.py`) kennt jetzt auch diesen Fall: Karten, die die Sicht des Spielers weder in Hand
    noch Befehlszone führt, werden nicht aktiviert (bisher nur Schlachtfeld, Friedhof, Exil). Zwei neue Tests in
    `test_full_game_pilot_mana_and_may.py` (einer rot ohne, grün mit der Änderung; Gegenprobe: Ninja in der
    Befehlszone wird weiter aktiviert).
  - Seed 401, Pod 017 (Flourishing Defenses gegen Blowfly Infestation): `ENGINE_FAILURE` durch das Limit von
    50000 Entscheidungen. „Whenever a -1/-1 counter is put on a creature, you may create a 1/1 Elf Warrior"
    und die Gegenkarte, die den nächsten -1/-1-Marker auf den neuen Token legt, ergeben eine Schleife mit
    bis zu 199 Fähigkeiten auf dem Stapel. XMage fragt alle fünfzehn Runden „Draw game because of infinite
    looping?"; der Pilot antwortete jedes Mal Nein. Die Fortführung ist eine Wahl des Piloten (die Schleife
    ließe sich mit einem Nein auf den Elf-Trigger brechen), die Frage der Engine ist aber der regelgemäße
    Ausgang (CR 104.4b): `_INFINITE_LOOP_PROMPT` (`full_game_pilot/choices.py`) behält die Ja-Option, das
    Spiel endet als Remis. Neue Datei `test_infinite_loop_draw_920.py` (zwei Tests rot ohne, grün mit der
    Änderung; Gegenprobe: andere Detriment-Fragen bleiben unverändert).
  Beide Pods laufen mit den Fixes durch (Pod 501/010: 2948 Entscheidungen; Pod 401/017: 5820 Entscheidungen,
  Remis, einzeln auf demselben Jar). Pilotvergleich auf zehn Seeds (1–10, gleiches Jar, `main` `981a4f8` gegen
  diesen Stand): alle Entscheidungs- und Verhaltenszähler identisch (36268 Entscheidungen); `wall_s` und
  `pilot_s` unterscheiden sich nur durch Maschinenrauschen.
- Determinismus-Zensus Plan-Seed 21 (Spiel-Seed 21) auf dem Pin `769e6ebb` (Lab `f50a1f754`, Muses eigenes
  Jar, `--games-per-jvm 6 --fast`, zwei Läufe, `LOCAL_OBSERVED`): 43 Pods laufen in beiden Läufen durch
  und liefern denselben Hash, Pod 010 fällt in beiden Läufen mit `BLOCK_DECLARATION_REJECTED` aus.
  - Pod 010 (Kaalia of the Vast gegen Scarlet Witch, Chaotic Avenger, Zug 45): Predatory Impetus lag auf
    Kaalia („must be blocked if able"), die Engine lehnte deshalb die leere Erklärung und den Block des
    Reiver Demon ab, den anderen Angreifer des Rahmens. Die Leiter des Piloten (Urteil, größte
    Erklärung, leere Erklärung, Abbruch) legte bei einem Rahmen mit einem Block und zwei Angreifern nur
    den bestbewerteten Block vor und nie den Block von Kaalia. Nach der leeren Erklärung erklärt der
    Pilot jetzt jeden einzelnen Block, den die früheren Antworten ausließen, und bricht erst danach ab;
    die ersten drei Antworten sind unverändert. Neuer Test in `test_full_game_pilot_judgment.py` (rot
    ohne, grün mit der Änderung). Einzeln nachgespielt (Muses Jar-Stand, `main`-Pilot ohne Pod-Wechsel):
    vorher `BLOCK_DECLARATION_REJECTED` in Zug 45, mit dem Fix 2880 Entscheidungen, Sitz 2 gewinnt.
- Determinismus-Zensus Plan-Seeds 24 bis 30 (Spiel-Seed gleich) auf dem Pin v11 `456b0e22` (Lab `84e245ace`,
  Muses v11-Jar, `--games-per-jvm 6 --fast`, zwei Läufe je Seed, `LOCAL_OBSERVED`): 644 Pod-Läufe, 636 ok,
  8 failed. Vier Pods liefern in den zwei Läufen verschiedene Hashes (Seed 24 Pod 030, Seed 27 Pod 028,
  Seed 30 Pod 005 und 036); Ursache `CODE_DERIVED` aus Muses Schritt C: `HashMap<Player, Integer>`
  (Wave of Vitriol) und `HashMap<UUID, Integer>` (From the Ashes) iterieren je Spiel in anderer
  Reihenfolge, behoben erst mit einem Fork-Patch (`LinkedHashMap`), nicht in diesem PR. Drei Pods
  fielen echt aus und liefen vorher nicht, alle drei einzeln nachgespielt (`main`-Pilot, v11-Jar):
  - Seed 30 Pod 045 (`XMAGE_ACTION_EXECUTION_FAILED`, The Prydwen, Steel Flagship, Crew 2): Die Engine
    fragt Crew und Saddle eine Kreatur nach der anderen ("selected power S of N") und beendet die
    Zahlung bei einer leeren Antwort. Der Pilot wählte bei jeder Frage eine Kreatur: Rex (Kraft 0),
    Brotherhood Scribe (-1), Sentinel Sarah Lyons (2) und Dr. Madison Li (0) kamen auf 1, die Kosten
    scheiterten, obwohl Sarah allein gereicht hätte. Jetzt kommen nur Kreaturen mit Kraft über 0 in
    Frage (Kreaturen, die mit Zähigkeit crewen, bleiben), und bei erreichter Kraft wählt der Pilot
    keine weitere. Neue Datei `test_crew_power_selection.py`. Vorher Abbruch, jetzt 3011 Entscheidungen.
  - Seed 29 Pod 000 (`XMAGE_ACTION_EXECUTION_FAILED`, Hierophant Bio-Titan): Der Pilot kündigte X = 3
    Zählermarken an (zwei bei The Swarmlord, eine bei Haruspex) und zahlte das gesenkte `{4}{G}{G}` zum Teil
    mit Haruspex' "Remove X +1/+1 counters from {this}: Add X mana". Für die Kosten blieben zwei Marken,
    der Zauber wurde zurückgesetzt. Die angekündigten Marken gehören jetzt den Kosten des Zaubers: Keine
    Manafähigkeit entfernt sie, und die Kosten nehmen die größten Stapel, bis die Zahl gedeckt ist.
    Neue Datei `test_cast_counter_cost_reserved.py`. Vorher Abbruch, jetzt 2538 Entscheidungen.
  - Seed 30 Pod 026 (`ENGINE_FAILURE`): Auf Muses Lab-Stand `84e245ace` bricht das Spiel bei
    `max_decisions=50000` ab (335 s), eine Pilot-Schleife. Auf `main` läuft der Pod durch (5940
    Entscheidungen, Sitz 2 gewinnt, gleicher Hash mit dem v10-Jar); behoben durch einen der Pilot-Fixes
    seit `84e245ace`, ohne eigene Änderung hier.
- Alter Pin `348b37db`, Stichprobe (25 Pods aus je vier verschiedenen Decks, Seed 1, nur Decks
  ohne fehlende Karten, `LOCAL_OBSERVED`): 19 Pods liefen durch, 6 scheiterten in vier Familien:
  Kosten mit Auswahl (Ghave, Necron Overlord, Grim Hireling: die Engine bietet die Aktivierung
  an, kann sie aber nicht ausführen), modaler Zauber mit Escalate (Collective Effort),
  Doppelseiten-Identität (inzwischen durch den Daten-Fix behoben) und ein
  `DECISION_ADVANCE_TIMEOUT` in `DistributeCountersEffect` (Ursache unbekannt, zweimal
  reproduziert). Eine Stichprobe ist keine Passquote.

## Reproduktion

```
python scripts/measure_precon_imports.py --jar <bridge.jar> --workdir <leeres Verzeichnis> --out imports.json --enumerate-missing
python scripts/precon_pod_sweep.py --jar <bridge.jar> --out sweep.json --import-report imports.json
# die 13 SYNTHETIC-Proxies: erzeugen, prüfen, importieren, zusammen mit den 182 echten spielen
python scripts/build_precon_variants.py --check
python scripts/measure_precon_imports.py --jar <bridge.jar> --workdir <leeres Verzeichnis> --out proxies.json --deck-dir data/decks/precon_variants
python scripts/precon_pod_sweep.py --jar <bridge.jar> --out sweep.json --import-report imports.json --synthetic-proxies
```

`--enumerate-missing` kostet eine Minute und listet je Deck alle fehlenden Namen. Beide Skripte
brechen mit Exit-Code 2 ab, wenn die Bridge nicht verfügbar ist, und `measure_precon_imports.py`
endet mit Exit-Code 3, wenn eine Zeile ein Infrastrukturfehler statt eines Deck-Fehlers ist; ein
fehlendes JAR zählt also nicht als 195 kaputte Decks. Der Sweep über 182 Decks (46 Pods) dauerte auf
einem Rechner mit 4 Kernen gut 55 Minuten.

Immer nur ein Sweep gleichzeitig: bei CPU-Mangel werden langsame Entscheidungen zu
`BRIDGE_TIMEOUT`/`DECISION_ADVANCE_TIMEOUT` und sehen wie Engine-Fehler aus.

## Nicht belegt

- „Ein SYNTHETIC-Proxy spielt wie das gedruckte Precon“: nicht belegt und nicht gemeint. Er ersetzt 0 bis
  8 Hauptdeck-Karten, bei vier Decks den Commander; die Ersatzkarten sind importbewiesen, nicht
  funktionsgeprüft.
- „Alle 195 Decks laufen im Pod“: im gemischten Lauf (Plan-Seed 44) liefen 48 von 49 Pods; der
  Abbruch ist der Kartenfehler von Sage of the Maze (siehe „Spielbarkeit“), er trifft nur die zwei
  Tricky-Terrain-Proxies.
- „Alle Precon-Karten sind in XMage implementiert und spielbar“ (frühere Fassung dieser Datei):
  widerlegt, 31 Kartennamen fehlen am Pin, und Import beweist keine Kartenfunktion.
- „Alle 182 importierbaren Decks laufen im Pod“: ohne die Fixes (#928, Crew/Marath) widerlegt (9 von 46
  Pods brachen ab); mit ihnen lief in einem Sweep jeder der 46 Pods durch, in einem zweiten mit
  anderem Plan und Seed brach einer ab (Pia Nalaar, siehe oben). Das ist ein Spiel pro Pod und
  keine Aussage über andere Seeds oder Pläne.
- Die Zahlen „195/195 ENGINE_FAILURE“ und „221 fehlende Karten“ aus früheren Übergaben: Das
  Skript hat dasselbe Deck auf alle Plätze gesetzt, die 221 stammt aus einer
  Dateinamen-Heuristik. Beide dürfen nicht mehr zitiert werden.
