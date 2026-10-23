# M4 — Endbericht: Deck-Verbesserung RogShai & Chulane (Schritte 0–4)

Quelle: Muse (Mess-Lane), 2026-10-23. Auftrag M4 inkl. Nachtrag 1 und 2;
Abnahmeliste Issue #976. Alle Zahlen LOCAL_OBSERVED, sofern nicht anders
gekennzeichnet. **Source Lock der Spiele: Lab `d48bbe5f2`, Pin v11, JAR
sha256 `69aa31eb…`** (unverändert seit Schritt 0; Prefilter nach #968 auf
`981a4f8f7`, siehe PREFILTER-968.md). Main ist inzwischen bei Repin v13
(Pin `90f5c4d3f8`, versiegelt) — für diese Messreihe ohne Wirkung; die
Batching-Methode (`--games-per-jvm` 6 bzw. 3) wurde durch PR #974
nachträglich qualifiziert (184 Vergleiche, 0 Abweichungen).

## Owner-Zusammenfassung

**Alle sechs Bündel sind UNDECIDED — kein Bündel ist entschieden besser oder
schlechter; die Messung hätte Effekte ab etwa 3,4–4,8 Prozentpunkten sehen
können, alle Punktschätzer liegen zwischen −5,0 und ±0,0 Punkten.** Fünf der
sechs Bündel enden mit Effekt exakt ±0,000; nur das RogShai-Kurven-Bündel
R-C zeigt einen negativen Punktschätzer (−0,050, p = 0,064, nicht
signifikant). Einzig belastbare Warnung: Das Manabasis-Bündel R-A senkt den
Ishai-Cast-Anteil von 94,5 % auf 87,5 %, ohne die Siege zu bewegen. Für
kleinere Effekte als ~4 Punkte wären je Bündel grob 600–1 100 Paare nötig
(MODELED) oder eine andere Metrik (Finishing Order, #875/S-1) — ohne neuen
Auftrag messe ich keine weiteren Bündel.

## 1. Ergebnis je Bündel (200 Paare, Seeds 1–50, Tisch wie Schritt 2)

Gepaarter Effekt = (Varianten-Siege − Baseline-Siege) / Paare; 95 %-KI als
Normalapproximation über die diskordanten Paare (halbe Breite
1,96 · √diskordant / Paare); Verdikt-Regel: Sign-Test p < 0,05.

### RogShai (Baseline: 35/200 Siege = 17,5 %, Ø 47,5 Züge, Mulligan 36,5 %)

| Bündel | Siege V:B | Disk. | Effekt | 95 %-KI | p | Verdikt |
|---|---|---|---|---|---|---|
| R-A Manabasis | 35:35 | 22 | +0,000 | [−0,046, +0,046] | 1,000 | UNDECIDED, sichtbar ab 4,6 Pkt. |
| R-B schwächste nicht-reaktive | 35:35 | 12 | +0,000 | [−0,034, +0,034] | 1,000 | UNDECIDED, sichtbar ab 3,4 Pkt. |
| R-C Kurve | 25:35 | 24 | −0,050 | [−0,098, −0,002] | 0,064 | UNDECIDED, sichtbar ab 4,8 Pkt. |

### Chulane (Baseline: 19/200 Siege = 9,5 %, Ø 48,2 Züge, Mulligan 35,0 %)

| Bündel | Siege V:B | Disk. | Effekt | 95 %-KI | p | Verdikt |
|---|---|---|---|---|---|---|
| C-A Manabasis | 19:19 | 16 | +0,000 | [−0,039, +0,039] | 1,000 | UNDECIDED, sichtbar ab 3,9 Pkt. |
| C-B schwächste nicht-reaktive | 19:19 | 16 | +0,000 | [−0,039, +0,039] | 1,000 | UNDECIDED, sichtbar ab 3,9 Pkt. |
| C-C Kurve | 14:19 | 19 | −0,025 | [−0,068, +0,018] | 0,359 | UNDECIDED, sichtbar ab 4,3 Pkt. |

Jedes Bündel hätte einen 5-Punkte-Effekt sehen können (halbe KI-Breiten
3,4–4,8 Punkte). Kein „besser" oder „schlechter" ohne Intervall: R-Cs
Intervall liegt zwar unter null, der Sign-Test (p = 0,064) entscheidet aber
nicht — das ist ein negativer Hinweis, kein Befund.

### Nebenkennzahlen (ohne Urteil, Nachtrag 1 §2.5)

- Kommandanten-Cast-Anteil: RogShai — Rograkh 100 % in allen Armen; Ishai:
  Baseline 94,5 %, **R-A 87,5 % (Warnung, s. u.)**, R-B 94,0 %, R-C 95,5 %.
  Chulane: Baseline 88,0 %, C-A 90,5 %, C-B 87,0 %, C-C 86,5 %.
- Mulligan-Spiele: RogShai 36,5 % (Baseline) / 36,5 / 36,0 / 35,5 %;
  Chulane 35,0 % / 31,5 / 35,0 / 34,0 %.
- Ø Züge: RogShai 47,5 / 46,7 / 47,9 / 48,4; Chulane 48,2 / 47,9 / 48,0 / 48,0.
- **Zug des ersten Kommandanten-Casts: UNKNOWN.** Die Entscheidungs-Events
  der Transkripte tragen kein Zug-Feld (nur eine laufende `sequence`);
  spielweit existiert nur die End-Zugzahl. Beide Mess-Lanes nutzen dasselbe
  Transkript-Schema, die Kennzahl ist daraus nicht ableitbar
  (CODE_DERIVED aus 1 600 geprüften Records).

**Warnung R-A (kein Ergebnis):** Das Manabasis-Bündel tauscht bewusst Weiß
gegen Tempo (Prefilter: Ishai T4 play 0,589 → 0,536). In den Spielen fällt
der Ishai-Cast-Anteil um 7 Punkte (94,5 % → 87,5 %), während die Siege
gleich bleiben. Wer R-A trotzdem spielen will, kauft den Tausch mit dieser
Sichtbarkeit; ein Erfolgs- oder Misserfolgsbeweis ist das nicht.
Nach Nachtrag 2 §2 wird R-A bei diesem Ausgang **nicht** in Einzeltausche
zerlegt (dieselbe Nachweisgrenzen-Lücke), und kein anderes Bündel wird
zerlegt, weil keines entschieden besser ist.

**Lesart R-B (Nachtrag 2 §2):** Effekt exakt ±0,000 bei nur 12 diskordanten
Paaren — die Sortierregel „niedriger Spielanteil" hat hier keine schwachen
Karten gefunden; das stützt die Regel-Kritik („Spielanteil ist kein
Kartenwert"), es widerlegt sie nicht und es adelt die getauschten Karten
nicht.

## 2. Paar-Bilanz und Retry-Buchhaltung (#976 Punkt 1)

- Geplant: 200 Paare je Bündel (50 Seeds × 4 Sitze), analysiert: **200/200
  bei allen sechs Bündeln; gestrichene Paare: 0.** Kein Paar wurde je als
  Niederlage gezählt, weil ein Arm fehlte.
- BRIDGE_TIMEOUT-Fälle (alle Klasse `protocol`, Last-Artefakte, keine
  Engine-Fehler): RogShai Spitzenstand 48 fehlgeschlagene Fälle (Seed-Blöcke
  32/33) — 47 im ersten Retry-Zyklus abgeschlossen, der letzte
  (R-C, Seed 31, Sitz 4) im finalen Retry → **48/48 nachgeholt**.
  Chulane: 22 Timeout-Fälle über den Verlauf (2 aus Seed 16, 20 aus dem
  Scheiben-Fenster Seeds 39–41) — alle in Retries abgeschlossen → **22/22**.
  Endstand beider Läufe: 800/800 Spiele abgeschlossen, 0 fehlgeschlagen.
- Konsistenz: Die Schritt-4-Baselines (17,5 % / 9,5 % über 200 Spiele)
  passen zu Schritt 2 (17 % / 8 % über je 100, Seeds 1–25-Teilmenge).

## 3. Scheiben-Integrität (#976 Punkt 2)

Die Läufe ab Seed ~31 (RogShai) bzw. den Resten (Chulane) liefen als
getrennte Prozesse in Seed-Scheiben (Grund: Punkt 5).
(a) Jedes (Seed, Sitz) kommt in der Auswertung je Arm **genau einmal** vor
(200 je Arm, 800 je Deck — aus den Aggregaten nachrechenbar). Durch
Scheiben-Neustarts entstanden doppelte Records für 15 (RogShai) bzw. 100
(Chulane) Fälle; alle **115/115 Duplikate sind ergebnisgleich** (Sieger,
Züge, Mulligan, Kommandanten-Casts identisch).
(b) Alle Scheiben liefen auf demselben Lock und denselben Dateien
(sha256): JAR `69aa31ebf15dc47c…`, RogShai-Deck `c3061ede866c6b44…`,
Chulane-Deck `06665cd0e686154c…`, Bündel R-A `307e75fd07fa398e…`,
R-B `ee46dc91d4dc835e…`, R-C `4900efa37902824a…`, C-A `4c1b84e87be228d8…`,
C-B `683512c241399af55…`, C-C `727e7544eef82906…`; Gegner (Repo-Stand am
Lock): Doom Prevails `3c090f7916413384…`, Elven Empire `bdd15857b48c66f2…`,
Painbow `01fcd6e895364778…`.
(c) Slot-Alignment: Das Comparison-Report-Schema führt `identical_pairs`
(ein Feld `slot_alignment` existiert nicht). Werte der letzten
Runner-Reports (Retry-Scheiben): RogShai 34/24/29, Chulane 14/24/24
identische Paare — zusammen mit den 115/115 gleichen Duplikaten ist die
Paar-Ausrichtung über alle Scheiben belegt.

## 4. Sammlung, Tisch, Grenzen

- **Sammlungs-Endprüfung (Nachtrag 2):** `sammlung-2026-09-19-flach.txt`
  am 2026-10-22 erhalten (1 399 Karten / 2 046 Exemplare). Alle 20
  Bündel-Neukarten frei ≥ 1 nach der maßgeblichen Datei, **null
  Abweichungen** zu den vorläufigen Werten; Claudes Referenzwerte
  (Faerie Mastermind 0, Glacial Fortress 0, Azorius Signet 1) exakt
  reproduziert. Frei-0-Ausschlüsse gesamt: diese 3 Karten.
- **Tisch-Sensitivität (§2.6): gegenstandslos.** Sie gilt dem besten
  Bündel je Deck an einem zweiten Tisch; kein Bündel ist entschieden
  besser (oder überhaupt entschieden). Einen UNDECIDED-Spitzenreiter an
  einem zweiten Tisch zu messen, würde Rauschen vermessen. Die drei
  READY-Listen für einen solchen Lauf wären aus dem Precon-Pool zu
  wählen, sobald ein Bündel je entschieden ist.
- Tisch-Vorbehalt wie in Schritt 2: Zwei der drei Gegnerlisten sind
  Ersatzlisten (Elven Empire, Painbow, beide NOT READY) — absolute
  Quoten verzerrt, gepaarte Vergleiche am selben Tisch sind die Aussage.
- Keine Eingriffe in `data/**`, kein Pilot-Fix, kein Fork-Push.
  Farmland-Befund (Pilot cykelt statt zu spielen) steht in
  ZWISCHENBERICHT2.md und ist Claudes Prüf-Lane, nicht Teil dieses Berichts.

## 5. Werkzeug-Befunde (#976 Punkt 5)

1. **Exit-Code-Fehler (eigener Befund, offengelegt):** Mein erstes
   Supervisor-Skript las `$?` in derselben Zeile nach einer
   Command-Substitution — alle „ENDE rc=0"-Zeilen der Nacht waren dadurch
   nichtig; getötete Läufe sahen wie Abschlüsse aus. Korrigiertes Skript
   liegt bei (`run_supervisor_fixed.sh`: `pipefail`, rc auf eigener
   Zeile, Scheiben-Strategie).
2. **Speicherbefund (Tool-Finding):** Der Vergleichsprozess hält alle
   Records im RAM (`run_sequential_blocks` akkumuliert + aggregiert je
   Look neu): gemessen **5,25 GB RSS bei 495 Records**; mit 2 JVM-Workern
   auf der 7-GB-Box wurde der Prozess wiederholt gekillt. Gegenmaßnahme
   war die Scheiben-Strategie (eigener Prozess je 9–12 Seeds, workers 1).
   Ursachencode liegt in `scripts/run_full_game_deck_comparison.py` /
   `full_game_comparison.py` (CODE_DERIVED). Einen separaten Issue-Text
   dazu lege ich in Anhang A bei — anlegen kann ich ihn mit dem mir
   verfügbaren GitHub-Werkzeug nicht (kein create_issue); bitte per
   Klick übernehmen.

## 6. Prüfbarkeit (#976 Punkt 6 + Abnahme)

- Aggregate: `aggregate_rogshai.json`, `aggregate_chulane.json`
  (Paar-Zählungen, Siege, Diskordante, Nebenkennzahlen-Summen).
- Reproduktion: `reproduce_step4.py` liest nur die Aggregate und gibt
  Effekt, Intervall, Sign-Test und Verdikt je Bündel aus — alle Zahlen
  dieses Berichts entstehen so. Testkommando:
  `python reproduce_step4.py aggregate_rogshai.json aggregate_chulane.json`
  (Python 3.12, keine Engine nötig).
- **Manipulations-Test (gelaufen):** In einer Kopie des RogShai-Aggregats
  wurde ein Wert geändert (R-A: variant_wins 35 → 36, diskordant 22 → 23).
  Die Skript-Ausgabe ändert sich nachweislich: Effekt +0,000 → +0,005,
  KI [−0,046, +0,046] → [−0,042, +0,052], X 4,6 → 4,7. Eine Prüfung, die
  nicht fehlschlagen kann, ist damit ausgeschlossen.
- Roh-Transkripte (1 600 Records, GB-Größenordnung) bleiben lokal
  archiviert wie bei M3. Hash-Liste der Record-Dateien auf Anfrage;
  Einzel-Records reiche ich auf Verlangen nach.

## Anhang A — Issue-Text (Speicherbefund, bitte anlegen)

Titel: `run_full_game_deck_comparison.py: sequential runner holds all records in memory (~5 GB at 800 games), killed on 7 GB hosts`

Body: „During the M4 bundle runs (200 pairs × 4 contenders = 800 games,
seeds 1–50, --stop-when-decided --look-every 5), the comparison process
reached 5.25 GB RSS at 495 persisted records and was OOM-killed repeatedly
on a 7 GB box (2 workers). Cause (code-derived): run_sequential_blocks
accumulates every block's records and re-aggregates the combined report
at each look; the batch layer likewise materialises all records.
Workaround used: seed slices of 9–12 seeds per process, workers 1.
Measured on lab d48bbe5f2, pin v11. Suggested direction: stream records
to the aggregator per block instead of accumulating parsed payloads, or
cap the in-memory set to per-case outcomes for completed blocks."
