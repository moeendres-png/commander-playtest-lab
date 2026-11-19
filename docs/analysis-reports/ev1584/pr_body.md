Refs #1584

- **Head zum Zeitpunkt des Reviews:** `b173de7d24a82f5d1cecceb3ead87ed9504a106b`
- **Pflicht-Checks auf diesem Head:** `quality` · `security` · `infrastructure`: laufen (Co-Lead wartet auf CI)
- **MATERIAL:** ja (Engine-Bridge, Studio-Bridge-Gate `BEHAVIOUR`: bisher gescheiterte Partien bekommen ein Ergebnis, eine beendete Partie ändert sich). Review durch einen anderen Agenten auf exakter Head-SHA steht aus.
- **Offen (UNKNOWN / NOT_RUN):** siehe Abschnitt „UNKNOWN / NOT_RUN“ unten.

## Ursache
XMage ruft `selectBlockers(source, game, defendingPlayerId)` bei dem Spieler auf, der bestimmt, wie geblockt wird. Das ist normalerweise der Verteidiger. Bei einem Block-Bestimmer, der nicht der Verteidiger ist (`ChooseBlockersEffect`: Brutal Hordechief, Master Warcraft, Odric, Master Tactician, Berserkers' Frenzy, Melee; dazu Invasion Plans), ruft XMage den Bestimmer einmal je Verteidiger auf (APNAP), jeweils mit der ID dieses Verteidigers (`Combat.selectBlockers(Player blockController, …)`, Pin `f4d12f6e8`).

`XmageFullGamePlayer.selectBlockers` nahm `getAvailableBlockers(game)`, also die eigenen Kreaturen des gefragten Spielers. Die Kreaturen des Bestimmers können hier nie blocken (`CombatGroup.canBlock` verlangt, dass der Verteidiger sie kontrolliert). Deshalb gab es keine Option und kein Frame. Das Engine-Verhalten war je nach Lage verschieden:
- Bei unerfüllter Pflicht „blockt, falls möglich“ fragte XMage ohne Ende neu: `checkBlockRequirementsAfter` liefert false, und die Grenze `aiTries > 20` gilt nur für Computer-Spieler. Das ergab eine CPU-Schleife bis `SETTLE_TIMEOUT` und dann `ENGINE_FAILURE`; das waren die Seeds 1024, 1029 (Variante) und 1033.
- Ohne erzwingbare Pflicht wurden die Blocks des Verteidigers still übersprungen (§2 „silent skip“). Das betrifft auch beendete Partien: Seed 3, siehe unten.

## Änderung
- `selectBlockers` nimmt jetzt die Blocker aus `game.getBattlefield().getAllActivePermanents(new FilterCreatureForCombatBlock(), defendingPlayerId, game)`. Das ist dieselbe Menge wie `getAvailableBlockers(game)`, wenn der Verteidiger der gefragte Spieler ist (`PlayerImpl.getAvailableBlockers` am Pin), und derselbe Filter wie die Referenz `HumanPlayer.selectBlockers` (`ControllerIdPredicate(defendingPlayerId)`, Reichweite ALL im Commander). Die F-42-Kommentare nennen jetzt den gefragten Spieler statt „Verteidiger“.
- Weitere Stellen mit demselben Fehler: keine.
  - `getAvailableBlockers` hat im Bridge-Code keinen weiteren Aufrufer.
  - `XmageBridgePlayer.selectBlockers` schlägt geschlossen fehl.
  - `selectAttackers` wird nur beim angreifenden Spieler selbst aufgerufen (`Combat.selectAttackers`, Z. 265–271).
  - `declareBlocker(defendingPlayerId, …)` prüft über `group.canBlock` wie die Referenz.
- Frames: Entscheider ist der Block-Bestimmer (`actor_id`, Studio-Log `seat`). Die Optionen nennen `blocker_id` und `attacker_id`. Der Blocker steht im öffentlichen Spielfeld des Verteidigers in `pilot_state`, unter dessen sitzbasierter Kennung (`op-N`, `ActorSafeIdentity`). Damit ist der Verteidiger erkennbar. Es gibt kein neues Feld und keine Änderung am Frame-Vertrag. Gezeigt werden nur öffentliche Objekte (Kreaturen auf dem Spielfeld, Angreifer), keine Hand und keine Bibliothek.

## Tests
- **`XmageBlockControllerTest`** (neu, echte Engine, Invasion Plans, drei Sitze, P1 greift P2 und P3 mit je einer Raging Goblin an):
  - `blockControllerDeclaresEachDefendersBlockers`:
    - Frame 1 hat Entscheider P1 und als Blocker die Grizzly Bears von P2. Einzige Option ist der Goblin, der P2 angreift.
    - Frame 2 betrifft den Hill Giant von P3. Die leere Antwort lässt „blockt, falls möglich“ unerfüllt, die Engine fragt dasselbe Frame neu, dann wird geblockt.
    - Beide Blocks stehen in `game.getCombat()`.
  - `blockControllerFramesCarryNoOpponentHiddenCards` (§5):
    - Strukturprüfung: Gegner-Einträge haben weder `hand` noch `mana_pool`.
    - UUID-Orakel: Keine Hand- oder Bibliotheks-ID eines Gegners kommt im Frame oder in den Legal Actions vor. Die Gegner haben Karten auf der Hand, das Orakel ist also nicht leer.
    - Kein Kartenname aus einer Gegnerhand kommt vor.
    - Mutation: Dasselbe Block-Frame mit der Handkarte von P2 (als ID und als Name) macht das Orakel rot.
  - **Auf der BEFORE-Bridge scheitern beide Tests**: `DECISION_ADVANCE_TIMEOUT … 75s`, der Engine-Thread steht in der Blockschleife. Auf AFTER sind beide grün.
  - Das Orakel ist eine eigene Kopie: `XmageFullGameHiddenInformationTest.java` ist eine gepinnte Meta-Verification-Eingabe und bleibt unverändert.
- **Pilot, Zwei-Verteidiger-Randfall** (UNKNOWN aus der Diagnose; der Zähler gilt je Sitz und Zug): `test_block_controller_frames_for_two_defenders_each_start_at_the_judgment` in `tests/unit/test_full_game_pilot_judgment.py`. Das Frame des zweiten Verteidigers ist eine erste Frage (Urteil) und keine Nachfrage zum ersten, weil der Schlüssel Blocker- und Angreifer-ID enthält. Eine echte Nachfrage eskaliert weiter. Auf Bridge-Ebene deckt der Java-Test zwei Verteidiger mit einem Entscheider ab.

## Studio-Bridge-Gate: `BEHAVIOUR`
BEFORE ist `engine-bridge/` am Merge-Base `f028676976a46eb0a5ead84f282703b7b4e851bd`, AFTER der exakte PR-Head `b173de7d24a82f5d1cecceb3ead87ed9504a106b`. Gleicher Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d`.

| | SHA-256 des Jars |
|---|---|
| BEFORE | `7a946869cc2e4c3267d6bc22c3c5a69b7242bd8f504db572666daea9facfde41` |
| AFTER | `70d5ba8f90daa521cc79d971f9ad8da81ae95ed4679b9b7dfd86d5984d7ce4de` |

Bau der Jars, wichtig für die Einordnung: Beide Jars sind **nicht** mit `mvn package` gebaut. Lokal fehlen die `org.mage`-Artefakte, und XMage wurde nicht lokal gebaut. Gebaut wurde so:
- Aus dem Studio-Fat-Jar `204dd9ad…` (gepinnte XMage-Klassen) wurden alle `org/commanderlab/**` entfernt.
- Der gesamte Bridge-Quellcode des jeweiligen Stands wurde mit `javac --release 17` übersetzt und eingesetzt. Beide Jars entstehen nach demselben Rezept.
- Ergebnis: gleiche Eintragsliste, nur die Klassen `XmageFullGamePlayer*` unterscheiden sich.

Maßgeblich bleibt der Maven-Bau der CI.

Referenzsatz (echter Vier-Spieler-Pod, Seeds 1–36, `--workers 4 --games-per-jvm 9 --fast`). Kein Deck des Pods enthält eine Block-Bestimmer-Karte, deshalb war Identität vorhergesagt.
```
compare ref_before.json ref_after.json --expect-games 36 --require-different-jars
identical 36/36
frames identical 36/36          (Exit 0)

AFTER --games-per-jvm 1, Seeds 1-6, gegen BEFORE:
identical 6/6
frames identical 6/6
```
Dieser PR ändert weder `scripts/benchmark_xmage_full_games.py` noch den Transkript-Hash-Code.

**Tisch aus #1584** (`precon/2016/open_hostility` auf Sitz 0 gegen `precon/2026/lorehold_spirit`, `precon/2024/animated_army`, `precon/2022/token_triumph`; `python -m commander_lab.studio play`; Seeds 1–8 und 1000–1039 sowie Seed 1029 mit dem Variantendeck `open_hostility-v3`; je eine Partie pro Arm, seriell):

| Seed | BEFORE | AFTER |
|---|---|---|
| 1024 | `failed`, 1402 Frames, Zug 25 | `finished`, 2571 Frames, Sieger Sitz 0 |
| 1033 | `failed`, 1949 Frames, Zug 31 | `finished`, 2369 Frames, Sieger Sitz 1 |
| 1029 (Variante) | `failed`, 2855 Frames, Zug 41 | `finished`, 3404 Frames, Sieger Sitz 2 |
| 3 | `finished`, 2984 Frames, Sieger Sitz 0 | `finished`, 3000 Frames, Sieger Sitz 0 (erklärt) |
| 45 übrige | `finished` | identisch |

Identität gemessen am `semantic_transcript_sha256` des Studio-Logs und an einer normalisierten Frame-Folge (Kurz-IDs und UUIDs ersetzt). Das ist nicht der Frame-Digest des Benchmarks: Das Werkzeug kennt keine eigenen Decks. Ergebnis: 45/46 zuvor beendete Partien sind identisch, die eine Abweichung ist Seed 3. In AFTER ist keine Partie gescheitert (49/49 beendet).

Neue Block-Bestimmer-Frames in AFTER (Sitz 0 bestimmt die Blocks der Gegner, Brutal Hordechief):
- 1033: 11 Frames, Urteil „kein Block“. Die Engine verwirft das (alle müssen blocken, falls möglich). Die zweite Frage ergibt die maximale Erklärung, alle 11 blocken den Wight, und die Engine akzeptiert.
- 1024: Zug 25 mit 2 Frames (eine Nachfrage), Zug 28 mit 4 Frames.
- 1029 (Variante): 5 Frames, 3 Blocks.

**Seed 3 erklärt:**
- Die Folgen sind bis Frame 2982 gleich.
- Zug 40: Sitz 0 hat Brutal Hordechief aktiviert und greift Sitz 1 („Full Game Seat 2“, 9 Leben) mit Iroas, God of Victory, Stalking Vengeance und Sun Titan an. Iroas gibt den Angreifern Menace.
- BEFORE: kein einziges Block-Frame. Die 16 Kreaturen von Sitz 1 wurden still übergangen.
- AFTER: 16 Frames (n 2983–2998), eines je Kreatur von Sitz 1, Entscheider Sitz 0, je 3 Optionen. Der Pilot antwortet überall „kein Block“, denn ein einzelner Blocker kann einen Menace-Angreifer nicht blocken (`block_score` gibt −1). Die Engine akzeptiert die leere Erklärung ohne Nachfrage.
- Danach sind die restlichen 2 Frames identisch (normalisiert), Lebenspunkte am Ende gleich (28/9/0/−2), Sieger Sitz 0.
- Der Unterschied besteht genau aus den 16 Entscheidungen, die BEFORE nie gestellt hat. Jetzt ist es richtig: Die Blocks des Verteidigers werden erklärt, statt still zu entfallen.

**Bridge-Testsuiten und Smoke:** Bridge-Suite über die JUnit-Konsole (lokal, nicht Maven; Klassen des javac-Baus; Arbeitsverzeichnis `engine-bridge/target`, `-Dcommanderlab.repoRoot`):
- AFTER: 1211 Tests gefunden, 1204 grün, 1 übersprungen, 6 rot. Die 6 roten sind alle Folgen des Aufbaus:
  - 5 Replay-Tests (`XmageFullGameReplayExportTest`, `XmageFullGameForcedDecisionSkipTest`) starten eine JVM mit `java.class.path`. Neu gestartet mit echtem Klassenpfad: 13/13 grün.
  - `BridgeClasspathTest.noAiPlayerDependencyInPom` sucht `pom.xml` neben `test-classes`; die `pom.xml` ist unverändert.
- BEFORE mit denselben Testquellen: 1202 grün, 8 rot. Das sind dieselben 6 plus die 2 neuen `XmageBlockControllerTest`; sonst ist der Fehlersatz identisch.
- Reale Vier-Spieler-Smoke (`scripts/run_real_4p_full_game_smoke.py --progress-turns 4 --smoke-decisions 3000`, AFTER-Jar): Exit 0, `PASS`, Zwillingsläufe mit gleichem Fortschritts-Digest. Dazu kommen die 36 echten Vier-Spieler-Partien des Referenzsatzes, alle beendet.
- Python: `pytest -k "studio or hygiene or runtime_asserts or any_usage or shards"` ergibt 1733 grün, 2 übersprungen, 1 rot (`test_bridge_qualification_states`). Der rote Test scheitert am Merge-Base genauso, weil der flache Clone die Git-Historie zur Siegel-Epoche nicht hat. Pilot-Tests 65/65 grün, `ruff check` und `ruff format --check` grün.

**PB-03:** läuft in der CI. Ein Ergebnis, das nur am fehlenden neuen Siegel scheitert, ist `NOT_SEALED`, nie PASS. Ein echter Fehler blockiert.

**Bridge und Siegel:** Wie nach #1316 weicht die laufende Bridge danach erneut vom versiegelten Stand ab. Spiel-Logs und Serien tragen die neue `bridge_jar_sha256`, der Studio-Ausweis zeigt `BRIDGE_AHEAD_OF_QUALIFICATION`. Nichts auf dieser Bridge ist durch die versiegelte Epoche gedeckt. Fork, Pin, Siegel, `qualification/` und WS17 sind unverändert.

**Last:** 4-Kern-VM. Die Engine-Läufe liefen seriell, ohne parallele Suiten.
- Referenzarme je etwa 8–10 min (Load 2,5–6,8; BEFORE begann direkt nach einem abgebrochenen Lauf bei Load 10,1).
- Tisch-Partien: AFTER etwa 22–36 s, BEFORE-Hänger 54–110 s, Load 1,4–4,8.

## UNKNOWN / NOT_RUN
- Lokales `mvn verify`: `NOT_RUN`, weil XMage-Artefakte fehlen. Die Suite lief stattdessen über die JUnit-Konsole gegen die javac-Klassen (siehe oben). Maßgeblich ist `mvn verify` in der CI (XMage Full Game Conformance).
- `test_bridge_qualification_states` lokal rot, auch am Merge-Base (flacher Clone); der Lauf in der CI ist maßgeblich.
- Ein Block-Bestimmer, der während seines Block-Frames das Spiel verlässt (Aufgeben des Mensch-Sitzes): ungetestet. Die Engine-Schleife bleibt für diesen Fall unverändert, wie vor dem PR.
- Tische mit Odric, Master Warcraft, Melee, Berserkers' Frenzy: nur über den gemeinsamen Pfad abgedeckt (Invasion Plans im Test, Hordechief am Tisch).
- Pilot-Qualität: Der Pilot bewertet fremde Blocks aus eigener Sicht (eigene Lebenspunkte in Dringlichkeit und Chump-Regel). Das ist legal, aber nicht zielgerichtet; eigenes Folge-Issue, nicht Teil dieses PR.
- XMage akzeptiert bei Menace-Angreifern die leere Erklärung trotz „blockt, falls möglich“ (Seed 3). Das ist Fork-Verhalten (Regelautorität) und wurde nicht geändert. Ob es CR 509.1c in jedem Fall trifft, ist unbekannt.
- Lane `midgame_rows` der Qualifikation: Sie lehnt Block-Frames eines Nicht-Verteidigers geschlossen ab. Keine versiegelte Zeile nutzt eine solche Karte, daher keine Wirkung.
- Owner-PC ungemessen.

## Nebenbefund (nicht in diesem PR)
Seed 1007, Frame 602 schreibt eine native UUID in `chosen` des Studio-Logs. Vorschlag: eigenes Issue.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_011vaKpe3NEKpcUvzSn39pe1
