# Precon-Decks: gemessener Stand

Stand: 2026-10-20, Pin `043579bb` (XMage 1.4.62, Repin v9). Evidenzklassen nach `AGENTS.md` §4.
Alle Läufe sind lokal (`LOCAL_OBSERVED`), kein CI-Kredit.

## Bestand

`data/decks/precons/` enthält **195** Decks (2011–2026, je 100 Karten). Drei Decks mit gebannten
Karten wurden entfernt. Frühere Texte nannten 198 Decks; das stimmt nicht mehr.

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

## Spielbarkeit

**Import ist nicht Spielbarkeit.** Der Import beweist nur, dass Kartennamen und Commander
aufgelöst werden. Ob ein Deck in einem echten 4er-Pod durchspielt, zeigt `scripts/precon_pod_sweep.py`:
Pods aus vier verschiedenen Decks (derselbe Aufbau wie ein echtes Spiel; ein Deck auf mehreren
Plätzen lehnt der Validator vor dem Start ab).

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
```

`--enumerate-missing` kostet eine Minute und listet je Deck alle fehlenden Namen. Beide Skripte
brechen mit Exit-Code 2 ab, wenn die Bridge nicht verfügbar ist, und `measure_precon_imports.py`
endet mit Exit-Code 3, wenn eine Zeile ein Infrastrukturfehler statt eines Deck-Fehlers ist; ein
fehlendes JAR zählt also nicht als 195 kaputte Decks. Der Sweep über 182 Decks (46 Pods) dauerte auf
einem Rechner mit 4 Kernen gut 55 Minuten.

Immer nur ein Sweep gleichzeitig: bei CPU-Mangel werden langsame Entscheidungen zu
`BRIDGE_TIMEOUT`/`DECISION_ADVANCE_TIMEOUT` und sehen wie Engine-Fehler aus.

## Nicht belegt

- „Alle Precon-Karten sind in XMage implementiert und spielbar“ (frühere Fassung dieser Datei):
  widerlegt, 31 Kartennamen fehlen am Pin, und Import beweist keine Kartenfunktion.
- „Alle 182 importierbaren Decks laufen im Pod“: ohne die Fixes (#928, Crew/Marath) widerlegt (9 von 46
  Pods brachen ab); mit ihnen lief in einem Sweep jeder der 46 Pods durch, in einem zweiten mit
  anderem Plan und Seed brach einer ab (Pia Nalaar, siehe oben). Das ist ein Spiel pro Pod und
  keine Aussage über andere Seeds oder Pläne.
- Die Zahlen „195/195 ENGINE_FAILURE“ und „221 fehlende Karten“ aus früheren Übergaben: Das
  Skript hat dasselbe Deck auf alle Plätze gesetzt, die 221 stammt aus einer
  Dateinamen-Heuristik. Beide dürfen nicht mehr zitiert werden.
