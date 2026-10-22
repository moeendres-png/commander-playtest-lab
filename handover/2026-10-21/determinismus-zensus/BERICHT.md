# M3 — Determinismus-Zensus (Endbericht)

Auftrag: `auftrag-3-determinismus-zensus.md` inkl. Nachtrag 1 und dessen Nachbesserung
(Umstieg auf Pin v11 nach Seed 23). Reine Messung und Analyse: kein Fix im Repo,
kein PR, kein Fork-Push, kein Repin. Alle Angaben sind Zählungen je Lauf; keine
Prozent- oder Hochrechnungs-Aussagen. Evidenzklassen: LOCAL_OBSERVED für eigene
Läufe, CODE_DERIVED für Quelltext-Befunde, EXTERNAL_DATA für Referenzwerte aus
dem Auftrag/Nachtrag.

## Source Locks

| Linie | Lab-Stand | Mage-Pin (`primary_engine.commit`) | Eigenes JAR (sha256) |
|---|---|---|---|
| alt (Schritt 0/A, Seeds 21–23) | `f50a1f754096ac20f30a590f83b66357ee8de3ca` | `769e6ebbfdf1bd91eb357f63e0e6a3e848ed24b2` | `868061c9bec25323cfb93c35748a635a6e551fa087b5d59ec50ee5387c83e124` |
| v11 (p6g6, Seeds 24–30, Schritte C/D) | `84e245ace2eddf3a5c0e3befca216ad753fb0ba6` | `456b0e227cc09a90e9d485b9d932f3717ef9e2be` | `69aa31ebf15dc47c29234a711026c2caa3eb8d29efe5921a63991c22e8cd34e8` |

Der Nachtrag nannte für das Lab `43158793beaa` „oder neuer“; verwendet wurde das
zum Umstiegszeitpunkt aktuelle main `84e245ace2ed` (enthält #956). Der Pin wurde
in der ausgecheckten `config/rules_engines.json` verifiziert. Byte-Identität mit
Claudes JAR war nicht gefordert. Umgebung: Temurin 17.0.20.1, Maven 3.9.9, 2 CPUs,
7 GB RAM (`versions.txt`).

## Zusammenfassung

- **Schritt A (alte Linie):** Meine p6g6-Messung reproduziert Claudes Referenz in
  44 von 46 Pods exakt (Hash-Präfix + Entscheidungszahl). Die einzigen Abweichungen
  sind die zwei bekannten instabilen Pods 022 und 044.
- **Alte Linie, Seeds 21–23 (je 2 Läufe):** ein instabiler Pod (Seed 22, pod-004,
  gleiche Entscheidungszahl, verschiedener Hash). Fünf Fehler-Pods einzeln
  nachgefahren: einer ein Lastartefakt (21/pod-000), vier echt (21/pod-010
  Blockleiter, Fix #956; 21/pod-034 Scute-Swarm-Explosion; 22/pod-013 und
  23/pod-015 `XMAGE_ACTION_EXECUTION_FAILED` auf dem alten Stand).
- **v11, p6g6:** 46/46 ok. pod-022 trifft die Erwartung aus dem Nachtrag exakt
  (`904820b4f5b0`, 3524 Entscheidungen) — der Tempt-with-Reflections-Fix hält in
  der unabhängigen Nachmessung. pod-044 kam mit einem der zwei bekannten Hashes
  (weiter instabil, Fix nicht im Pin — erwartet). pod-006 weicht von der alten
  Linie ab, ist auf v11 aber in sich stabil (Solo = Sweep) — Stand-Unterschied
  durch die Pilot-/Bridge-Änderungen, keine Instabilität.
- **v11, Seeds 24–30 (14 Läufe, 644 Pod-Läufe):** **vier instabile Pods** —
  Seed 24 pod-030, Seed 27 pod-028, Seed 30 pod-005 und pod-036. **Acht
  Fehler-Ereignisse in fünf Pods:** zwei `BRIDGE_TIMEOUT` erwiesen sich im
  Einzelnachlauf als Artefakte (Solo ok, Hash identisch zum jeweils ok-Lauf);
  drei Pods sind echt defekt (Seed 29 pod-000 und Seed 30 pod-045
  `XMAGE_ACTION_EXECUTION_FAILED`, Seed 30 pod-026 `ENGINE_FAILURE` — jeweils in
  beiden Läufen und im Solo).
- **Schritt C:** Alle vier instabilen v11-Pods trennen sich an derselben Stelle:
  der Reihenfolge, in der ein „jeder Spieler sucht seine Bibliothek"-Effekt die
  Spieler abfragt. Ursache (CODE_DERIVED): `WaveOfVitriolEffect` sammelt die
  Spieler in einer `HashMap<Player, Integer>` und iteriert sie für die
  Entscheidungen; `FromTheAshesEffect` nutzt eine `HashMap<UUID, Integer>`.
  `PlayerImpl.hashCode()` leitet sich aus der pro Spiel zufälligen Spieler-UUID
  ab, UUIDs sind pro Spiel zufällig — die Iterationsreihenfolge wechselt daher
  von Spiel zu Spiel. Dasselbe Muster wie pod-022 (dort per `LinkedHashSet`
  behoben).
- **Schritt D:** Statischer Audit über die Karten der 182 importierbaren Decks
  (5.899 von 5.944 Namen einer Kartendatei zugeordnet): 28 iterierte Hash-Collections
  mit risikobehaftetem Schlüssel-/Elementtyp in Kartendateien, davon 20 mit
  Reihenfolge-Einfluss auf Effekte (zwei davon — die Schritt-C-Karten — zusätzlich
  auf Entscheidungen). Dazu 6 Dateien mit iterierten Enum-Mengen aus
  `Collectors.toSet()` (unklar) und mehrere geprüfte Negativbefunde. Kein
  Vollständigkeitsanspruch (heuristischer Text-Audit).

## Schritt 0 — Umgebung und Kalibrierung

Beide Linien: Mage-Teilmenge am Pin installiert, Bridge gebaut, Kalibrierung mit
`measure_precon_imports.py --enumerate-missing` gegen das eigene JAR:
**182/195 Import OK, 31 distinkte fehlende Karten** — auf beiden Ständen exakt
die Erwartung (`imports.json`, `imports_v11.json`).

## Schritt A — Gegenmessung p6g6 (alte Linie)

Eigener Sweep (workers 1, 1 Spiel/JVM), 46/46 ok, 0 failed. Pod-für-Pod gegen
Claudes Referenz (EXTERNAL_DATA): **44 identisch**; Abweichungen nur pod-022
(mein Hash `a993ad769217`, Referenz `8c846626183c`, je 3524 Entscheidungen) und
pod-044 (`88c142632960`/3389 gegen `dbddd7adb46c`/3466). **Keine neuen
Abweichungen.** Rohdaten: `sweep_p6g6_muse.json`.

## Schritt B — alte Linie (Pin 769e6ebb)

Läufe mit `--games-per-jvm 6 --fast`, je Seed zweimal (x/y).

| Seed | Lauf | Pods | ok | failed | Fehlerfamilien |
|---|---|---|---|---|---|
| 21 | x | 46 | 43 | 3 | BRIDGE_TIMEOUT ×1, BLOCK_DECLARATION_REJECTED ×1, BRIDGE_CLOSED ×1 |
| 21 | y | 46 | 44 | 2 | BLOCK_DECLARATION_REJECTED ×1, BRIDGE_CLOSED ×1 |
| 22 | x | 46 | 45 | 1 | XMAGE_ACTION_EXECUTION_FAILED ×1 |
| 22 | y | 46 | 45 | 1 | XMAGE_ACTION_EXECUTION_FAILED ×1 |
| 23 | x | 46 | 45 | 1 | XMAGE_ACTION_EXECUTION_FAILED ×1 |
| 23 | y | 46 | 45 | 1 | XMAGE_ACTION_EXECUTION_FAILED ×1 |

Hash-Vergleiche x gegen y (nur beidseitig ok):

| Seed | beidseitig ok | hash-verschieden | instabile Pods |
|---|---|---|---|
| 21 | 43 | 0 | — |
| 22 | 45 | 1 | pod-004: x `9605145dc30b` (4671), y `1a74a4410b5f` (4671) |
| 23 | 45 | 0 | — |

pod-004 (Seed 22) hat bei gleicher Entscheidungszahl verschiedene Hashes — die
Abweichung steckt in einem Zustand, der in der Entscheidungszählung nicht
sichtbar ist (Muster wie pod-044). Decks: 2018_nature_s_vengeance,
2018_built_from_scratch, 2020_arcane_maelstrom, 2016_breed_lethality. Nach der
Nachbesserung gilt Schritt C nur für v11-Pods; für pod-004 wurde daher keine
Replay-Analyse gemacht.

Einzelnachläufe der failed Pods (alte Linie, 1 Spiel, frische JVM):

| Seed | Pod | Sweep-Befund | Solo | Einordnung |
|---|---|---|---|---|
| 21 | pod-000 | BRIDGE_TIMEOUT (nur x) | ok, 62 s, Hash `38febad386f7` = y-Lauf | Lastartefakt bestätigt |
| 21 | pod-010 | BLOCK_DECLARATION_REJECTED (x+y) | failed, gleiche Familie | echt; zugeordnet: Pilot-Fehler Blockleiter, Fix Lab-PR #956 |
| 21 | pod-034 | BRIDGE_CLOSED (x+y; Batch-Walls 356/278 s) | failed BRIDGE_CLOSED, 1462 s | echt; zugeordnet: Scute-Swarm-Trigger-Explosion, regelkonform, bekannte Familie |
| 22 | pod-013 | XMAGE_ACTION_EXECUTION_FAILED (x+y) | failed, gleiche Familie | echt auf der alten Linie (Stand ohne #951 und vier Pilot-Fixes) |
| 23 | pod-015 | XMAGE_ACTION_EXECUTION_FAILED (x+y) | failed, gleiche Familie | echt auf der alten Linie (gleiche Einschränkung) |

Rohdaten: `sweep_p21g21_x/y.json`, `sweep_p22g22_x/y.json`, `sweep_p23g23_x/y.json`.

## Umstieg auf Pin v11 (Nachtrag 1)

Lab-Worktree auf `84e245ace2ed`, Pin `456b0e22…` in der Config verifiziert,
Mage-Install + Bridge neu gebaut (JAR oben), Kalibrierung wiederholt: 182/195,
31 fehlende Karten. Hinweis aus dem Bau: Die Modulpfade im v11-Baum tragen das
`Mage.`-Präfix (`Mage.Server.Plugins/Mage.Deck.Constructed` usw.).

### p6g6 auf v11 (workers 1, 1 Spiel/JVM)

46/46 ok, 0 failed. Gegen die Referenz der alten Linie: 43 Pods hashgleich,
3 abweichend:

| Pod | alte Linie | v11 | Entscheidungen | Einordnung |
|---|---|---|---|---|
| pod-022 | `a993ad769217` | `904820b4f5b0` | 3524 → 3524 | Erwartung aus Nachtrag 1 exakt getroffen (Tempt-Fix) |
| pod-044 | `88c142632960` | `88c142632960` | 3389 → 3389 | einer der zwei bekannten Hashes; weiter instabil, Fix nicht im Pin (erwartet) |
| pod-006 | `d704ac9fdd6a` | `218c154149f0` | 4376 → 4659 | auf v11 in sich stabil (Solo reproduziert Hash + Zahl exakt) → Stand-Unterschied, keine Instabilität |

Rohdaten: `sweep_p6g6_v11_muse.json`.

## Schritt B — v11 (Pin 456b0e22)

Läufe mit `--games-per-jvm 6 --fast`, je Seed zweimal (x/y).

| Seed | Lauf | Pods | ok | failed | Fehlerfamilien |
|---|---|---|---|---|---|
| 24 | x | 46 | 46 | 0 | — |
| 24 | y | 46 | 46 | 0 | — |
| 25 | x | 46 | 46 | 0 | — |
| 25 | y | 46 | 46 | 0 | — |
| 26 | x | 46 | 46 | 0 | — |
| 26 | y | 46 | 46 | 0 | — |
| 27 | x | 46 | 46 | 0 | — |
| 27 | y | 46 | 46 | 0 | — |
| 28 | x | 46 | 46 | 0 | — |
| 28 | y | 46 | 45 | 1 | BRIDGE_TIMEOUT ×1 |
| 29 | x | 46 | 45 | 1 | XMAGE_ACTION_EXECUTION_FAILED ×1 |
| 29 | y | 46 | 45 | 1 | XMAGE_ACTION_EXECUTION_FAILED ×1 |
| 30 | x | 46 | 44 | 2 | ENGINE_FAILURE ×1, XMAGE_ACTION_EXECUTION_FAILED ×1 |
| 30 | y | 46 | 43 | 3 | BRIDGE_TIMEOUT ×1, ENGINE_FAILURE ×1, XMAGE_ACTION_EXECUTION_FAILED ×1 |

Hash-Vergleiche x gegen y (nur beidseitig ok):

| Seed | beidseitig ok | hash-verschieden | instabile Pods (Hash x → y, Entscheidungen x → y) |
|---|---|---|---|
| 24 | 46 | 1 | pod-030: `205b305aeb5a` → `e0e1eeb73f71`, 4779 → 4815 |
| 25 | 46 | 0 | — |
| 26 | 46 | 0 | — |
| 27 | 46 | 1 | pod-028: `f923fc8b1b9e` → `adbd24b34af4`, 5409 → 4805 |
| 28 | 45 | 0 | — |
| 29 | 45 | 0 | — |
| 30 | 43 | 2 | pod-005: `1401a990c7a4` → `48abd23a173c`, 4967 → 3483; pod-036: `f8283d25d0da` → `df6a92270bb5`, 2112 → 2227 |

Failed Pods mit Diagnose-Prüfsumme (aus der Sweep-Fehlermeldung) und
Einzelnachlauf (1 Spiel, frische JVM, v11-JAR):

| Seed | Pod | Lauf | Familie | Diagnose-sha256 (Präfix) | Solo | Einordnung |
|---|---|---|---|---|---|---|
| 28 | pod-024 | y | BRIDGE_TIMEOUT | `a0885582f18f7386` | ok, 110 s, `9ede18fe356d` | Artefakt — Solo-Hash = Hash des x-Laufs |
| 29 | pod-000 | x | XMAGE_ACTION_EXECUTION_FAILED | `6895c96578121282` | failed, gleiche Familie (45 s) | echt |
| 29 | pod-000 | y | XMAGE_ACTION_EXECUTION_FAILED | `dd617290c2b804d5` | (siehe x) | echt; die Diagnose-Prüfsummen der beiden Läufe unterscheiden sich |
| 30 | pod-012 | y | BRIDGE_TIMEOUT | `920d903cae158dc3` | ok, 66 s, `8c5d99374e73` | Artefakt — Solo-Hash = Hash des x-Laufs |
| 30 | pod-026 | x | ENGINE_FAILURE | `683af50c65854769` | failed ENGINE_FAILURE (283 s) | echt |
| 30 | pod-026 | y | ENGINE_FAILURE | `d4865bccb6640631` | (siehe x) | echt |
| 30 | pod-045 | x | XMAGE_ACTION_EXECUTION_FAILED | `ce505f92008b9df4` | failed, gleiche Familie (46 s) | echt |
| 30 | pod-045 | y | XMAGE_ACTION_EXECUTION_FAILED | `e26e61457255be70` | (siehe x) | echt |

Anmerkung zu Seed 29 pod-000 und Seed 30 pod-026/pod-045: Die Fehler treten in
beiden Läufen und im Solo auf; `BLOCK_DECLARATION_REJECTED` (Seed 21 pod-010,
Fix #956) trat auf v11 in keinem Lauf auf.

Rohdaten: `sweep_p24g24_v11_x/y.json` … `sweep_p30g30_v11_x/y.json`.

## Schritt C — erste abweichende Entscheidung (nur v11-Instabile)

Methode: Einzel-Nachspiele mit Entscheidungs-Log (`replay/replay_log.py`),
Normalisierung (UUIDs, `object_id`, Kurz-IDs in Klammern), Vergleich der
Entscheidungsströme (cls/seat/src/opts/sel). Prompt-Texte enthalten gekürzte
IDs und wurden nur als Kontext, nicht als Vergleichsfeld genutzt (die
Prompt-Differenzen an ID-Stellen sind Normalisierungsrauschen, keine
Entscheidungsdifferenzen).

| Seed/Pod | Replays | verschiedene Hashes in Replays | erste abweichende Entscheidung |
|---|---|---|---|
| 24 / pod-030 | 6 | 4 (`e0e1eeb7` ×2, `82483304` ×2, `4eb6ff64`, `205b305a`) | **#2857**: `choose_use`, Sitz 3 (Lauf a) gegen Sitz 1 (Lauf f), Quelle **Wave of Vitriol**, Prompt „Search your library for up to 4 basic lands?", Optionen [Yes, No], Wahl in beiden [Yes] |
| 27 / pod-028 | 2 | 2 (beide neu: `fe59500c`, `84bbe903`) | **#2321**: `choose_use`, Sitz 3 gegen Sitz 1, Quelle **From the Ashes**, Prompt „Search your library for up to four basic land cards?", Wahl beide [Yes] |
| 30 / pod-005 | 2 | 2 (`1401a990` = Sweep-x, `3dcc2dd4` neu) | **#2349**: `choose_use`, Sitz 0 gegen Sitz 2, Quelle **Wave of Vitriol**, „Search your library for up to 4 basic lands?", Wahl beide [Yes] |
| 30 / pod-036 | 2 | 2 (`427cd41e` neu, `df6a9227` = Sweep-y) | **#1614**: `choose_use`, Sitz 1 gegen Sitz 0, Quelle **Wave of Vitriol**, „up to 3 basic lands?" gegen „up to 1 basic lands?" (die Zahl ist spielerindividuell; der Unterschied folgt aus dem Sitzwechsel), Wahl beide [Yes] |

In allen vier Fällen sind Optionen und Wahl an der Trennstelle gleich — was
wechselt, ist die **Reihenfolge, in der die Spieler gefragt werden**. Danach
laufen die Spiele auseinander (verschiedene Entscheidungszahlen).

Ursachen (CODE_DERIVED, Pin `456b0e22`):

- **Wave of Vitriol** — `Mage.Sets/src/mage/cards/w/WaveOfVitriol.java`:
  Zeile 80 `Map<Player, Integer> sacrificedLands = new HashMap<>();`,
  Iteration Zeile 98 `for (Map.Entry<Player, Integer> entry : sacrificedLands.entrySet())`
  mit `entry.getKey().chooseUse(...)` in der Schleife.
  `PlayerImpl.hashCode()` (`Mage/src/main/java/mage/players/PlayerImpl.java`,
  Zeilen 5739–5743) ist `Objects.hashCode(this.playerId)` — die Spieler-UUID
  wird pro Spiel neu zufällig vergeben, also wechselt die HashMap-Reihenfolge
  von Spiel zu Spiel.
- **From the Ashes** — `Mage.Sets/src/mage/cards/f/FromTheAshes.java`:
  Zeile 67 `Map<UUID, Integer> playerAmount = new HashMap<>();`, Iterationen
  Zeile 77 (Suchen) und Zeile 97 (Mischen) über `playerAmount.entrySet()`.
  UUID-Schlüssel sind pro Spiel zufällig.

Fix-Richtung (nur benannt, **nicht angewendet** — kein Fix im Repo laut
Auftrag): Spieler in Sitzreihenfolge abarbeiten (z. B. über
`game.getState().getPlayersInRange(...)`, das sitzgeordnet ist) oder die Map
als `LinkedHashMap` in Sitzreihenfolge befüllen — dasselbe Muster wie der
`LinkedHashSet`-Fix für Tempt with Reflections (pod-022).

Divergenz-Ausschnitte (normalisiert, ±3 Entscheidungen Kontext):
`replay/s24_p030_divergenz.json`, `replay/s27_p028_divergenz.json`,
`replay/s30_p005_divergenz.json`, `replay/s30_p036_divergenz.json`. Die
vollständigen Replay-Logs (je ~0,6–1,6 MB) überschreiten das Push-Limit von
128 KB pro Datei und liegen lokal beim Mess-Agenten; ihre Hashes und
Entscheidungszahlen stehen in der Tabelle oben.

## Schritt D — statischer Audit (erweitert, CODE_DERIVED)

Methode: Für die 5.944 distinkten Kartennamen der 182 importierbaren Decks
(`imports_v11.json`) die Kartendatei im Pin gesucht (5.899 zugeordnet, 45 nicht
zugeordnet — u. a. Rückseiten/DFC- und Sonderformen; kein Vollständigkeitsanspruch).
Geprüft: `HashMap`/`HashSet`-Deklarationen, deren Schlüssel-/Elementtyp keinen
stabilen Wert-Hash hat (UUID — Werte pro Spiel zufällig; Player — Hash aus der
zufälligen UUID; Card/Permanent/Token-Familien — kein eigenes `hashCode`,
Identitäts-Hash; Enums — Identitäts-Hash), **und** die in derselben Datei
iteriert werden (for-each, `entrySet`/`keySet`/`values`, `stream`, `forEach`).
Zusätzlich: `Collectors.toMap/toSet/toCollection`-Stellen und Deklarationen
außerhalb des Hauptmusters (Felder, `computeIfAbsent`, zurückgegebene Sets)
stichprobenartig nachgeprüft. Effekt-Klassen im Engine-Kern wurden nur geprüft,
wo eine Schritt-C-Karte sie benutzt — beide Schritt-C-Effekte sind innere
Klassen der Kartendateien und damit oben erfasst.

„Einfluss" heißt: Die Iterationsreihenfolge bestimmt, in welcher Reihenfolge
Spieler-Entscheidungen abgefragt oder Effekte angewendet werden. „Ja
(Entscheidungen)" ist nur für die zwei Schritt-C-Karten durch Laufzeit-Evidenz
belegt; „Ja (Effekte)" ist aus dem Code abgeleitet (sequentielle Anwendung),
ohne dass für diese Karten ein divergierender Lauf beobachtet wurde.

### Tabelle A — HashMap/HashSet in Kartendateien, iteriert, Risikotyp

| Karte | Datei:Zeile | Collection | iteriert | Einfluss | Begründung (1 Satz) |
|---|---|---|---|---|---|
| From the Ashes | f/FromTheAshes.java:67 | HashMap<UUID, Integer> | ja | **Ja (Entscheidungen + Effekte)** | Schritt C #2321: Spieler werden in HashMap-Reihenfolge zum Suchen gefragt. |
| Wave of Vitriol | w/WaveOfVitriol.java:80 | HashMap<Player, Integer> | ja | **Ja (Entscheidungen + Effekte)** | Schritt C #2857/#2349/#1614: gleiche Stelle, Player-Hash aus Zufalls-UUID. |
| Curse of Bounty | c/CurseOfBounty.java:77 | HashSet<UUID> | ja | Ja (Effekte) | Untap-Effekt wird pro Spieler in Set-Reihenfolge angewendet. |
| Curse of Disturbance | c/CurseOfDisturbance.java:78 | HashSet<UUID> | ja | Ja (Effekte) | Token-Effekt pro Spieler in Set-Reihenfolge (Muster wie Bounty, im Code verifiziert). |
| Curse of Opulence | c/CurseOfOpulence.java:82 | HashSet<UUID> | ja | Ja (Effekte) | Gold-Token-Effekt pro Spieler in Set-Reihenfolge. |
| Curse of Verbosity | c/CurseOfVerbosity.java:76 | HashSet<UUID> | ja | Ja (Effekte) | Zieh-Effekt pro Spieler in Set-Reihenfolge. |
| Curse of Vitality | c/CurseOfVitality.java:76 | HashSet<UUID> | ja | Ja (Effekte) | Lebensgewinn pro Spieler in Set-Reihenfolge. |
| Curse of the Swine | c/CurseOfTheSwine.java:70 | HashMap<UUID, Integer> | ja | Ja (Effekte) | Boar-Token werden pro Controller in entrySet-Reihenfolge erzeugt (pod-044-Klasse). |
| Fandaniel, Telophoroi Ascian | f/FandanielTelophoroiAscian.java:76 | HashSet<UUID> | ja | Ja (Effekte) | Lebensverlust wird pro Spieler in Set-Reihenfolge angewendet. |
| Highcliff Felidar | h/HighcliffFelidar.java:82 | HashSet<UUID> | ja | Ja (Effekte) | Zerstörung läuft sequentiell über das Set (`forEachOrdered` über HashSet-Strom). |
| Incendiary Command | i/IncendiaryCommand.java:81 | HashMap<UUID, Integer> | ja | Ja (Effekte) | Kartenziehen pro Spieler in entrySet-Reihenfolge. |
| Infernal Offering | i/InfernalOffering.java:75 | HashMap<UUID, UUID> | ja | Ja (Effekte) | Opfer werden in entrySet-Reihenfolge gebracht. |
| Legate Lanius, Caesar's Ace | l/LegateLaniusCaesarsAce.java:77 | HashSet<UUID> | ja | Ja (Effekte) | Opfer sequentiell in Set-Reihenfolge. |
| Master of Ceremonies | m/MasterOfCeremonies.java:74–76 | HashSet<UUID> ×3 | ja | Ja (Effekte) | Token-Erzeugung pro Wähler in Set-Reihenfolge (drei gleich gebaute Schleifen). |
| Order of Succession | o/OrderOfSuccession.java:72 | HashMap<UUID, UUID> | ja | Ja (Effekte) | Kontrollwechsel werden in entrySet-Reihenfolge angewendet. |
| Scythe Specter | s/ScytheSpecter.java:67 | HashMap<UUID, UUID> | ja | Ja (Effekte) | Abwerfen läuft sequentiell über keySet — der Code-Kommentar sagt „must happen simultaneously", die Umsetzung ist sequentiell. |
| Terastodon | t/Terastodon.java:70 | HashMap<UUID, Integer> | ja | Ja (Effekte) | Elephant-Token pro Controller in entrySet-Reihenfolge (pod-044-Klasse). |
| Unexplained Absence | u/UnexplainedAbsence.java:89 | HashSet<UUID> | ja | Ja (Effekte) | Manifest pro Controller in Set-Reihenfolge. |
| Reins of Power | r/ReinsOfPower.java:77–78 | HashSet<UUID> ×2 | ja | Unklar | GainControl-Effekte werden in Set-Reihenfolge registriert; Ziele sind disjunkt, Zustandsfolge statisch nicht entscheidbar. |
| Retether | r/Retether.java:75 | HashMap<Card, Permanent> | ja | Unklar | Auren werden per entrySet angelegt; ob die Reihenfolge zustandssichtbar ist, hängt von Zielüberlappung ab. |
| Soulflayer | s/Soulflayer.java:53 | HashSet<Ability> (Feld) | ja | Unklar | Fähigkeiten werden in Set-Reihenfolge auf das Permanent kopiert; Keyword-Mengen sind semantisch ungeordnet, die Serialisierung könnte die Reihenfolge zeigen. |
| Cliffside Rescuer | c/CliffsideRescuer.java:91 | HashSet<UUID> | ja | Nein | Nur `stream().noneMatch(...)` — Existenzprüfung, reihenfolgeunabhängig. |
| Fortunate Few | f/FortunateFew.java:61 | HashMap<Permanent, ?> | ja | Nein | keySet dient nur dem Aufbau einer Ausschluss-Filterliste. |
| Slaughter the Strong | s/SlaughterTheStrong.java:71 | HashSet<UUID> | ja | Nein | Iteration summiert nur Stärke und baut eine Prädikatliste. |
| Tymna the Weaver | t/TymnaTheWeaver.java:95 | HashSet<UUID> (Werte) | ja | Nein | Iteration zählt nur Gegner (`contains`), keine Anwendung. |

### Tabelle B — Collectors-/Sonderstellen (nachgeprüft)

| Karte | Datei:Zeile | Muster | Einfluss | Begründung |
|---|---|---|---|---|
| Dance of the Manse | d/DanceOfTheManse.java:97 | Collectors.toSet() → HashSet<Card>, danach addEffect-Schleife | Ja (Effekte) | Continuous Effects werden in Set-Reihenfolge (Identitäts-Hash der Karten) registriert. |
| Aetheric Amplifier; Bribe Taker; Exotic Pets; Sin, Unending Cataclysm; The First Tyrannic War; The Thing | diverse | Collectors.toSet() über CounterType (Enum), iteriert | Unklar | Enum-Mengen mit Identitäts-Hash; ob die Counter-Verarbeitungsreihenfolge zustandssichtbar wird, hängt vom jeweiligen Effekt ab. Kathril (unten) zeigt die behobene Form desselben Musters. |
| Mantle of the Ancients | m/MantleOfTheAncients.java:113 | Collectors.toSet() → HashSet<Card> | Unklar | Anhänge-Reihenfolge an dasselbe Permanent könnte sichtbar sein. |
| Trazyn the Infinite | t/TrazynTheInfinite.java:71 | Collectors.toSet() → HashSet<Ability> | Unklar | Wie Soulflayer: addAbility in Set-Reihenfolge. |
| Celestial Judgment | c/CelestialJudgment.java:73 | Collectors.toMap → HashMap<Integer, List<Permanent>>, iteriert mit Spielerwahl pro Gruppe | Nein | Integer-Schlüssel haben stabilen Wert-Hash; die Gruppenreihenfolge ist für gleiche Schlüsselmenge deterministisch. |
| Galactus, Devourer of Worlds | g/GalactusDevourerOfWorlds.java:109 | Collectors.toSet() → Set<Player> | Nein | Nur Maximum/Filter; die Rückgabe-Menge selbst trifft keine Reihenfolge (Verbraucher außerhalb der Karte). |
| Lethal Scheme | l/LethalScheme.java:73 | Collectors.toSet() + HashMap<Player, Set<Permanent>> | Nein | Dient nur dem Aufbau einer Lookup-Map; die Spieler-Schleife danach ist sitzgeordnet. |
| Mezzio Mugger | m/MezzioMugger.java:74 | Collectors.toSet() → HashSet<Card> | Nein | Sammel-Exil plus unabhängige Einzeloperationen (makeCardPlayable). |
| Pako, Arcane Retriever (Watcher) | p/PakoArcaneRetriever.java:120 | HashMap<UUID, Set<MageObjectReference>> (roh) | Nein | Nur `computeIfAbsent` + `anyMatch` — Mitgliedschaft/Existenz. |
| Leadership Vacuum | l/LeadershipVacuum.java:74 | new HashSet<>(Permanents) an moveCards | Nein | Sammel-Move in die Kommandozone, keine Auswahlreihenfolge. |
| Leonin Arbiter | l/LeoninArbiter.java:104 | HashSet<UUID> in State-Value | Nein | Nur `add`/Mitgliedschaft (Spieler, die bezahlt haben). |
| Trap the Trespassers | t/TrapTheTrespassers.java:95 | `return new HashSet<>()` (leer) + Vote per Targetwahl | Nein | Die leere Menge ist Platzhalter; die Wahl läuft über eine Target-Auswahl. |
| Lavabrink Floodgates | l/LavabrinkFloodgates.java:82 | HashSet als Choice-Set einer Auswahl | Unklar | Optionsmengen werden dem Spieler vorgelegt; ob ihre Reihenfolge die Pilot-Wahl (Gleichstand) beeinflusst, ist statisch nicht entscheidbar. |

### Positiv-Kontrollen (behobene Form desselben Musters, im Pin verifiziert)

| Karte | Datei:Zeile | Form |
|---|---|---|
| Tempt with Reflections | t/TemptWithReflections.java:70 | `LinkedHashSet`, mit Code-Kommentar: „HashSet would create the tokens in a different order every game" — der pod-022-Fix. |
| Kathril, Aspect Warper | k/KathrilAspectWarper.java:87 | `Collectors.toCollection(() -> EnumSet.noneOf(CounterType.class))`, Kommentar: „enum order, not identity-hash order: the prompts must come in the same order every run". |
| Luminous Broodmoth | l/LuminousBroodmoth.java:131 | `Collectors.toCollection(LinkedHashSet::new)` — Einfügereihenfolge stabil. |

Grenzen des Audits: Textmuster-Erkennung (Deklaration + Iteration in derselben
Datei). Nicht erfasst werden u. a. Collections, die in Helper-Methoden anderer
Dateien gebaut und zurückgegeben werden, sowie Iteration in anderen Dateien
als der Deklaration. 222 der zugeordneten Kartendateien enthalten überhaupt
`HashMap`/`HashSet`; 183 Deklarationen hat das Muster erfasst, die übrigen
Dateien wurden über die Collectors-/Lücken-Prüfung oben abgedeckt. Engine-Kern
außerhalb der Karten (z. B. die pod-044-Stellen `CreateTokenEvent`/
`TokenImpl.putOntoBattlefieldHelper` aus dem Nachtrag) war nicht Gegenstand
dieses Audits.

## Methoden- und Grenzanmerkungen

- Mehrere Läufe wurden durch Runtime-Neustarts der Mess-VM unterbrochen.
  Teil-Sweeps wurden mit derselben Sweep-Maschinerie nur um die fehlenden
  Pod-Indizes fortgesetzt (Plan je Datei gegen den Pod-Plan verifiziert);
  betroffene Dateien sind an ihrem Inhalt nicht von einem Stück zu
  unterscheiden, die Fortsetzung ändert weder JAR noch Seeds noch Batch-Größe.
- Solo-Nachläufe liefen mit einem Spiel pro JVM über denselben produktiven
  Spielpfad (`benchmark_xmage_full_games`-Maschinerie) wie die Sweeps.
- Die Runtime der Mess-VM ist selbst eine Fehlerquelle (kills ohne
  Fehlermeldung); alle Zahlen oben stammen aus den auf Disk verifizierten
  Sweep-Dateien, nicht aus Prozess-Ausgaben.

## Dateien in diesem Ordner

- `BERICHT.md` — dieser Endbericht
- `imports.json`, `imports_v11.json` — Kalibrierungen beider Linien
- `jar_sha256.txt` — beide eigenen JARs
- `versions.txt` — Umgebung
- `sweep_p6g6_muse.json` (Schritt A), `sweep_p6g6_v11_muse.json` (v11-Vergleich)
- `sweep_p21g21_x/y.json` … `sweep_p23g23_x/y.json` — alte Linie
- `sweep_p24g24_v11_x/y.json` … `sweep_p30g30_v11_x/y.json` — v11-Zensus
- `replay/replay_log.py` + `replay/*_divergenz.json` — Schritt-C-Werkzeug und
  Divergenz-Ausschnitte (vollständige Logs lokal, >128 KB je Datei)
- `audit_stepD.json` — Rohdaten des statischen Audits (alle erfassten
  Deklarationen)

Status: Endbericht. `git status` im Mess-Worktree ist sauber (keine
Repo-Änderungen; alle Werkzeuge und Rohdaten liegen außerhalb des Lab-Repos).
