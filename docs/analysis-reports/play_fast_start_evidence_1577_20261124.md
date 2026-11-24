# #1577: PLAY mit Fast-Flags, Echt-Engine-Beleg, Identitätsprobe und Startzeit (2026-11-24)

Refs #1577, #1558, #1591. Alle Zahlen: lokale Messung am Owner-PC, `SIMULATED_RESULT`, kein CI-Beleg,
keine Qualifikation. Die Bridge-JAR wurde für diese Messung aus `main` `4d32d5eb5` lokal gebaut
(`mvn -o -DskipTests package` in `engine-bridge/`, kein Eingriff in den Quelltext), SHA-256
`dacd9b15b4263fd58fe03c75c4bf25fb69264058ca822d8820b9f2fd73466f91`; Zustand
`BRIDGE_AHEAD_OF_QUALIFICATION`, `covered_by_sealed_epoch: false`. Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d`,
Engine 1.4.62, Java 21, Linux, 16 Kerne. Die JAR im Studio-Datenordner des Owners war vom 2026-11-11 und kennt den
Schalter nicht; sie wurde nicht verwendet.

Tisch aller Läufe: Mensch am Sitz 0 mit `precon/2026/lorehold_spirit` gegen die Engine-KI mit
`precon/2024/animated_army`, über die PLAY-Routen (`POST /api/games`, `/api/play/{id}/decision`), KI-Pause 0 ms.
Der Mensch ist das Testskript `_scripted_human_answer` aus `tests/unit/test_human_seat_play_1169.py`
(deterministisch, kein Pilot, keine Stärkeaussage).

## 1. Echt-Engine-Test (war `NOT_RUN`)

`test_real_engine_human_seat_plays_a_game_to_its_end_through_the_play_routes` mit
`COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -Xmx3g -jar <jar> full-game"`: **1 passed, 43,7 s**.
Seed 11: Status `finished`, Sieger Sitz 1, `decision_count` 899, `forced_decisions_skipped` 282, 617 Frames,
Antworten des Menschen 357 (mulligan 1, priority 347, target 1, choose_object 8), kein Concede.

## 2. Identitätsprobe, Schalter an gegen aus (gleiche Seeds)

Schalter aus: `-Dcommanderlab.fullGame.skipForcedDecisions=false` im Umgebungsbefehl.

| Seed | Schalter | Sieger | `decision_count` | übersprungen | Frames | Antworten Mensch | `semantic_transcript_sha256` | Dauer |
|---|---|---|---|---|---|---|---|---|
| 11 | aus | [1] | 899 | 0 | 899 | 357 | `d2314ebea1faabd55775b0abc1a6c707760939047ccf970e688b4dcd1dafa7b5` | 19,0 s |
| 11 | an | [1] | 899 | 282 | 617 | 357 | `d2314ebea1faabd55775b0abc1a6c707760939047ccf970e688b4dcd1dafa7b5` | 15,3 s |
| 12 | aus | [1] | 576 | 0 | 576 | 199 | `a588f7fe…` | 11,0 s |
| 12 | an | [1] | 576 | 46 | 530 | 199 | `a588f7fe…` | 10,5 s |
| 13 | aus | [1] | 428 | 0 | 428 | 158 | `d11acbd8…` | 9,9 s |
| 13 | an | [1] | 428 | 59 | 369 | 158 | `d11acbd8…` | 9,2 s |

Ergebnis: 3 von 3 Seeds mit gleichem Sieger, gleicher Entscheidungszahl, gleichem Transkript-Hash (für die Seeds 12
und 13 sind hier nur die ersten 8 Zeichen festgehalten, die Rohdateien der Läufe liegen nach einem Neustart der
Messsitzung nicht mehr vor; die Gleichheit der vollen Hashes wurde im Lauf geprüft) und gleicher Zahl der Antworten des Menschen. Frames plus übersprungene Pässe ergeben jeweils
`decision_count` (617+282, 530+46, 369+59). Das belegt die Gleichheit der Partie für diesen Tisch und diese
Seeds, nicht für jeden Tisch (andere Decks, 4 bis 6 Sitze: `UNKNOWN`). Die Zeitunterschiede (bis 3,7 s)
sind Einzelwerte, keine Serie.

## 3. Startzeit PLAY (AppCDS und Fast-Flags), Seed 12, n = 5 je Variante

Gemessen: Zeit von der Startanfrage bis zur ersten offenen Entscheidung des Menschen, und bis zum Spielende.
Reihenfolge nacheinander (nicht verschränkt), ruhige Maschine. Das Archiv: `build-appcds`, 14,4 s, 322 MB.

| Variante | erste Entscheidung (s, 5 Werte) | Median | Spielende (s, 5 Werte) | Median |
|---|---|---|---|---|
| Basis: G1, Schalter aus, kein Archiv | 3,45 / 2,97 / 2,94 / 3,25 / 3,01 | 3,01 | 8,96 / 8,59 / 8,50 / 8,68 / 9,23 | 8,68 |
| Fast-Flags (Serial-GC, Schalter an), kein Archiv | 19,41 / 3,05 / 3,01 / 3,30 / 3,13 | 3,13 | 24,71 / 8,20 / 8,03 / 8,85 / 8,32 | 8,32 |
| Fast-Flags mit Archiv `<jar>.jsa` | 2,56 / 2,02 / 2,01 / 2,09 / 2,07 | 2,07 | 8,59 / 7,19 / 7,40 / 7,37 / 7,34 | 7,37 |

Lesart: Das AppCDS-Archiv verkürzt den Start um etwa 1,0 s (Median 3,13 auf 2,07 s, rund 34 %); Serial-GC allein
ist beim Start im Rauschen (3,01 gegen 3,13 s). Der Ausreißer 19,41 s ist der erste Lauf nach dem Wechsel der JAR
(kalter Dateicache), er steht ungekürzt in der Tabelle. Der Spielende-Vorteil des Überspringens ist bei KI-Pause
0 ms klein; er wächst mit der eingestellten KI-Pause, weil jeder übersprungene Pass diese Pause nicht mehr
durchläuft (nicht gemessen, `UNKNOWN`).

## Offen

- Kein echter JVM-Start mit einem anderen Collector im Befehl (G1 wurde in der Basis-Variante gesetzt und startete;
  Parallel-GC und ZGC `UNKNOWN`).
- Messung mit eingestellter KI-Pause und mit Vierer-Tisch (Chulane) `UNKNOWN`.
- Windows-PC `UNKNOWN` (alles hier Linux).
