# 7 und 8 Sitze: Machbarkeitsversuch mit der Bridge (isolierte Forschung, Refs #1672)

**Einordnung:** isolierte Forschung nach der Klausel in `docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md` (Owner-Anweisung 2026-11-22, #1672/#1656). Alle Zahlen `SIMULATED_RESULT` aus dem Cloud-Container, **nie ein 4P- oder 6P-Beleg, kein Qualifikationsbeleg, kein Zulassungs-Endpunkt**. XMage ist Regelautorität; Engine-Verhalten ist nur beschrieben. Branch `research/seats-7-8-1672` (nie PR gegen main), Basis `main` @ `138a50c2`, Code-Commit `8fe56af7`.

**Ergebnis:** 7 und 8 Sitze laufen technisch. **n/N = 12/12** natürlich beendet (7 Sitze 6/6, 8 Sitze 6/6), dazu Kontrollen 4/5/6 Sitze 9/9 und zwei Wiederholungen 2/2 (gesamt 23/23). Kein Abbruch, keine Fehlermeldung, keine Sitzlücke, kein Fork-Eingriff. Nötig war nur eine Java-Konstante plus acht Python-Grenzen.

## Aufbau
- **Forschungs-JAR:** `scratchpad/seats78/jar/xmage-engine-bridge-research78.jar`, SHA-256 `49eb043e5a055b06275890bb1ce8adbd754637a0c6889c714e28820ab96db8dd`, offline gebaut (`mvn -o … package -DskipTests`, 15 s), Pin `f4d12f6e80`. CRC-Vergleich mit der Vergleichs-JAR `49d18f2f…` (unverändert): nur 4 Bridge-Klassen anders (`XmageFullGameSession`, `XmageFullGameJsonlBridge`, `XmageMidgameJsonlBridge`, `XmageNativeStateRestoration`, die die Konstante einbetten); alle `mage/**`-Einträge gleich. Bridge-Tests `NOT_RUN` (z. B. `XmageFullGamePlayerCountTest.java:111` hält die 6 fest).
- **Harness:** `scripts/research/seats78_harness.py`: eigener Deck-Lader (2..8), sonst die Studio-Spielvorbereitung (`play.prepare_game`) und der Rekorder; eine Partie je JVM, kein Studio-Endpunkt berührt. Flags wie Teil B (`SerialGC`, `h2.bindAddress`, `skipForcedDecisions=true`, `-Xmx3g`), **aber ohne AppCDS** (Abweichung). RSS = `VmHWM` der Bridge-JVM aus `/proc`, CPU = JVM (Kind-Prozess).
- **Decks** (verschachtelt, Tisch A aus Teil B): A4–A6 wie Teil B; **A7 = A6 + `2023_divine_convocation`**, **A8 = A7 + `2025_temur_roar`**. Seeds 1–3 für 4–8 Sitze, zusätzlich Seeds 4–6 für 7/8. Ohne Menschensitz.
- **Last:** Fremdlast lief mit (u. a. eine weitere Bridge-JVM); loadavg beim Start 1,0–5,4. Nie mehr als ein eigenes Spiel, nie mehr als 2 JVMs.

## Messwerte (Median, Spanne; n je Zeile)
| Sitze | n | beendet | Wandzeit [s] | CPU JVM [s] | Peak-RSS JVM [MiB] | Entscheidungen | `trigger_order` je Partie | letzter Zug |
|---|---|---|---|---|---|---|---|---|
| 4 (A4) | 3 | 3/3 | 24,2 (13,9–38,0) | 39,3 | 643 (max 729) | 2.744 (1.680–4.539) | 12 (Summe 52) | 42 |
| 5 (A5) | 3 | 3/3 | 31,7 (19,4–49,0) | 57,5 | 701 (max 707) | 4.952 (2.939–5.813) | 13 (63) | 64 |
| 6 (A6) | 3 | 3/3 | 45,6 (31,6–47,1) | 73,1 | 877 (max 919) | 5.829 (4.839–5.963) | 43 (124) | 59 |
| 7 (A7) | 6 | 6/6 | 87,0 (46,1–102,3) | 106,5 | 955 (max 1.343) | 9.760 (5.970–10.801) | 43,5 (414; 15–208) | 92,5 |
| 8 (A8) | 6 | 6/6 | 98,8 (65,7–121,9) | 113,1 | 945 (max 1.006) | 10.314 (8.124–13.552) | 61 (404; 33–120) | 91,5 |

- **Kontrolle Reproduzierbarkeit über Maschinen:** A4 Seed 2/3 = 1.680/4.539 Entscheidungen (= Min/Max in Teil B), A5 Seed 1 = 4.952 (= Container-Smoke auf JAR `49d18f2f`), A6 Seed 1 = 5.963, Sieger Sitz 4 (= Teil-B-Smoke B0). Die angehobene Konstante ändert das 4–6-Sitz-Spiel also nicht.
- **Wiederholung derselben Partie (je eigene JVM):** 8-S1 und 7-S2 je 2/2 gleich: `semantic_transcript_sha256`, Entscheidungen (8.124 / 10.371), Sieger und Ausscheide-Reihenfolge identisch; Frames 4.328/4.328 bzw. 7.191/7.191 gleich, nachdem nur die Objekt-Kennungen `[xxx]` ersetzt wurden (roh unterscheiden sich nur diese). Kein #1715-Gate (keine Pool-/Mehrfach-JVM-Läufe, n = 2).
- **Sitzlücken:** keine; jeder Sitz 0..N−1 entschied und stand in `players`. 15 Entscheidungsklassen bei 7/8 (14 bei 5/6).
- **Eliminierung:** jede Partie endete mit genau N−1 `LOST`-Ereignissen und einem Sieger (7: 6/6, 8: 6/6); Sieger verteilt über Sitze 0, 1, 4, 5, 6.
- **Commander-Schaden:** in 3/12 Partien erreichte Kampfschaden eines Commanders gegen einen Spieler ≥ 21 (7-S3 Zhulodok→P6 27; 8-S1 Kasla→P5 25; 8-S5 Zhulodok→P6 21); der Spieler schied jeweils im selben Kampfschadensschritt bei Leben > 0 aus (18, 11, 10). Beobachtung aus dem Ereignislog, keine Regelprüfung.
- **Reichweite (CR 801.2):** Die Bridge setzt `RangeOfInfluence.ALL` und `MultiplayerAttackOption.MULTIPLE` (`XmageCommanderGames.java:42-43, 50-51`, `CODE_DERIVED`); begrenzte Reichweite ist nicht aktiv. Empirisch: 0 von 2.155 `declare_attacker`-Frames bei 7/8 boten weniger Optionen als lebende Gegner + 1; in 11/12 Partien wurde jeder Gegnersitz mindestens einmal angegriffen (7-S2: 6 von 7 Sitzen, Pilotwahl). Ob begrenzte Reichweite bei 7/8 überhaupt gewollt wäre: Owner/Regel-Frage, `UNKNOWN`.
- **Speicher:** höchstens 1.343 MiB (7-S1) bei `-Xmx3g`; kein OOM, kein GC-Abbruch. Pool-JVM mit mehreren Partien: `NOT_RUN`.

## Vergleich mit der Hochrechnung im Papier (`MODELED`)
- **Absolute Wandzeit nicht vergleichbar:** Container-A4 24,2 s gegen 12,91 s auf dem Owner-PC (Faktor ≈ 1,9, Fremdlast, ohne AppCDS). Die 45–51 s für 8 Sitze sind daher nicht direkt prüfbar; über das 4P-Verhältnis umgerechnet ≈ 52 s (`MODELED`, n = 3).
- **Verhältnisse zu 4 Sitzen (Mediane, Seeds 1–3, n = 3 je Sitzzahl):** 7 Sitze Wand 3,84×, CPU 2,97×, Entscheidungen 3,78×; 8 Sitze Wand 4,03×, CPU 2,89×, Entscheidungen 3,66× (Papier: Wand 2,8–3,0× / 3,4–3,9×, CPU 2,2× / 2,5–2,7×). Gemessen liegt etwas **über** der Hochrechnung, aber mit großer Streuung (paarweise 8/4 Wand 2,56–7,48×) und Fremdlast; 6/4 lag hier bei 1,89× (Teil B 2,22×).
- **Entscheidungen** sind maschinenunabhängig (siehe Kontrolle): 7 Sitze 9.760 (Papier 8.100–8.700, darüber), 8 Sitze 10.314 (Papier 10.000–11.600, darin); Maximum 13.552, weit unter der Grenze 50.000 (`full_game.py:1245`). Decks A7/A8 sind meine Wahl; Deck-Effekt nicht getrennt.

## Nötige Änderungsstellen für eine Einführung (`main` @ `138a50c2`)
- **Für einen Lauf tatsächlich nötig (hier geändert):** `engine-bridge/…/XmageFullGameSession.java:43`; `full_game.py:306, 352, 1229` (1887 prüft `lane_max == MAX_PLAYERS`, folgt mit); `full_game_batch.py:62`; `full_game_pilot/state.py:77`; `full_game_pilot/common.py:816`; `candidates/models.py:224-225`. Fehlertexte (`failure_privacy.py:85`) unverändert gelassen.
- **Für ein Produkt zusätzlich (nicht geändert):** Studio `play.py:259`, `launch.py:32` (+ Presets/Gegner `launch.py:51, 73`), `table_spec.py:35` (Wandgrenze nur 2–4), `:61, 64`, `web.py`, `paired_series.py:181`, Brett-Farben `partie.css`; `full_game_comparison.py:87` (höchstens 5 Gegner); Replay `semantic_replay/tape.py:49, 58, 98` (≤ 5); Ratschen/Tests `XmageFullGamePlayerCountTest.java:111`, `tests/unit/test_seats_5_6_part_a_1661.py:665`, `test_owner_player_cap.py` u. a.; Policy `AGENTS.md` §1, `STUDIO_SCOPE.md`, Entscheid 2026-11-08 (Owner).
- **Aufwand:** Engine-Kern klein (Schätzung ≈ 0,5 Agent-Tag inkl. Ratschen-Tests); Produkt gesamt bleibt bei der Papier-Schätzung 8–13 Agent-Tage plus Owner-PC-Messung, weil Studio, Gates, F5-Szenarien und Messkampagne den Großteil tragen. Kein Fork-Push nötig (bestätigt: Spiel läuft am Pin).

## Risiken
- **Zeit je Partie:** ≈ 4× 4P (Wand), Züge ≈ 2,2× (92 statt 42); Serien mit 98/128 Partien je Block werden teuer.
- **#1715-Determinismus:** `trigger_order` bis 208 je Partie (7-S5); das Gleichstandsrisiko wächst mit der Sitzzahl.
- **Speicher:** unkritisch in der Einzel-JVM (≤ 1,35 GiB); Pool-JVM bei 7/8 `UNKNOWN`.
- **Engine-Reichweite:** `ALL` ist Bridge-Setzung; Regelpunkte bei 7/8 (APNAP über 6 Nichtaktive, Ausscheiden mit Objekten) ohne gezielte Szenarien: `NOT_RUN`.
- **Pilot/Stichprobe:** n = 6 je Sitzzahl, ein Tisch, keine Referenz für Sitzbalance; nicht als Spielstärke-Aussage lesen.

Rohlogs und Einzel-JSONs bleiben im Scratchpad (`scratchpad/seats78/runs/`, `aggregate_runs.json`), nicht im Repo.
