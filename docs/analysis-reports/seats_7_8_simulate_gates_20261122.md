# 7 und 8 Sitze für SIMULATE: Gates zur Einführung (Refs #1672)

**Einordnung:** Gate-Läufe zum Einführungs-PR für 7/8 Sitze (Branch `feat/seats-7-8-simulate-1672`, Register E18, Owner-Anweisung 2026-11-22: „ja kümmer dich drum, dass es halt geht und führe es auch ein für die Simulationen“). Alle Zahlen sind `SIMULATED_RESULT` aus dem Cloud-Container (4 Kerne, 15 GB). Sie sind **nie ein 4P- oder 6P-Beleg, kein Qualifikationsbeleg** und kein Owner-PC-Wert. XMage ist die Regelautorität.

**Identität** (`gates_seats_7_8_simulate_20261122/IDENTITY.txt`): Lab-Stand der Läufe `6ce01abad6a9`; die Bridge-Quelle ist gleich dem PR-Head. Der Arbeitsbaum war sauber, `commander_lab.__file__` zeigt auf den Klon. BEFORE-JAR (main `3037a425`): `417342256ed0…9a89f`. AFTER-JAR: `08cad92aa3e3…e4a10`. Pin `f4d12f6e80`, OpenJDK 21.0.12.1.

## Ergebnisse

| Gate | Ergebnis (n/N) |
|---|---|
| Studio-Bridge-Gate `NEUTRAL`, Referenzsatz (echter Vierertisch, Seeds 1–36, 4 Worker, 9 Partien je JVM) | BEFORE 36/36 fertig, AFTER 36/36 fertig; semantischer Hash **36/36 gleich**, Frames **36/36 gleich** (`cmp-36.txt`) |
| AFTER mit 1 Partie je JVM, Seeds 1–6, gegen BEFORE | Hash **6/6**, Frames **6/6** gleich (`cmp-gpj1.txt`; Exit 1 nur wegen der 30 Seeds, die nur in BEFORE stehen) |
| F5-Szenarien (Bridge-Test `XmageSeatsFiveSixF5ScenarioTest`, 5 bis 8 Sitze) | AFTER **37/37** grün (21 Fälle bei 5/6, 16 bei 7/8). BEFORE: alle **16/16** Fälle bei 7/8 scheitern, die 21 Fälle bei 5/6 sind grün; der Test unterscheidet also. Der erste AFTER-Lauf scheiterte nur an APNAP bei 8 Sitzen, weil die Grenze 80 der Test-Hilfe zu klein war; mit 160 grün (`java_after_first_run_bound80.txt`). F5-3 bleibt PARTIAL, weil die bekannte Engine-Abweichung nur bei 5/6 dokumentiert ist |
| Bridge-Tests PlayerCount (2..8 gehen durch, 9 nicht; Mid-game-Lane 2..6) und ContractTruth | 9/9 und 2/2 |
| Determinismus 7 Sitze (Tisch A7, Seeds 1–8, jede Partie in eigener JVM gegen 8 Partien je JVM auf- und absteigend) | 24/24 Partien beendet. Gegen `up` und gegen `down`: Status, Transkript, Sieger, Entscheidungen, Frame-Zahl und normalisierter Frame-Digest je **8/8** gleich |
| Determinismus 8 Sitze (Tisch A8, gleiche Methode) | 24/24 Partien beendet. Transkript, Sieger, Entscheidungen und Frame-Zahl je **8/8** gleich; normalisierter Frame-Digest **7/8** gegen `up` und **7/8** gegen `down` |
| Echt-Engine-Smoke über den Studio-Serienpfad (`compare-decks`, 2 Paare je Tisch, Tisch `precon` A7/A8) | 7 Sitze: 4/4 Partien beendet, 0 gescheitert. 8 Sitze: 4/4 beendet, 0 gescheitert. `series_table_check` = (7 bzw. 8, `consistent`), also Evidenzzeile „Tisch mit 7/8 Sitzen“. Ausgabe trägt `BRIDGE_AHEAD_OF_QUALIFICATION` |
| PLAY-Echt-Engine-Tests (`test_human_seat_play_1169.py` mit AFTER-JAR) | **100/100** grün, 0 übersprungen (PLAY 5/6 unverändert) |

**Befund 8 Sitze, Seed 7 (`LOCAL_OBSERVED`, Ursache UNKNOWN):** Die Abweichung steht in 2 von 7.238 Frames, erstmals in Frame 1.286 (Zug 31, `choose_use` „Move Bello, Bard of the Brambles … to the command zone …?“). In `players[3].graveyard` stehen dieselben Karten in anderer Reihenfolge. Alle drei Läufe (einzeln, `up`, `down`) weichen paarweise voneinander ab. Das ist also ein Effekt von Lauf zu Lauf, nicht vom Stapeln (Batching). Transkript, Entscheidungen und Sieger sind in allen Läufen gleich. Bei 6 Sitzen gab es einen ähnlichen Befund (Seed 4, Schadensmarker, E16 Nr. 6). Das Owner-Wort dort deckt nur 6 Sitze. Nichts ist umklassifiziert (Register, Entscheide 2026-11-20/21 Nr. 2). Ob Bedingung (a) bei 8 Sitzen als erfüllt gilt, entscheidet der Owner.

**Speicher und Zeit** (`det78_summary.json`, parallel mit Fremdlast, nicht mit dem Owner-PC vergleichbar):

| Sitze | Einzel-JVM: Wand Median (min–max) | Peak-RSS Median / max | 8 Partien je JVM: Peak-RSS up / down |
|---|---|---|---|
| 7 | 114,4 s (74,1–140,9), n = 8 | 891 / 1.132 MiB | 1.231 / 883 MiB |
| 8 | 143,8 s (83,9–189,0), n = 8 | 909 / 1.181 MiB | 1.255 / 1.255 MiB |

Speicher bei 16 Partien je JVM (Studio-Standard): UNKNOWN (n = 0).

**Mutationen** (`mutate.out`, eigener Worktree am Stand `6ce01aba`): **22/22** getötet. M13 (Tischprüfung `deck_series` zurück auf 2..6) überlebte zuerst. Danach wurde der Test um die Herkunft „aus Plan und gespielten Partien“ geschärft, und der Nachlauf tötete M13. Abgedeckt sind: beide Sperren und die Rücknahme auf 6, die Code-Obergrenze, die Partie-Grenze, Runner und Handshake (nur 8, oder auch 7), Policy, Bindung, Szenario-Modell, Planer-Basis, die Sperrzeile der Seite, ein gekürztes Preset, die Wandgrenze bei 7 Sitzen (der Pool würde sich öffnen), die Java-Konstante, der Spiegel der Referenzwerte, `load_decks`, `DeckComparisonSpec` und der Dauer-Hinweis.

## Nicht gelaufen (NOT_RUN / UNKNOWN)

- Konformanz und Qualifikations-Lane bei 7/8 (Tabelle bleibt 2..6). Replay-Tape bei 7/8 (Modell höchstens 5). Serien-Pool bei 7/8 (abgewiesen).
- Volle Bridge-Testsuite lokal. PB-03 läuft nur in der CI (`NOT_SEALED` ≠ PASS).
- Presets `mixed` und `optimized` bei 7/8. Dauer auf dem Owner-PC. Sitzbalance und Pilotgültigkeit bei 7/8.
- `tests/unit/test_packaging_smoke.py` lokal: Umgebungsfehler (lokales setuptools lehnt `project.license` ab); `pyproject.toml` ist unverändert.

Rohlogs und Partie-Logs bleiben im Scratchpad. Hier liegen nur die Vergleichs-JSONs, die Messdateien je Lauf, die Skripte und die Test-Zusammenfassungen.
