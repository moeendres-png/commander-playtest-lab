# 5 und 6 Sitze, Teil A (#1661): was ohne Echt-Engine belegt ist

- **Stand:** Branch `feat/s2a-seats-5-6-prep-1661`, gebaut auf `main` @ `0fb8fce1`, vor dem Push auf `106b4939` nachgezogen (2026-11-20).
- **Was dieser Bericht nicht tut:** Er gibt 5/6 Sitze nicht frei. `launch.MAX_RELEASED_SEATS = 4`
  (`src/commander_lab/studio/launch.py:37`), `OPPONENT_COUNTS = [1, 2, 3]`
  (`src/commander_lab/studio/static/partie.js:11`) und die Serien-/`compare-decks`-Sperre bleiben
  unverändert. Die Freigabe ist ein eigener, Owner-gebundener PR (`AGENTS.md` §8, E15 Q5).
- **Belege:** Tests in `tests/unit/test_seats_5_6_part_a_1661.py`: 19 Testfunktionen, 35 Fälle.
  Alle Daten sind synthetisch, die Bridge ist eine Test-Bridge. Kein Echt-Engine-Lauf.
- **Teil B** (Echt-Engine F2/F3/F6/F7/F8) macht der Co-Lead in einem eigenen Lastfenster. Die
  Schrittliste steht in Abschnitt 5.

## 1. Ergebnis je Nachweis

Stände: **PASS (Test)** heißt, ein benannter Test ohne Engine belegt die Studio-/Bridge-
Schnittstelle. **NOT_RUN** heißt, es braucht Echt-Engine-Läufe (Teil B). **UNKNOWN** heißt, es
ist mit vorhandenen Mitteln nicht belegbar. Ein PASS an der Schnittstelle ist nie ein PASS der
Regel selbst.

| # | Nachweis | 5 SIMULATE | 5 PLAY | 6 SIMULATE | 6 PLAY | Begründung |
|---|---|---|---|---|---|---|
| F1 | Festlegungen `ALL`/`MULTIPLE`, 6 ohne Replay-Anspruch | Entwurf (Owner) | Entwurf (Owner) | Entwurf (Owner) | Entwurf (Owner) | Drei Sätze in Abschnitt 4. Ist-Stand per Test festgehalten (`test_f5_4_…`). |
| F2 | Vollständigkeit, 2 Tische × 12 Seeds | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | braucht Echt-Engine; Schritt B2 |
| F3 | Identität 1 gegen W Worker, Position in der JVM, N ≥ 20 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | braucht Echt-Engine; Schritt B3. Das Digest-Werkzeug `identity_row` ist an synthetischen Logs geprüft. |
| F4 | Verdeckte Information je Sitz 5 und 6 | PASS (Test) | PASS (Test) | PASS (Test) | PASS (Test) | Test-Bridge, alle laufenden Antworten, Mensch auf Sitz 1/5 (5 Sitze) und Sitz 1/5/6 (6 Sitze); Mutationsproben 9 von 10 rot (Abschnitt 2). **SIMULATE:** belegt ist nur die gemeinsame Schwärzung im Spielprotokoll (`read_game`); SIMULATE zeigt keine Hände live, und einen 5/6-Weg für SIMULATE in der Oberfläche gibt es noch nicht (Abschnitt 4, Freigabe-Diff Punkt 3). Ob die echte Bridge bei 5/6 nur Akteur-gebundene Zustände liefert: NOT_RUN (Teil B, Audit `audit_actor_scoped_frame` läuft in jeder Runner-Partie mit). |
| F5 | acht Regelpunkte aus Plan §2 | Schnittstelle PASS (Test), Regel NOT_RUN | wie links | wie links | wie links | Tabelle in Abschnitt 3: je Punkt zwei Spalten |
| F6 | Laufzeit 4/5/6, 10 Seeds, eine JVM je Partie und Pool | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | Schritt B4. Die p99-Latenz je Entscheidung schreibt das Studio-Protokoll nicht mit: UNKNOWN, solange niemand sie misst. |
| F7 | Piloten: Auslassungen, Angriffsziel-Verteilung | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | Schritt B5 (Auswertung der B2-Logs). Für 5/6 gibt es keine menschliche Referenz. |
| F8 | gepaarte Serie mit voller Sitz-Rotation, 25 bzw. 36 je Block und Arm | Planung PASS (Test), Lauf NOT_RUN | nicht anwendbar | Planung PASS (Test), Lauf NOT_RUN | nicht anwendbar | Rotation vollständig (Latin Square), jede Einheit gespielt, Ausfälle und Fehlsitze zensiert und je Klasse gezählt; Lauf in Schritt B6. **SIMULATE:** belegt ist nur der Planungs- und Auswertungscode (`run_comparison_series`, `pod_decks`, `start_series`); die Serien-Oberfläche kennt nur Vierertische (`POD_PRESETS`, `PAIRED_TABLE_SEATS = 4`), ein 5/6-Weg dort fehlt. |

Zusatz (Kriterium 3 des Co-Leads): **Die Partie-Seite stellt 5 und 6 Sitze dar:** PASS (Test,
Node mit DOM-Attrappe, Freigabe nur im Speicher simuliert). **Die Sperre ist die einzige Hürde
auf dem PLAY-Weg:** PASS (Test, echte Route `POST /api/games` mit Test-Bridge bis Spielende).
**Das Studio lehnt 5 Sitze ohne Schalter weiterhin ab:** PASS (Test).

## 2. Tests und Mutationsproben

| Test | belegt |
|---|---|
| `test_f4_no_running_response_carries_a_hidden_card_of_another_seat[5p-sitz1, 5p-sitz5, 6p-sitz1, 6p-sitz5, 6p-sitz6]` | Keine laufende Antwort enthält Handkarten (`hand`, `hand_cards`) eines anderen Sitzes. Die Test-Bridge legt jedem Zustand alle Hände bei. Das ist strenger als die echte Bridge, die KI-Zustände akteur-gebunden liefert. Mitgeprüft, aber schon durch die Bauart sicher und von keiner Mutationsprobe abgedeckt: das `context` einer KI-Entscheidung wird nie ausgeliefert und nie in einen Frame übernommen. Geprüft werden `GET /api/play`, die gehaltene Abfrage mit `since` (#1593), `GET /api/games` und der Zustand, den eine Antwort mit `start` trägt (#1578). Positivkontrolle: Die eigene Hand ist sichtbar. Nach Spielende sind alle Hände da, die Geheimnisse waren also zum Lecken vorhanden. |
| `test_f4_hidden_pick_of_ai_seat_five_or_six_stays_hidden_while_running[5, 6]` | Eine verdeckte Wahl der KI-Sitze 2 bis 6 (Bottom/Tutor) bleibt bis Spielende ohne Kartennamen. |
| `test_release_constant_is_the_only_seat_hurdle_on_the_play_route[5-0, 6-0, 6-5]` | Mit der Konstante 4 antwortet die Route mit 422 „locked“. Wird nur die Konstante (im Speicher) auf 6 gesetzt, spielt dieselbe Anfrage über die echte Route eine ganze Partie: 5 bzw. 6 Deck-Handles, Startsitz `seed % N`, Ergebnis, Sitze 0..N-1. |
| `test_studio_refuses_five_and_six_seats_at_the_seat_rule_and_the_play_route` | Die Abnahme aus #1661, soweit hier geprüft: die Sitzregel (`validate_released_seat_count`) lehnt 5/6 ohne Schalter ab und lässt sie mit Schalter zu, 7 auch mit Schalter nicht; die PLAY-Route `POST /api/games` antwortet bei 5 Sitzen mit 422. Batch, Paired und `compare-decks` prüfen die bestehenden Tests `test_studio_simulations.py:372, 403, 443`. |
| `test_f5_1` … `test_f5_8` | Abschnitt 3 |
| `test_f8_rotation_plan_is_complete_at_five_and_six_seats[5, 6]` | 25/36 Einheiten. Jede Kombination (Startsitz `seed % N`, getesteter Sitz) kommt genau einmal vor, jede relative Position N-mal, jedes Deck sitzt N-mal auf jedem Sitz (`pod_decks`). |
| `test_f8_series_plays_every_planned_unit_and_names_every_failure[5, 6]` | `run_comparison_series` spielt alle 2 × 25 bzw. 2 × 36 Partien in Planreihenfolge. Ein Ausfall auf Sitz 5 und ein Fehlsitz auf dem letzten Sitz zensieren je ein Paar, werden je Klasse gezählt (`EngineTimeout`, `Misseated`) und gewarnt. Keiner zählt als Niederlage. |
| `test_f8_default_censoring_limit_stops_a_decision_on_one_failed_pair` | Die Grenze von 5 %: Bei 25 und 36 Paaren lässt ein zensiertes Paar die Entscheidung zu, zwei Paare sperren sie. |
| `test_f8_series_manager_plans_seeds_for_whole_rotations[5, 6]` | Das Budget N² ergibt genau N aufeinanderfolgende Seeds. Plan und Dauer-Untergrenze rechnen mit N Sitzen je Seed. |
| `test_play_board_draws_five_and_six_seats_with_their_names_and_colors[5, 6]` | Das Brett zeichnet N Sitz-Panels (Sitz 1 bis Sitz N, mit Commander), die Hand nur dort, wo das Protokoll eine führt. Die Farben `.s4`/`.s5` sind vorhanden, das Grid hat keine feste Sitzzahl. |
| `test_new_game_dialog_offers_five_and_six_players_only_once_the_lock_line_changes` | Heute bietet der Dialog 2 bis 4 Spieler an. Nur mit geänderter Sperrzeile (im Speicher) bietet er 2 bis 6 an und füllt Sitz 2 bis Sitz 6 mit fünf verschiedenen Decks. Er sendet dann 5 Gegner und 6 Stile. |
| `test_identity_row_ignores_run_fields_and_catches_one_changed_frame` | Das F3-Werkzeug für Teil B ignoriert Zeit, IDs, JVM-Position und Pfad und erkennt eine geänderte Entscheidung. |

**Mutationsproben** (je eine Einzelmutation, dann die neue Testdatei mit `PYTHONPATH=<Clone>/src`,
danach `git checkout`). Ergebnis: 9 von 10 rot.

| Mutation | Ergebnis |
|---|---|
| Frame-Schwärzung der Hand für Sitz 5 aus (`games.redact_frame_for_human_seats`, `seat != 4`) | rot (11 Fälle) |
| dasselbe für Sitz 6 (`seat != 5`) | rot (5) |
| Pilot-State-Schwärzung für Sitz 5 aus (`redact_pilot_state_for_human_seats`) | rot (9) |
| dasselbe für Sitz 6 | rot (4) |
| verdeckte Wahl (`private_selection`) für Sitz 5 sichtbar | rot (2) |
| dasselbe für Sitz 6 | rot (1) |
| Pilot-State behält `hand_cards` | rot (12) |
| `_sanitize_decision` schwärzt gar nicht (`play.py`) | rot (12) |
| Brett liest „Full Game Seat N“ zusätzlich 0-basiert (alter Stand, siehe Befund B-1) | rot (2) |
| Frame-Schwärzung behält `hand_cards` | **grün: redundante Stelle**. `games._player()` übernimmt `hand_cards` nie in einen Frame. Das Entfernen dort ist Absicherung, keine Testlücke. |

## 3. F5: die acht Regelpunkte (Plan §2), Schnittstelle getrennt von der Regel

| Punkt | Schnittstelle (ohne Engine) | Regel selbst (XMage) |
|---|---|---|
| 1 APNAP | PASS: `test_f5_1_apnap_trigger_order_at_seat_five_or_six_passes_only_engine_options[5, 6]`. Eine `trigger_order`-Entscheidung auf dem letzten Sitz kommt unverändert an, eine gefälschte ID wird mit 422 abgelehnt, die Reihenfolge geht nur aus angebotenen IDs zurück. | NOT_RUN: Reihenfolge über mehr als zwei Nichtaktive nur am Pin prüfbar. Teil B kann `trigger_order`-Entscheidungen in den B2-Logs zählen, prüft die Regel aber nicht. Gezielte Szenarien: UNKNOWN. |
| 2 Ausscheiden im Stapel/Kampf | PASS: `test_f5_2_a_seat_leaving_mid_game_keeps_the_game_running_for_the_others[5-out0, 6-out1]`. Die Seite folgt den übrigen Sitzen, Ausgeschiedene erscheinen als verloren, nichts leckt, der Engine-Sieger steht im Ergebnis. | NOT_RUN/UNKNOWN: ob Objekte und Kontrolleffekte korrekt verschwinden, zeigt nur der Pin |
| 3 Commander-Schaden je Paar | PASS: `test_f5_3_commander_damage_for_all_ordered_pairs_at_six_seats_is_shown_as_published`. Alle 30 geordneten Paare kommen beim richtigen Verteidiger und Angreifer an, nichts wird addiert oder fallen gelassen. | NOT_RUN: 21-Schwelle je Commander am Pin |
| 4 Einflussbereich `ALL` | PASS (Ist-Stand): `test_f5_4_bridge_keeps_range_all_and_attack_multiple_for_every_table_size` liest die Bridge nur. `ALL` und `MULTIPLE` gelten für jede Tischgröße, es gibt keinen 5/6-Sonderzweig. Die Sichtbarkeit belegen die F4-Tests. | Festlegung: Owner (F1). Engine-Semantik: NOT_RUN |
| 5 Mehrfach-Verteidiger | PASS nach Fix: `test_f5_5_attacks_on_several_defenders_mark_exactly_those_seats[5, 6]` (vor dem Fix rot: markiert waren Sitze 2, 3 und 5 statt 2 und 5) | NOT_RUN: Angriffs- und Blockzuordnung am Pin |
| 6 Concede/Terminal | PASS: `test_f5_6_human_concedes_at_five_or_six_seats_and_only_then_hands_are_shown[5, 6]`. Der Mensch auf dem letzten Sitz gibt auf, das Ergebnis kommt von der Engine, Hände werden erst mit dem Abschlusszustand gezeigt. | NOT_RUN: mehrere Concedes und „letzter Spieler“ in XMage |
| 7 Sitz-/Zugreihenfolge | PASS: `test_f5_7_seat_and_turn_order_cover_seats_five_and_six[5, 6]`. Sitze 0..N-1, Piloten 1..N, Startsitz `seed % N` (interaktiv per Test, Runner `full_game.py:1514` per Quelltext-Prüfung). Die Frames folgen der Engine-Reihenfolge, N Seeds decken alle Startsitze ab. | NOT_RUN: Zugreihenfolge über die erste Runde hinaus am Pin; „lückenlos im Log“ prüft B2 |
| 8 Replay-Asymmetrie | PASS: `test_f5_8_replay_tape_takes_five_seats_and_refuses_six`. Das Tape nimmt 5 Sitze, lehnt 6 ab (`tape.py` dreimal `le=5`). Kein Studio-Modul nutzt `semantic_replay`. | 5 Sitze Tape-MATCH: NOT_RUN. 6 Sitze: nicht möglich ohne Tape-Erweiterung (F1-Satz 3) |

**Fork-Befund:** keiner aus Teil A. Offen bleibt #1628 (Kampfregel, `needs:owner`). Der
Issue-Entwurf für einen möglichen Befund aus Teil B steht in Abschnitt 5, Schritt B7.

## 4. Befunde, F1-Entwurf, was bei 6 Sitzen nicht geht

**B-1 (behoben in diesem PR, PLAY-Anzeige):** `seatPanel` in `partie.js` hat ein Angriffsziel
„Full Game Seat N“ zusätzlich 0-basiert gelesen. Ein Angriff auf Sitz 2 markierte daher auch
Sitz 3 als angegriffen. Die Bridge benennt Spieler 1-basiert
(`XmageFullGameSession.java:233`, `"Full Game Seat " + (index + 1)`). Das Brett rechnet keine
Regel, es ordnet nur den Engine-Namen dem Sitz zu. Der Fehler bestand schon bei 4 Sitzen, mit
mehr Verteidigern wird er häufiger. Weiter offen (UNKNOWN): die Formen `Seat N`/`Seat N+1`
derselben Funktion sind ebenso doppeldeutig. Woher sie kommen, ist im Repo nicht belegt; sie
sind unverändert.

**B-2 (Befund, kein Fix, Voraussetzung vor dem Freigabe-PR):** `card_outcomes.build_table` (`card_outcomes.py:812-837`) trennt Partien nicht nach Tischgröße.
Das gilt schon heute für 2/3/4 Sitze. Mit 5/6 Sitzen mischt die Kartenauswertung Basis-
Siegraten von 1/4, 1/5 und 1/6. Die gepaarte Serie ist nicht betroffen: Paare brauchen
denselben Gegner-Tisch. „Kohorten nie mischen“ ist harte Regel, deshalb ist die Trennung nach
Tischgröße eine **Voraussetzung vor dem Freigabe-PR**, nicht ein Teil davon. Ansatz aus #1671:
die geschichtete Risikodifferenz (`card_outcomes.py:922`) mit der Tischgröße als Schicht und
„nicht zusammenfassen bei anderem Gegnertisch-Satz“ (`card_outcomes.py:1041`). Der Co-Lead
legt dafür ein eigenes Issue an; dieser PR baut es nicht.

**B-3 (Hinweis):** Der Planungstext im Serien-Dialog (`paired.js:40`) nennt „exakt 0,612 für
unabhängige Partien mit 25 % Siegrate“. Bei 5/6 Sitzen ist die Basis 20 % bzw. 16,7 %
(exakt 0,566 bzw. 0,527). Der Planungswert 0,63 bleibt vorsichtig, der Text sollte bei 5/6 die
Sitzzahl nennen. Die Dauer-Untergrenze (541,2 Partien/h, gemessen bei 4 Sitzen) bleibt eine
Untergrenze, weil 5/6-Partien länger dauern.

**UNKNOWN (nicht 5/6-spezifisch):** Verdeckt Exiliertes. `face_down` wird nur beim Schreiben
eines Frames zu „(verdeckt)“ (`games.py:93`); `redact_pilot_state_for_human_seats`
(`games.py:579-598`) entfernt nur die Hand. Ob die Bridge verdeckt exilierte Karten anderer
Sitze im Pilot-State mit Namen liefert, ist nicht geprüft; die Tests legen `exile: []` an.
Ebenso UNKNOWN bleiben die Formen `Seat N`/`Seat N+1` im Brett (`partie.js:463-464`).

**B-4 (Fakt):** Die CLI `python -m commander_lab.studio play` nimmt 2 bis 6 `--deck` ohne
Sperre (Entwicklerweg). Teil B misst damit. `play-batch` ebenso.

**F1, Entwurf der drei Sätze für den Owner (Owner legt fest):**
1. „Bei 5 und 6 Sitzen gilt dieselbe Engine-Einstellung wie bei 2 bis 4 Sitzen: Einflussbereich
   `ALL` (jeder Spieler wirkt auf alle) und Angriffsoption `MULTIPLE` (Angriff auf mehrere
   Gegner in einem Kampf); das ist eine Produkt-Einstellung, keine Regelvereinfachung.“
2. „5 Sitze werden mit Replay-Nachweis qualifiziert (Tape-MATCH wie bei 4 Sitzen).“
3. „6 Sitze werden ohne Replay-Anspruch freigegeben; die Oberfläche sagt das, und ein
   6-Sitz-Lauf zählt nie als Replay-PASS. Eine Tape-Erweiterung auf 6 ist eine eigene, geprüfte
   Änderung.“ (Alternative für den Owner: erst Tape erweitern, dann 6 freigeben.)

**Was bei 6 Sitzen konkret nicht geht** (für die Hinweistexte des Freigabe-PR):

| Funktion | bei 6 Sitzen | Beleg |
|---|---|---|
| Partie ansehen, live spielen, Nachspiel (Schritt/Zug vor und zurück) | geht. Das Nachspiel nutzt die aufgezeichneten Frames, nicht das Tape. | `test_play_board_…[6]`, `test_f5_8_…`; `replay.js` hat keinen Sitzbezug (nicht eigens bei 6 getestet) |
| Semantik-Replay (Tape-MATCH, Zwillingslauf) | **geht nicht**: das Manifest lehnt 6 Sitze ab | `semantic_replay/tape.py:49, 58, 98`; `test_f5_8_…` |
| `scripts/run_external_full_game_conformance.py` und das Replay-Gate | **geht nicht** für 6 (nutzt das Tape) | `semantic_replay/gate.py` |
| PB-03-Zeilen | nicht anwendbar: 30 feste Java-Fixtures, unabhängig von der Sitzzahl | `qualification/current_boundary/pb03_runtime.py` |
| Bridge-Gate-Referenzsatz | gilt nur für 4 Sitze; ein 5/6-Satz fehlt | `docs/STUDIO_PLAN_SIMULATOR.md:58-66` |
| Kartenauswertung über alle Partien | geht, mischt aber Tischgrößen | B-2 |

Vorschlag Hinweistexte (nur Text):
- Partie-Dialog bei 6 Spielern: „6 Spieler: Die Partie wird aufgezeichnet und lässt sich
  nachspielen. Einen Replay-Nachweis (Semantik-Replay) gibt es bisher nur bis 5 Sitze.“
- Serien-Dialog bei 5/6: „Tisch mit 5 (6) Sitzen: Basis-Siegrate 20 % (16,7 %). Ergebnisse
  werden nicht mit 4-Sitz-Serien zusammengezählt.“
- Allgemein bis zur Freigabe (E15 Q5, schon so gewollt): „5 und 6 Sitze sind noch nicht
  freigegeben.“

**Der Freigabe-PR** (Owner-Go vorausgesetzt). Für PLAY ist er mechanisch, für SIMULATE nicht:

*A. Mechanisch (Konstanten und Texte):*
1. `src/commander_lab/studio/launch.py:37`: `MAX_RELEASED_SEATS = 6`; der Kommentar
   `launch.py:33-36` („two to four seats … locked“) wird angepasst.
2. `src/commander_lab/studio/static/partie.js:11`: `const OPPONENT_COUNTS = [1, 2, 3, 4, 5];`;
   der Kommentar `partie.js:8-10` wird angepasst. Der Wächter `test_studio_static_guards.py:361`
   folgt der Konstante von selbst.
3. Texte: Hilfe `--allow-unreleased-seats` (`__main__.py:442`, „unreleased outside Owner
   qualification“; der Schalter wird nach der Freigabe überflüssig oder entfällt) und der
   Bias-Hinweis in `sources.py:275` („seat 5 is not released for Studio play“).
4. Tests, die die Sperre festhalten und dann umgeschrieben werden:
   `test_human_seat_play_1169.py:935` (`(2, 4)` und die 422 für 5/6),
   `test_studio_simulations.py:372, 403, 443` (Batch, Paired, `compare-decks` lehnen 5/6 ab),
   und in dieser Datei `test_studio_refuses_five_and_six_seats_at_the_seat_rule_and_the_play_route`,
   der erste Teil von `test_release_constant_is_the_only_seat_hurdle_on_the_play_route`
   (`== 4`, 422) und der `locked`-Teil von `test_new_game_dialog_…`.

*B. Für SIMULATE zusätzlich zu bauen (keine Konstante, eigener Umfang):*
5. Die Serien-Oberfläche kennt nur Vierertische: `POD_PRESETS: dict[str, tuple[str, str, str]]`
   (`launch.py:41`, drei Gegner je Preset) und `PAIRED_TABLE_SEATS = 4` (`paired.js:11-12`,
   Plan und Dauer rechnen mit 4 Sitzen). Nötig sind Presets oder eine Gegnerwahl mit 4 bzw. 5
   Gegnern, die Sitzzahl im Serien-Dialog (`seats_per_seed` aus dem Tisch, nicht fest 4) und
   Tests dazu. Ohne das ist SIMULATE bei 5/6 nur über die CLI (`compare-decks`) erreichbar.
6. B-2 (Trennung der Kartenauswertung nach Tischgröße) muss **vorher** gelöst sein; eigenes Issue.

*C. Owner-Sache:* Hinweistexte (oben), B-3 nach Entscheid, Entscheid-Eintrag (E16) und die
Owner-Texte (`AGENTS.md` §1 „two to four seats are active“, `STUDIO_SCOPE.md`).

## 5. Teil B: Schrittliste für den Co-Lead (Echt-Engine, ca. 2–3 h)

Allgemein: Echt-Engine nur bei 1-min-loadavg < 2 (`cut -d' ' -f1 /proc/loadavg`) und ohne
parallele Suiten. Läufe im Hintergrund mit Zeitgrenze, keine Poll-Schleifen. Alles, was nicht
läuft, heißt `NOT_RUN`. Die Zeitschätzungen beruhen auf einem einzigen Messpunkt (6 Sitze
3,2-fach gegenüber 4, n = 1); sie sind unsicher. Gegen die Engine ist diese Liste nicht
geprüft. Geprüft sind nur die Studio-Befehle und das Digest-Werkzeug.

**Wichtig für Vergleiche:** `play` startet die Engine mit dem reinen Umgebungsbefehl, also ohne
das Überspringen erzwungener Pässe. Serien (`compare-decks`, Pool) nutzen
`launch.fast_bridge_command`, mit `-Dcommanderlab.fullGame.skipForcedDecisions=true`. Die
Entscheidungszahlen beider Wege unterscheiden sich daher absichtlich. Deshalb laufen alle
F2/F3/F6-Läufe unten über `play-batch` mit einem festen Befehl `FAST`, der den Serien-Optionen
entspricht. Verglichen werden immer **gleiche Spiel-IDs in getrennten `--data`-Ordnern**: Die
Spiel-ID geht in `scenario_id` ein, und unterschiedliche IDs sollen kein Störfaktor sein.

**B0 Vorbereitung (gemeinsam):**
```bash
cd <CLONE> && export PYTHONPATH=$PWD/src
python -c "import commander_lab; print(commander_lab.__file__)"   # muss <CLONE>/src zeigen
JAR=<PFAD>/xmage-engine-bridge.jar
FAST="java -XX:+UseSerialGC -Dh2.bindAddress=127.0.0.1 -Dcommanderlab.fullGame.skipForcedDecisions=true -Xmx3g -jar $JAR full-game"
export D=<SCRATCH>/s2b-data; mkdir -p "$D"
P=data/decks/precons
A4="$P/2023_eldrazi_unbound.json $P/2026_lorehold_spirit.json $P/2024_animated_army.json $P/2022_token_triumph.json"
A5="$A4 $P/2023_veloci_ramp_tor.json";  A6="$A5 $P/2023_blood_rites.json"
B4="$P/2024_death_toll.json $P/2024_deep_clue_sea.json $P/2023_divine_convocation.json $P/2023_fae_dominion.json"
B5="$B4 $P/2024_family_matters.json";   B6="$B5 $P/2023_tinker_time.json"
deckargs() { for f in $1; do printf -- '--deck %s ' "$f"; done; }
# Wandzeit, CPU-s (Kindprozesse inkl. JVM) und RSS-Spitze eines Befehls (/usr/bin/time fehlt hier)
measure() { python -c 'import json,resource,subprocess,sys,time
t=time.monotonic(); rc=subprocess.run(sys.argv[2:]).returncode; r=resource.getrusage(resource.RUSAGE_CHILDREN)
json.dump({"rc":rc,"wall_s":round(time.monotonic()-t,2),"cpu_s":round(r.ru_utime+r.ru_stime,2),"maxrss_kib":r.ru_maxrss},open(sys.argv[1],"w"))' "$@"; }
```
Vorab je Tisch einen Seed mit 6 Sitzen spielen (Rauchtest). Bricht ein Deck mit „unsupported“
ab, das Deck durch den nächsten Precon im Ordner ersetzen und das im Bericht notieren.

**B2 = F2 Vollständigkeit** (2 Tische × 12 Seeds × {5, 6} = 48 Partien, eine JVM je Partie,
sequenziell). Die Läufe dienen zugleich als F6-Einzel-JVM-Messung, als F3-Basis und als
F7-Datenbasis:
```bash
for n in 5 6; do for t in A B; do eval decks=\$$t$n; for s in $(seq 1 12); do
  COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST" measure "$D/m-$t$n-s$s.json" \
    python -m commander_lab.studio --data "$D/single" play-batch $(deckargs "$decks") --game $s:s2b-$t$n-s$s
done; done; done
# optional, nur wenn das Lastfenster reicht (Basis für F6): dieselbe Schleife mit "for n in 4"
```
Abnahme je Sitzzahl: 24/24 mit `status == "finished"`, sonst ist jede Abweichung als Klasse
benannt (`failure_class`). Jede Klasse in den Frames gehört zu den 17 Klassen von
`ExternalPilotDecisionPolicy._SUPPORTED_CLASSES` (`full_game_pilot/policy.py:29`). Die
Sitzfolge ist lückenlos (jeder Sitz 0..N-1 kommt in den Frames vor). Auswertung:
```bash
python - "$D/single/games" <<'PY'
import sys, glob, gzip, json, collections
from commander_lab.engine.rules.full_game_pilot.policy import ExternalPilotDecisionPolicy as P
ok = P._SUPPORTED_CLASSES; rows = collections.defaultdict(collections.Counter)
for f in sorted(glob.glob(sys.argv[1] + "/s2b-*.jsonl.gz")):
    L = [json.loads(l) for l in gzip.open(f, "rt")]; h = L[0]; r = L[-1]; fr = [x for x in L if x.get("kind") == "frame"]
    n = len(h["seats"]); rows[f"{n}p"][r.get("status")] += 1
    bad = {x["decision_class"] for x in fr} - ok
    seats = {x["seat"] for x in fr}
    if r.get("status") != "finished" or bad or seats != set(range(n)):
        print("ABWEICHUNG", f, r.get("status"), r.get("failure_class"), sorted(bad), sorted(set(range(n)) - seats))
print({k: dict(v) for k, v in rows.items()})
PY
```

**B3 = F3 Identität** (N ≥ 20 je Sitzzahl, gleiche Spiel-IDs, getrennte Ordner):
- (a) Position in der JVM: dieselben 12 Seeds von Tisch A in **einer** JVM
  (`-Dcommanderlab.fullGame.gamesPerJvm=12`), einmal aufsteigend und einmal absteigend. Mit der
  B2-Basis (eine JVM je Partie) sind das je Sitzzahl 2 × 12 = 24 Vergleiche:
```bash
FAST12="java -Dcommanderlab.fullGame.gamesPerJvm=12 ${FAST#java }"
for n in 5 6; do eval decks=\$A$n
  COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST12" python -m commander_lab.studio --data "$D/up" play-batch \
    $(deckargs "$decks") $(for s in $(seq 1 12); do printf -- '--game %s:s2b-A%s-s%s ' $s $n $s; done)
  COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="$FAST12" python -m commander_lab.studio --data "$D/down" play-batch \
    $(deckargs "$decks") $(for s in $(seq 12 -1 1); do printf -- '--game %s:s2b-A%s-s%s ' $s $n $s; done)
done
```
  Das Spielprotokoll hält `position_in_jvm` und `jvm_life_id` fest. Vorher an einem Lauf
  prüfen, dass die Positionen 1..12 wirklich in einer JVM liegen (`jvm_life_id` gleich).
- (b) 1 Worker gegen W = 3 Worker im Pool: je Sitzzahl `compare-decks` zweimal, gleiche Seeds
  und gleiche `--series-id`, getrennte Ordner; `--pairs 10` ergibt 20 Partien je Lauf. Der Pool
  baut seinen Befehl selbst (`series_engine`):
```bash
for n in 5 6; do eval decks=\$A$n; set -- $decks; base=$1; shift; var=$P/2023_divine_convocation.json
  for w in 1 3; do COMMANDER_LAB_STUDIO_SERIES_POOL=1 COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -Xmx3g -jar $JAR full-game" \
    python -m commander_lab.studio --data "$D/w$w" compare-decks \
    --base-deck "$base" --variant-deck "$var" $(for o in "$@"; do printf -- '--opponent %s ' "$o"; done) \
    --pairs 10 --look-every 10 --base-seed 2000 --rotate-seats --allow-unreleased-seats \
    --workers $w --series-id s2b-id-$n --out "$D/id-$n-w$w.json"; done; done
```
- Vergleich mit dem geprüften Werkzeug (`identity_row`). Primär wird
  `semantic_transcript_sha256` verglichen, wie im 4-Sitz-Bridge-Gate. Zusätzlich Sieger,
  Entscheidungszahl und `frame_digest`, die zeigen, wo zwei Läufe auseinandergehen:
```bash
python - <<'PY'
import glob, os, sys
sys.path.insert(0, os.getcwd())
from tests.unit.test_seats_5_6_part_a_1661 import identity_row
D = os.environ["D"]
def rows(folder, pattern): return {os.path.basename(p): identity_row(p) for p in glob.glob(f"{D}/{folder}/games/{pattern}")}
def sem(a, b): return sum(a[k]["semantic_transcript_sha256"] == b.get(k, {}).get("semantic_transcript_sha256") for k in a)
for n in (5, 6):
    base = rows("single", f"s2b-A{n}-s*.jsonl.gz")
    for other in ("up", "down"):
        o = rows(other, f"s2b-A{n}-s*.jsonl.gz")
        print(n, other, f"semantisch {sem(base, o)}/{len(base)}", f"vollständig {sum(base[k] == o.get(k) for k in base)}/{len(base)}")
    w1, w3 = rows("w1", f"s2b-id-{n}-*.jsonl.gz"), rows("w3", f"s2b-id-{n}-*.jsonl.gz")
    print(n, "pool w1/w3", f"semantisch {sem(w1, w3)}/{len(w1)}", f"vollständig {sum(w1[k] == w3.get(k) for k in w1)}/{len(w1)}")
PY
```
  (`compare-decks` schreibt nach `<data>/games/`, Spiel-IDs `<series-id>-<arm>-s<seed>-t<sitz>`,
  `paired_comparison.py:1170`.) Abnahme: n gleich von N mit N ≥ 20 je Sitzzahl und Vergleich.
  Jede Abweichung wird als Befund mit Seed und Feld gemeldet, sie wird nicht weggemittelt.
  Weichen nur `frame_digest` und nicht der semantische Hash ab, zuerst prüfen, ob ein Frame-Feld
  laufabhängig ist. Frames enthalten heute keine Objekt-IDs (`games._permanent`,
  `games._card_name`). Ein Replay-Tape-MATCH ist für 6 Sitze ausgeschlossen (F1-Satz 3). Für 5
  Sitze bräuchte der Tape-Zwilling einen 5-Sitz-Aufruf von `semantic_replay.gate.run_replay_gate`,
  den es heute als CLI nicht gibt: NOT_RUN.

**B4 = F6 Laufzeit** (Tisch A, Seeds 1–10, 4/5/6): aus `m-A{n}-s{s}.json` von B2 kommen
`wall_s`, `cpu_s` und `maxrss_kib`, aus dem Ergebnis `decision_count` und
`forced_decisions_skipped`. Berichtet werden Median und Spannweite je Sitzzahl mit n, dazu das
Verhältnis 5/4 und 6/4 auf denselben Seeds. Für 4 Sitze braucht es den optionalen B2-Lauf. Fehlt
er, bleibt das Verhältnis UNKNOWN. Pool: die Wandzeit der B3b-Läufe mit `w3`, geteilt durch die
Zahl der Partien. p99 je Entscheidung bleibt UNKNOWN, weil Frames keine Zeitstempel tragen.
Daraus entsteht nur ein **Vorschlag** für Zeitgrenzen und Worker-Deckel; heute gelten
sitzzahl-blind 120 s je Anfrage, 50.000 Entscheidungen (`full_game.py:1188-1189`) und 1.800 s je
Pool-Partie (`game_pool.py:55`). Ein Budget legt der Owner fest.

**B5 = F7 Piloten** (aus den B2-Logs, keine neuen Läufe): je Sitzzahl die
`declare_attacker`-Frames mit Ziel (`" attacks Full Game Seat N"` im gewählten Label) zählen,
als Angriffsziel-Verteidiger-Verteilung n/N. Die Frames ohne Angreifer dienen als
Auslassungs-Zähler. Dazu `forced_decisions_skipped` aus den Ergebnissen. Im Gültigkeitsblock
steht: „keine menschliche Referenz für 5/6“. Wie der Auslassungs-Zähler genau definiert ist,
legt der Co-Lead fest. Hier ist er ein Vorschlag.

**B6 = F8 gepaarte Serie** (je Sitzzahl ein Block: 25 bzw. 36 Paare, also 50 bzw. 72 Partien):
```bash
for n in 5 6; do eval decks=\$A$n; set -- $decks; base=$1; shift; var=$P/2023_divine_convocation.json
  COMMANDER_LAB_STUDIO_SERIES_POOL=1 python -m commander_lab.studio --data "$D/f8" compare-decks \
    --base-deck "$base" --variant-deck "$var" $(for o in "$@"; do printf -- '--opponent %s ' "$o"; done) \
    --pairs $((n*n)) --look-every $((n*n)) --base-seed 3000 --rotate-seats --allow-unreleased-seats \
    --workers 3 --series-id s2b-f8-$n --out "$D/f8-$n.json"; done
```
Abnahme: `pairs_played == 25/36`, `seeds` = 5 bzw. 6 aufeinanderfolgende,
`pairs_censored` ausgewiesen, jede zensierte Partie in `failure_classes`, keine stillen
Ausfälle (2 × Budget = Zahl der Logs mit Ergebnis plus Zahl der benannten Ausfälle). Die
Antwort (`DECIDED`/`NOT_DECIDED`) ist hier kein Ziel und wird nicht als Deck-Aussage berichtet.
Kohorte: nur 5- bzw. nur 6-Sitz-Partien, nie mit 4 gemischt.

**B7 Fork-Befund (Vorlage, nur falls Teil B einen findet):** Titel „Fork-Befund 5/6 Sitze:
<Regelpunkt>“. Inhalt: Pin `f4d12f6e80`, Seed, Tisch (Deck-Dateien), Sitzzahl, Frame-Nummer,
erwartetes und beobachtetes Verhalten mit Regelzitat, kein Fix. Labels `needs:owner`, Verweis
auf #1661 und gegebenenfalls #1628. Fork- und Bridge-Änderungen sind Owner- bzw.
Studio-Bridge-Gate-Sache.

**Zeitbudget (Schätzung, unsicher):** B2 48 Partien ≈ 1,5–2 h sequenziell (4-Sitz-Basis
≈ 50 s, ×2,4 bis ×3,2). B3a 48 Partien in 4 JVMs ≈ 1–1,5 h. B3b und B6 zusammen 80 + 122
Partien mit 3 Workern ≈ 1,5–2 h. Das sprengt 2–3 h. Vorschlag zur Reihenfolge: B2 (5 und 6),
B3b, B6, dann B3a und die 4-Sitz-Basis, wenn Zeit bleibt. Was offen bleibt, wird als
`NOT_RUN` berichtet.

## 6. Prüflauf dieses PR

Alle Läufe mit `PYTHONPATH=<Clone>/src`; `commander_lab.__file__` zeigte auf `<Clone>/src`.
Die Zahlen stehen im PR-Text. Nicht gelaufen: Echt-Engine (Teil B), Windows, echter Browser
(der Brett-Test nutzt eine DOM-Attrappe in Node), echte Studio-Datenbank.
