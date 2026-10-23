# M4 Schritt 4 — Zwischenstand (2026-10-23, 09:40 CEST)

Quelle: Muse (Mess-Lane). Status: **ZWISCHENSTAND, keine Endwerte.** Source Lock
unverändert: Spiele auf Lab `d48bbe5f2`, Pin v11, JAR `69aa31eb`. Main ist inzwischen
bei Repin v12 + PR #970 + PR #974; für diese Läufe ohne Wirkung (Lock gilt).
Batching (`--games-per-jvm` 6, in den Restscheiben 3) ist durch PR #974 nachträglich
qualifiziert: 184 Vergleiche gegen Einzelspiel-Hashes, 0 Abweichungen; das dort
gefundene Bridge-Speicherleck (~1,6 MiB/Spiel in einer JVM) ist bei Batchgrößen
3–6 harmlos (EXTERNAL, Claudes Qualifikation auf v12).

## Methoden-Korrektur zur Stop-Regel (wichtig für die Gegenprüfung)

`--stop-when-decided` stoppt **nur**, wenn jede Variante per Sign-Test
(per-Look-α = 0,005) VARIANT_BETTER oder BASELINE_BETTER ist
(`sequential_look_decided` in `full_game_comparison.py`, CODE_DERIVED).
NO_CLEAR_DIFFERENCE / INSUFFICIENT stoppen nie. Die Läufe gehen daher über
die vollen Seeds 1–50 (200 Paare je Bündel). Frühere „ENDE rc=0"-Zeilen meines
Supervisor-Skripts waren durch einen Bash-Fehler (`$?` nach Command-Substitution)
wertlos; der Vergleichsprozess wurde bei großen Läufen wiederholt speicherbedingt
gekillt (er hält alle Records im RAM). Die Restspiele laufen deshalb in
Seed-Scheiben (eigener Prozess je Scheibe, workers 1, games-per-jvm 3).

## RogShai — Zwischenstand bei 124 Paaren (LOCAL_OBSERVED)

Auswertung: Streaming-Aggregation über die Game-Records, Paarung über (Seed, Sitz),
Effekt = mittlere Paar-Differenz der Siege, 95 %-KI Normalapproximation,
Urteil gegen die Nachweisgrenze ±0,125 aus Nachtrag 1.

| Arm | Spiele | Siege | Ø Züge | Mulligan | Ishai gewirkt | Rograkh gewirkt |
|---|---|---|---|---|---|---|
| Baseline | 124 | 20 (16,1 %) | 47,0 | 37 % | 95 % | 100 % |
| R-A Manabasis | 124 | 21 (16,9 %) | 46,4 | 37 % | **86 %** | 100 % |
| R-B schwächste nicht-reaktive | 124 | 20 (16,1 %) | 47,1 | 37 % | 94 % | 100 % |
| R-C Kurve | 123 | 18 (14,6 %) | 47,7 | 37 % | 95 % | 100 % |

- R-A: Effekt **+0,008** [−0,049, +0,065], diskordant 13 → UNDECIDED
- R-B: Effekt **+0,000** [−0,045, +0,045], diskordant 8 → UNDECIDED
- R-C: Effekt **−0,016** [−0,076, +0,044], diskordant 14 → UNDECIDED

Nebenkennzahl ohne Urteil: R-A senkt den Ishai-Cast-Anteil von 95 % auf 86 %
(Weiß-Verlust des Bündels; vgl. Prefilter Ishai T4 play 0,589 → 0,536).

## Chulane — Zwischenstand bei 115 Paaren (LOCAL_OBSERVED)

| Arm | Spiele | Siege | Ø Züge | Mulligan | Chulane gewirkt |
|---|---|---|---|---|---|
| Baseline | 115 | 9 (7,8 %) | 47,8 | 33 % | 89 % |
| C-A Manabasis | 115 | 12 (10,4 %) | 47,4 | 31 % | 91 % |
| C-B schwächste nicht-reaktive | 114 | 8 (7,0 %) | 47,4 | 33 % | 88 % |
| C-C Kurve | 114 | 7 (6,1 %) | 47,6 | 32 % | 89 % |

- C-A: Effekt **+0,026** [−0,025, +0,077] → UNDECIDED
- C-B: Effekt **−0,009** [−0,066, +0,048] → UNDECIDED
- C-C: Effekt **−0,018** [−0,077, +0,042] → UNDECIDED

Kreuzprobe: Der Runner-eigene Report bei 62 Paaren liegt als
`runner_report_chulane_62paare.json` bei (C-A dort +0,06, INSUFFICIENT, p = 0,219;
C-B +0,03, p = 0,688 — gleiche Lesart: nichts entschieden).

## Laufstatus

- RogShai: 549/800 abgeschlossen, 48 BRIDGE_TIMEOUT (Seed-Blöcke 32/33 aus einer
  überlasteten Phase; Retry-Scheibe fährt sie solo nach), Rest in Scheiben 33–50.
- Chulane: 458/800 abgeschlossen, 0 fehlgeschlagen; Rest in Scheiben 16–50.
- Rohrecords (GB-Größenordnung, Transkripte) bleiben lokal archiviert wie bei M3;
  Aggregate und dieser Stand sind die prüfbare Ablage. Hash-Listen auf Anfrage.
