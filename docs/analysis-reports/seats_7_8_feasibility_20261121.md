# 7 und 8 Spieler im Commander Studio: Machbarkeit und Sinn (Refs #1672)

**Empfehlung:** Zuerst 5 und 6 Sitze vollständig absichern (Option A: #1715, F5, Replay-Tape mindestens für 5 Sitze, F1); 7/8 **später, nicht jetzt**. Ins Produkt kommen 7/8 nur mit einem eigenen Owner-Entscheid, der das 6er-Maximum vom 2026-11-08 ausdrücklich aufhebt. Technisch geht das ohne Fork-Änderung, aber jede Antwort kostet etwa 4- bis 9-mal so viel wie am Vierertisch, und es gibt keine Referenz für Sitzbalance und Pilotgültigkeit.

- **Stand:** `origin/main` @ `2a481efbe`, Pin `f4d12f6e80` (`config/rules_engines.json:41`). Nur gelesen, keine Läufe. Alle Datei:Zeile-Angaben beziehen sich auf diesen Stand; die Zeilen `full_game.py:278/324/1172` aus #1672 und aus `charter_simulate.md` (nicht auf `main`, Commit `278c4977b`; zitiert wie in #1672) §4.1 sind veraltet.
- **Klassen:** Code-Befunde `CODE_DERIVED`. Messwerte `SIMULATED_RESULT` aus `docs/analysis-reports/seats_5_6_part_b_report.md` (Owner-PC, WSL2, 313/313 Partien, kein Qualifikationsbeleg). Hochrechnungen `MODELED` (Schätzung), 7/8-Laufzeitverhalten `UNKNOWN`.
- **Zwei Prämissen des Auftrags korrigiert:** (1) Die Faktoren 1,56× und 2,22× gelten für 4→5→6 Sitze, nicht für 2→3→4. Herkunft: Wandzeit-Median, Tisch A, Seeds 1–10, n = 10 je Sitzzahl, eine JVM je Partie (Teil B §5). (2) Es gibt keine „XMage-AI“ im Spiel: `AGENTS.md` §2 verbietet engine-interne KI, die Sitze spielen Lab-Piloten (`full_game_pilot`). Die Frage nach der KI-Qualität betrifft also diese Piloten.

## 0. Governance: das eigentliche Tor

- `docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md`: höchstens 6 Sitze; der Entscheid untersagt, einen operativen 7+-Betrieb zu planen, zu bauen oder zu benchmarken. Nur eine neue direkte Owner-Anweisung hebt ihn auf. Erlaubt ist nach dem Owner-Update vom 2026-11-08 allein **isolierte Forschung bis 8 Sitze auf ausdrücklichen Auftrag**: eigener Harness, kein Zulassungs-Endpunkt, kein Standard, kein UI-Versprechen, kein Ergebnis als 4P- oder 6P-Beleg.
- `AGENTS.md:16-17` und `docs/STUDIO_SCOPE.md:36` sagen beide: „Höchstzahl 6“. E10 erlaubt, alte Entscheide zu überarbeiten, die Sitz-Vorbehalte nach `AGENTS.md` §8 bleiben aber bestehen.
- E15 Q5 (`OWNER_DECISIONS_STUDIO_20261118.md:404`): „7/8 zurückgestellt bis zur 6er-Messung“. Die 6er-Messung liegt jetzt vor (Teil B). Damit ist die Bedingung für dieses Papier erfüllt, eine Freigabe folgt daraus nicht.
- **Einordnung (Vorschlag, keine Feststellung):** Der Owner-Wunsch vom 2026-11-20 („Simulate bitte bis 8 wenns geht (oder halt auch bis 6)“, #1672) ist nach dieser Lesart noch kein Forschungsauftrag und keine Aufhebung. Das entscheiden Co-Lead bzw. Owner, siehe Frage (a) in §5.

## 1. Harte Grenzen und Konvention

| Ebene | Grenze | Art | Beleg |
|---|---|---|---|
| XMage-Spiel (Pin) | keine Obergrenze: `CommanderFreeForAll.setNumPlayers` prüft nichts | keine | Fork `Mage.Server.Plugins/Mage.Game.CommanderFreeForAll/src/mage/game/CommanderFreeForAll.java:44-45` |
| XMage-Match-Typ | `maxPlayers = 10`, `minPlayers = 3`; gilt nur auf dem Server-/Match-Weg, den die Bridge nicht nutzt | Server-Konvention | `CommanderFreeForAllType.java:16-17`; die Bridge baut das Spiel direkt: `XmageCommanderGames.java:35-57` |
| Bridge (Java) | `MAX_PLAYERS = 6`; meldet `max_players` als Fähigkeit | **hart** (wirft eine Ausnahme) | `XmageFullGameSession.java:43, 125-129`; `XmageFullGameJsonlBridge.java:192, 571, 633, 655` |
| Python-Runner, Schemas | 2..6; der Runner verlangt `lane_max == MAX_PLAYERS` | **hart** (Validierung) | `full_game.py:306, 352, 1229, 1813, 1887`; `full_game_batch.py:62`; `full_game_comparison.py:87`; `full_game_pilot/state.py:77`, `common.py:816`; `candidates/models.py:224-225` |
| Studio | Engine 2..6 (`MIN_SEATS, MAX_SEATS`), freigegeben 4 | hart (6), Sperre (4) | `studio/launch.py:32, 39, 781-787` |
| Replay-Tape | 2..5 | hart | `semantic_replay/tape.py:49, 58, 98` |

**Ergebnis:** Die Obergrenze 6 ist eine Festlegung des Lab in Bridge und Python, keine Grenze von XMage. Ein Fork-Push ist **nicht** nötig. Wie sich die Engine bei 7 oder 8 Spielern zur Laufzeit verhält, hat im Lab nie jemand geprüft: `UNKNOWN` (`charter_simulate.md` (nicht auf `main`, Commit `278c4977b`; zitiert wie in #1672) §4.1: „kein einziger Lauf“).

## 2. Skalierung: Hochrechnung auf 7/8 (`MODELED`, Schätzung)

Grundlage sind drei Messpunkte von **einem** Tisch (A4/A5/A6, Seeds 1–10, n = 10 je Sitzzahl; Teil B §5). Die Spanne reicht von einer linearen Fortschreibung bis zu einem Potenzgesetz durch 4 und 6 Sitze. Drei Punkte schließen eine steilere Kurve nicht aus.

| Größe (Median) | 4 gem. | 5 gem. | 6 gem. | 7 geschätzt | 8 geschätzt |
|---|---|---|---|---|---|
| Wandzeit je Partie [s] | 12,91 | 20,18 | 28,73 | 37–39 (2,8–3,0×) | 45–51 (3,4–3,9×) |
| CPU je Partie [s] | 30,83 | 42,76 | 54,56 | 66–68 (2,2×) | 78–82 (2,5–2,7×) |
| Entscheidungen | 2.704 | 4.534 | 6.329 | 8.100–8.700 | 10.000–11.600 |
| RSS einer Einzel-JVM [MiB] | 749 | 777 | 969 | nicht belastbar (`UNKNOWN`) | nicht belastbar (`UNKNOWN`) |
| Pool-Durchsatz, 3 Worker [Partien/h] | nicht im selben Aufbau gemessen | 607,3 (n = 50) | 379,2 (n = 72) | 280–310 | 215–265 |

- **Tisch-Effekt ist so groß wie ein Sitz:** B6 hat einen Wandzeit-Median von 21,75 s, A6 von 28,16 s (je n = 12). Die Deckwahl verschiebt das Ergebnis also etwa um 25 %. Sitz- und Deck-Effekt sind in diesen Daten vermengt.
- **Speicher ist nicht der Engpass:** Die Pool-JVM lag bei 5 Sitzen bei höchstens 1.420 MiB, bei 6 Sitzen bei 1.448 MiB (Teil B §5); die Heap-Grenze ist fest `-Xmx3g` (`launch.py:156`). Für 7/8 erwartet: etwa 1,5–2 GiB je JVM, `UNKNOWN`, bis es gemessen ist.
- **Zeitgrenzen:** Das Maximum lag bei 9.451 Entscheidungen (B6). Für 8 Sitze ergibt die Hochrechnung etwa 15.000–17.300 (B6-Maximum × Median-Faktor 6→8 aus Tisch A, also tischübergreifend), unter der Grenze von 50.000 (`full_game.py:1245`). `GAME_WALL_LIMIT_SECONDS` kennt nur 2–4 Sitze (`table_spec.py:35`); bei 5–8 Sitzen bricht es fail-closed mit einem Fehler ab.
- **Serienkosten:** Ein voller Rotationsblock hat N² Paare, also 2·N² Partien: 32 / 50 / 72 / **98** / **128** bei 4 bis 8 Sitzen. Der 6er-Block dauerte gemessen 683,6 s (B6). Geschätzt: 7 Sitze 19–21 min, 8 Sitze 29–36 min je Block und Variante. Der Planungs-Design-Effekt `1 + (m−1)·0,25` (`paired_series.py:94`, Annahme, nicht gemessen) steigt von 1,75 (4 Sitze) auf 2,75 (8 Sitze).
- **Holm und Kohorten:** Jede Sitzzahl ist eine eigene Kohorte. `card_outcomes` schichtet seit #1683 nach Tischgröße (`card_outcomes.py:21-22`), und nach dem Entscheid vom 2026-11-08 zählt nichts als 4P- oder 6P-Beleg. Also braucht jede Sitzzahl eigene Erkundungs- und Bestätigungs-Seeds und eine eigene Holm-Familie; nichts lässt sich mit 4-Sitz-Daten poolen.

## 3. Spielsinn und Aussagekraft

**Stichprobe (Wilson 95 %, z = 1,96, exakt gerechnet; Halbbreite am Punkt p = Basis):** Basis 1/N bei gleichstarken Decks.

| Sitze | Basis | ±5 Pp absolut | ±3 Pp | ±20 % relativ (±0,2·p) | ±10 % relativ | Paar-SD unabhängig √(2p(1−p)) |
|---|---|---|---|---|---|---|
| 4 | 25 % | 286 | 798 | 286 (±5 Pp) | 1.150 | 0,612 |
| 6 | 16,7 % | 213 | 593 | 480 | 1.920 | 0,527 |
| 7 | 14,3 % | 189 | 523 | 577 | 2.306 | 0,495 |
| 8 | 12,5 % | 170 | 468 | 674 (±2,5 Pp) | 2.691 | 0,468 |

- **So zu lesen:** Für dieselbe *absolute* Breite braucht ein 8er-Tisch weniger Partien. Ein Unterschied von 5 Pp ist bei 12,5 % Basis aber ein viel größerer Effekt als bei 25 %. Für dieselbe *relative* Genauigkeit braucht er 2,36-mal so viele Partien (674 statt 286). Die Paar-SD-Werte 0,612 / 0,566 / 0,527 stimmen mit dem Docstring in `paired_series.py:118-126` und mit Teil A B-3 überein; die Planung rechnet sitzzahl-blind mit 0,63 (`full_game_comparison.py:70`), also vorsichtig.
- **Kosten je Antwort** (relative Genauigkeit × Zeit je Partie, `MODELED`): 7 Sitze **4,4–6,1×**, 8 Sitze **5,9–9,2×** gegenüber dem Vierertisch (untere Grenze aus der CPU-Zeit, obere aus der Wandzeit). Das Charta-Modell nannte 9–16× (`charter_simulate.md` (nicht auf `main`, Commit `278c4977b`; zitiert wie in #1672) §4.2, [S]). Es ruhte auf älteren 6er-Punkten (1,7–3,2×, je n = 1); nach Teil B (6 Sitze: 2,22× Wandzeit, 1,77× CPU) liegt die Spanne niedriger. Bei Q4 („eine Nacht je Frage“, 5.400 Partien) hieße das am 8er-Tisch etwa 6–9 Nächte je Frage.
- **Nutzen:** Jede heute festgelegte Owner-Frage ist eine Vierer-Frage: die erste Chulane-Frage (Landzahl-Achse, G-SIM Punkt 5, E7/C2) und die PLAY-Abnahme AK-1 (drei Vierer-Partien, E4). Keine davon braucht 7/8.
- **Pilotgültigkeit:** Die Lab-Piloten verhandeln nicht. Politik reduziert sich auf eine Bedrohungs-Heuristik (zum Beispiel `political_visibility`, `models/pilots.py:63`). Kingmaking und Zielwahl zwischen 7 Gegnern sind ungeprüft. Belegtes Muster bei 4 Sitzen: Der spätere Sieger wird am wenigsten angegriffen, 33/36 Vierer-Pod-Partien, Ursache oder Folge `UNKNOWN` (`docs/research/PILOT_STRENGTH_OPTIONS.md:71`). Hinweis, ausdrücklich ohne Vergleich (unterschiedliche Kohorten): Der Anteil „Do not attack“ lag bei 177/1.019 Frames (4 Sitze, nur Tisch A) gegenüber 920/2.738 (5 Sitze) und 977/3.026 (6 Sitze, beide A+B gepoolt) (Teil B §6).
- **Sitzbalance (G-SIM Punkt 3) ist bei 7/8 nicht prüfbar:** Die einzige menschliche Referenz betrifft Vierer-Partien (29,1 / 25,7 / 23,6 / 21,5 %, n = 300.240); für 5 bis 8 Sitze fehlt sie. Der Startsitz ist `seed % N`.
- **Determinismus-Risiko #1715 wächst mit der Sitzzahl:** `trigger_order`-Frames je Partie stiegen von etwa 19,9 (5 Sitze, 478/24) auf etwa 42,6 (6 Sitze, 1.023/24; A+B gepoolt). Der Gleichstand in `XmageFullGamePlayer.java:2648-2656` (Etikett, dann Zonenwechsel-Zähler) hat schon bei 6 Sitzen eine echte Zustandsabweichung erzeugt (1/20, Teil B §4.2).
- **Verdeckte Information:** Das Frame-Audit läuft bei jeder Entscheidung (`audit_actor_scoped_frame`, `full_game.py:178, 227`, sitzzahl-unabhängiger Code). Die F4-Tests decken nur die Sitze bis 6 ab. Für 7/8 also `CODE_DERIVED`, als Lauf `UNKNOWN`.
- **Spieldauer und PLAY:** Etwa 3,7–4,3-mal so viele Entscheidungen; zwischen zwei eigenen Zügen spielen 7 KI-Sitze. Das Brett hat Sitzfarben nur für `.s0`–`.s5` (`partie.css:64-65`). Wie oft am realen Tisch 7+ gespielt wird und wie groß der Tisch des Owners ist: unbekannt, im Repo gibt es dazu kein n/N; die Aussage „selten“ in #1672 ist unbelegt.

## 4. Änderungsstellen für ein 7/8-Produkt (`origin/main` @ `2a481efbe`)

- **Bridge (Studio-Bridge-Gate):** `XmageFullGameSession.java:43` (die Konstante prüfen auch `XmageFullGameJsonlBridge.java:192` und `XmageNativeStateRestoration.java:1159`). Tests, die die 6 festhalten: `XmageFullGameBridgeContractTest.java:23, 38, 51`, `JsonlBridgeTest.java:117`, `XmageFullGameContractTruthTest.java:31` (folgt der Konstante). Gate-Art: Auf dem Vierer-Referenzsatz `NEUTRAL`, dazu ein eigener Test für 7/8, der auf der BEFORE-Bridge fällt (`AGENTS.md` §10). Was ungetestet bleibt, ist `UNKNOWN`.
- **Engine-Python:** `full_game.py:306, 352, 1229, 1813, 1887`; `full_game_batch.py:62`; `full_game_comparison.py:87`; `full_game_pilot/state.py:77`; `full_game_pilot/common.py:816`; `candidates/models.py:224-225`. Nicht anfassen: `qualification/current_boundary/game_driver.py:883` (eingefrorene Qualifikation).
- **Studio:** `launch.py:32, 39, 386, 781-787, 804`; Gegner je Preset nur bis 6 Sitze: `POD_PRESETS` (`launch.py:51`, drei Gegner) plus `POD_PRESET_EXTRA_OPPONENTS` (`launch.py:73`, genau zwei weitere); `table_spec.py:35, 61, 64`; `web.py:300, 321, 349, 1507`; `play.py:259`; `paired_series.py:181`; `static/paired.js:14-16`; `static/partie.js:12`; `static/partie.css:64-65`; Hilfetexte `__main__.py:488`, `launch.py:345`.
- **Replay:** `semantic_replay/tape.py:49, 58, 98` (heute höchstens 5; für 6 gilt nach dem F1-Entwurf schon „ohne Replay-Anspruch“).
- **Ratsche/Negativtest:** `tests/unit/test_seats_5_6_part_a_1661.py:665` („seven seats are refused even with the switch“). Kriterium 1 des Entscheids vom 2026-11-08 verlangt Negativtests für 7 und 8 an jedem Zulassungspunkt; ausdrückliche Tests dafür fand eine Suche nur dort.
- **Kein Änderungsbedarf (`CODE_DERIVED`):** `frame_digest.py:232-268` (Digest je Sitz, ohne feste Sitzzahl); `cohort_fields` (`games.py:412-419`: `cohort`, `played_seats`, keine Sitzzahl); `card_outcomes` (schichtet nach Tischgröße). `max_players` steht nicht in der Fähigkeitsliste von `config/rules_engines.json` (grep leer), nur im Rollentext „2..6-player“ (`:49`). Den Text passt der Pin- bzw. Ableitungsweg an (`AGENTS.md` §4).
- **Policy (Owner):** `AGENTS.md:16-17`, `docs/STUDIO_SCOPE.md:36`, `docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md`, Entscheid-Register.
- **Zählung:** etwa 32 Stellen in rund 20 Dateien, mehr als die „rund 15“ der Charta. Die Charta zählte die Studio-Oberfläche und die Ratschen nicht mit. Nicht geprüft und deshalb `UNKNOWN`: Pilot-Sichten (`full_game_pilot_views.py`) auf feste Gegnerzahlen.

## 5. Bedingungen, Aufwand, Risiken

**Reihenfolge:**
1. 5/6 nach Option A abschließen: #1715 mit 4-Sitz-Vergleich, F5 als gezielte Szenarien, Tape ≥ 5, F1.
2. Owner entscheidet: entweder isolierter 7/8-Forschungsauftrag (Klausel vom 2026-11-08) oder gar nichts.
3. Nur bei positivem Forschungsergebnis **und** einem Owner-Entscheid, der das 6er-Maximum aufhebt, folgt ein Produkt-Paket.

Die Charta-Auslöser für eine Neubewertung (§4.3) stehen heute so: 6er-Partie höchstens 3-mal so lang wie die 4er-Partie → **erfüllt** (2,22× Wandzeit, Tisch A, n = 10); RSS höchstens 2 GB je JVM → **erfüllt** (höchstens 1.448 MiB); „der Owner spielt real Tische mit mehr als 6“ → **unbekannt**.

**Aufwand (Schätzung, Agent-Tage, ohne Owner-Zeit):**
- Isolierter Machbarkeitsversuch: Forschungs-JAR mit geänderter Konstante, eigener Harness, 2 Tische × 3–12 Seeds bei 7/8, Wandzeit/CPU/RSS/Vollständigkeit. **1–2 Tage** plus 1–2 h Owner-PC (CPU-exklusiv).
- Produkt 7/8 nach abgeschlossenem 5/6:
  - Code und Ratschen: 3–5 Tage.
  - Bridge-Gate-Nachweis: 1 Tag.
  - Messkampagne analog Teil B (F2/F3/F6/F8; die Blöcke mit 98/128 Partien): 2–3-mal die Rechenzeit von Teil B, 1–2 Owner-PC-Sitzungen.
  - F5-Regelszenarien und Tape-Entscheid: 2–4 Tage.
  - PLAY-Brett für 8 Sitze: 1–2 Tage.
  - **Summe etwa 8–13 Agent-Tage plus 2 Owner-PC-Sitzungen.**

**Risiken:**
- #1715 und #1692 (Determinismus) treten mit mehr Triggern häufiger auf.
- Engine-Verhalten bei 7/8 `UNKNOWN`; ein Fork-Befund wäre Owner-Vorbehalt.
- Pilot-Aussagen ohne Referenz.
- Je Antwort 4–9-fache Kosten verdrängen die Chulane-Fragen am Vierertisch.
- Das Ergebnis darf nie als 4P- oder 6P-Beleg erscheinen (Kohortenregel).

**Fragen an den Owner (Entscheidungsvorlage):**
- (a) Isolierter 7/8-Forschungsauftrag nach der Klausel vom 2026-11-08 (eigener Harness, kein Endpunkt, nicht als 4P/6P-Beleg): ja / nein / später (Vorschlag: später, nach Option A für 5/6).
- (b) Revision des 6er-Maximums (`AGENTS.md` §1, Entscheid 2026-11-08): ja / nein / erst nach der Forschung (Vorschlag: erst nach der Forschung).
- (c) Spielen Sie real an Tischen mit mehr als 6 Spielern, und wie oft? (offener Charta-Auslöser; ohne ein Ja hier hat 7/8 keinen belegten Nutzen.)
