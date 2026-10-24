# Max-Review — 02_BEFUNDE.md (Pass B: Fehler und Lücken, nach Schwere)

Stand: Lab-main `ee47312a7`, Engine-Pin `90f5c4d3f8`. Schwere: hoch = falsches Verhalten oder
falsche Zahl in einem Artefakt, das Entscheidungen trägt; mittel = Kontrolle beweist weniger als
behauptet, oder Wartungs-/Verständnisrisiko mit konkretem Beleg; niedrig = Doku-/Prozess-Unschärfe
ohne Verhaltensfolge; Info = zur Kenntnis, kein Handlungsbedarf. Alles, was nicht ausdrücklich als
von Muse gemessen markiert ist, ist ein Lese-/PR-Body-Befund, keine Laufzeit-Verifikation.
„Body:" = Behauptung aus dem PR-Body, keine Verifikation.

## Hoch

Keine Befunde der Stufe hoch aus Pass A/B. (Die in Spielen gefundenen Regel-/Pilotfehler der
Vergangenheit — Abbrüche, Endlosschleifen, falsche Ziele — sind in den gemergten PRs #743–#1006
adressiert; ob sie in aktuellen Spielen noch auftreten, misst die laufende Abort-Kette, s. unten.)

## Mittel

### B-01 — #914 behauptet falsche Importzahlen, #924 korrigiert sie (Doku trägt falsche Zahl)
#914: 192/195 Decks OK, 0 fehlende Karten. #924 (Nachfolger, gleiche Messung, Pin 043579bb):
182/195, 13 Decks durch 31 engine-unbekannte Namen blockiert; #924 räumt zusätzlich unvedrahtete
Scores (toter Code) in #914 ein. Wer nur #914 liest, liest falsche Zahlen. Beleg: Tabellenzeilen
#914/#924 in `01_PR_PRUEFUNG.md` (PR-Body + Git-Diff). Folge: #914-Body sollte einen Korrektur-
vermerk tragen (kein Rewrite — Historie bleibt), damit niemand die 192/195 zitiert.

### B-02 — `tests/conftest.py:73` macht 41 Tests grün, ohne dass Dirty-State je geprüft wird
`clean_tracked_worktree` (session-autouse) patcht Dirty-Worktree-Prüfungen auf „sauber"; 41 ehemals
failing Tests laufen dadurch grün. Nur das `real_worktree_checks`-Fixture (`:112`) erreicht echte
Prüfungen. Beleg: Pass A, Bereich 4 (Code-Befund, Laufzeit NICHT GEPRÜFT). Das ist die stärkste
„Kontrolle aus dem falschen Grund" im Repo: Die grüne Suite beweist für diese 41 Tests nicht, dass
Dirty-State korrekt behandelt wird. Vorschlag: Die 41 Tests in `03_VERBESSERUNGEN.md` als eigene
Verbesserung (entweder echte Prüfung oder ehrliche Markierung als „setzt sauberen Worktree voraus").

### B-03 — Fake-Bridge-Fixture behauptet `external_rules_engine`-Niveau
`tests/fixtures/fake_external_engine_bridge.py:27` meldet `engine_version: "fixture-not-real"`,
behauptet aber `validation_level: external_rules_engine`. Ein Protokoll-Test dagegen beweist nichts
über die echte Engine. Eingrenzung (beruhigend): einziger Importeur ist
`tests/contract/test_phase85_protocol.py:52`. Beleg: Pass A, Bereich 4. Vorschlag: Fixture-Level auf
einen ehrlichen Wert (`fixture`) ändern oder den Test als Protokoll-Test labeln.

### B-04 — Falsche-Grund-Kontrolle Nr. 3: Receipt-Test mit gefaktem Maven
`tests/qualification/test_current_boundary_native_suite_receipt.py:9` läuft „end to end with a faked
Maven process" und beweist nur den Receipt-Pfad, nicht den Engine-Lauf. Beleg: Pass A, Bereich 4.
Zusammen mit B-02/B-03: Drei Stellen, an denen die Suite weniger beweist als ihr Name verspricht —
keine davon ist ein Laufzeitfehler, alle drei sind Ehrlichkeitslücken im Test-Narrativ.

### B-05 — Zahlungsabbrüche: alte Hypothese WIDERLEGT, neuer Befund (gemessen 2026-10-25)

Auftragszahl: In den 24 Spielen von #1006 enden 136 von 3.599 Zahlungen mit „Cancel mana payment".
**Baseline neu gemessen (Max-Review, 24 Real-Pod-Seeds, Main ee47312a7 + Pin v13, Jar
`0fda80ec…5fddb9`, Daten `~/workspace/tmp/max-review/abort24/`): 135 abgebrochene Casts bei
85.982 Entscheidungen = 1,57/1000 — praktisch identisch mit der Phase-4b-Messung (134, 1,60/1000).
Main mit Phase 1/3a hat die Rate nicht verändert.**
**Ursachen-Klassifikation (Detektor `abort_context.py`, Zählregel: je rohem Cancel die
angebotenen Labels gegen die Restkosten aus dem Prompt geprüft — generisch akzeptiert jede
Farbe, farbig nur die exakte Farbe): 136 rohe Cancels, davon 92 mit nur „Cancel mana payment"
als Option und 44 mit nur nicht-zahlenden Alternativen (Pool-Mana in Farben, die das
verbleibende farbige Symbol nicht bezahlen) — 136/136 erzwungen, 0 echte Wahlen.**
Muster am Beispiel Bitter Downfall (32 Cancels, alle erzwungen): Pilot startet den Cast,
bezahlt 1–3 Mana, dann keine angebotene Quelle mehr bei Rest {1}–{3} — der Cast war zur
Zahlungszeit absolut unterdeckt, keine Sequenzierungsfrage. Die alte Hypothese (Filterländer +
eingeschränktes Any-Color als Hauptursachen) ist damit **widerlegt**: Die Dead Ends sind
Mana-Unterdeckung (Menge und/oder Farbe), keine Restriktionen.
**Offen (Code-Analyse, kein Transkript-Befund):** Wo die Unterdeckung entsteht — Pilot-
Schätzung der Bezahlbarkeit zur Cast-Wahl vs. Engine-`getPlayable`-Überschätzung. Das ist
R-01 Item 2, nicht Teil dieser Messung. Nebenbefunde: Ketten-Abbrüche (≥1 Kicker) 12,
Kette ≥2: 0 (Phase-4b-Fix hält); X=0 nur 1/30 (Fähigkeit, legitim); pay-any-amount 0 Fragen
im Real-Pod (erwartet).

## Niedrig

### B-06 — #888 trägt „Not merged per policy" im Body, ist aber gemergt
Widerspruch zwischen Body-Vermerk und Listenstatus, ungeklärt. Beleg: Tabellenzeile #888.
Folge: keinerlei Verhaltensfolge; nur ein Fall für die „Body lügt nie, aber manchmal widerspricht er
sich"-Liste. Klärung: ein Satz im Issue #888-Thread oder Body-Ergänzung.

### B-07 — #911 und #912 tragen [DRAFT] im Titel trotz Merge
Reine Titelhygiene; beide PRs sind gemergt und in der Tabelle geführt. Beleg: Tabellenzeilen
#911/#912. Folge: keine, außer dass Titel-Suchen nach Drafts diese PRs fälschlich treffen.

### B-08 — #827: Workflow-Datei musste per Web-UI übernommen werden, Zeitpunkt unbelegt
Body warnt selbst: Die zentrale Workflow-Datei konnte per API nicht gepusht werden (fehlende
Workflows-Berechtigung) und musste per Web-UI übernommen werden — ob das vor dem Merge geschah,
ist aus dem Body nicht belegt. Beleg: Tabellenzeile #827. Folge: Falls die Datei erst nach dem Merge
landete, war der gemergte Stand kurzzeitig anders als geprüft. Klärung nur über Workflow-Historie
möglich (NICHT GEPRÜFT).

### B-09 — #939: 2 fehlgeschlagene Tests im Full Suite ohne Einordnung
Body nennt 2 fehlgeschlagene Tests (Rest 5.563 passed) ohne deren Einordnung. Beleg: Tabellenzeile
#939. Folge: keine, solange die 2 Tests als bekannt-flaky dokumentiert sind — das ist aus dem Body
nicht ersichtlich. Klärung: Testnamen + Grund in einem Satz.

### B-10 — #949/#950: je ein Abbruch bleibt als Engine-Problem offen
Encore-Schleife (Seed 16) und Seed-20-Abbruch sind laut Body Engine-Probleme, im Piloten nicht
lösbar bzw. gar nicht behoben. Beleg: Tabellenzeilen #949/#950. Folge: Diese Abbrüche können in
aktuellen Sweeps weiterhin auftreten; sie gehören in die bekannte Restliste (und in die Abort-
Ketten-Auswertung als mögliche „sonstige"-Ursache).

### B-11 — #899/#895: Owner-Entscheidungen laut Body offen
Evidence-Lanes (Schritt 3 Vergleichs-Runner) bzw. Schritt 3 für den Vergleichs-Runner bleiben laut
Body Owner-Entscheidung. Beleg: Tabellenzeilen #899/#895. Folge: keine akute; die Punkte gehören in
die offene-Entscheidungen-Liste, nicht in Vergessenheit.

### B-12 — HANDOFF-Dokument veraltet (selbst als veraltbar markiert)
`docs/claude/state/HANDOFF.md:8,18-19` nennt Lab-Stand `129ff155`,
`docs/performance/REFERENCE_36_SEEDS_2026-10-24.md:34` nennt `053708e56` (main nach #1004), gleicher
Pin `90f5c4d3f8`. Das Dokument warnt selbst (`HANDOFF.md:4`, „regenerate", „Git wins") — Veraltung,
kein Policy-Widerspruch. Ob `129ff155` vor/nach `053708e56` liegt, wurde nicht per Git-Log geprüft.
Beleg: Pass A, Bereich 1. Folge: niedrig, weil das Dokument seine eigene Veraltung ankündigt; trotzdem
ist ein regeneriertes HANDOFF auf Stand ee47312a7 fällig (H-1-Mechanik aus #973 existiert).

## Info (kein Handlungsbedarf, aber festgehalten)

### B-13 — Sonderbefund #1003: gemergter Stand = verifizierter Stand + 3 Annotationszeilen (VERIFIZIERT)
- `4ac422597` (merged head laut API) ist in keinem lokalen Clone ein gültiges Objekt (`git cat-file -t`
  in `commander-playtest-lab` und `wt-phase4b` je `fatal: Not a valid object name`). Der Blob-Diff
  3401cb0b vs. 4ac422597 ist damit lokal nicht durchführbar.
- Ersatzvergleich, selbst ausgeführt: verifizierter Pre-Merge-Head `3401cb0b` (Clone `wt-phase4b`, HEAD
  bestätigt) vs. Squash-Commit auf main `c0e5f7f1` (Subjekt endet mit `(#1003)`, 4 Dateien identisch
  zur PR-Dateiliste). Ergebnis: `choices.py` exakt 2 geänderte Zeilen (Z. 638, Z. 658, je `Any`→`object`
  in Annotationen), `payment.py` exakt 1 geänderte Zeile (Z. 1126, `Any`→`object` in Annotationen),
  `priority.py` identisch, Testdatei identisch; alle Zeilenzahlen gleich (874/1320/364/180). Beide
  Python-Dateien enthalten `from __future__ import annotations` — Annotationen sind zur Laufzeit
  Strings, die Änderung hat daher kein Laufzeitverhalten (CODE_DERIVED, kein Messwert).
- Abschluss: 9 Unit-Tests aus `tests/unit/test_pilot_x_and_pay_amount.py` gegen Main ee47312a7
  (Worktree wt-maxreview) ausgeführt: **9 passed in 0.74 s**. #1003 gilt damit als VERIFIZIERT:
  Spiele an 3401cb0b + Tests am gemergten Stand + Diff = 3 Annotationszeilen ohne Laufzeitverhalten.
- Brücke (ehrlich): Dass `4ac422597` denselben Baum trägt wie der Squash `c0e5f7f1`, folgt nur aus
  Standard-Squash-Semantik, nicht aus lokalem Objektvergleich.

### B-14 — Klärung #978: Issue, kein PR (korrekt keine Tabellenzeile)
`GET /repos/moeendres-png/commander-playtest-lab/pulls/978` liefert HTTP 404 — #978 ist kein PR,
sondern ein Issue (wie #999/#1001). Die Verifikation „Precon-Import 9/9, Pod-Sweep 8/8, Bericht
Commit 469faaf2" steht als Berichts-Fakt, nicht als PR-Zeile; in der Tabelle fehlt #978 zurecht.

### B-15 — Test-Schieflage (Zählung, keine Wertung)
Unit 2260 + Qualifikation 1580 Definitionen gegen Integration 40, Golden 8, Property 8, Fuzz 5,
Mutation 3 (gezählt, nicht ausgeführt). `config/evals.yaml:6` erlaubt Golden sogar 0,95 statt 1,0.
15 Repin-Dateien sind per Design stillgelegt (`superseded_by_later_repin`-Skip, gezählt per
`grep -rln superseded_by_later_repin`) — kein toter Test im engen Sinn, aber Pin-Assertions
verschwinden mit dem nächsten Pin aus der Suite. 80 von 99 Python-Skripten ohne namensgleiche
Testdatei (grobe Heuristik, NICHT GEPRÜFT auf indirekte Abdeckung). Beleg: Pass A, Bereich 4.

### B-16 — Hartcodierte Einzelkarten-/Prompt-Sonderfälle im Pilot (Wartungsfläche)
In `full_game_pilot_views.py`/`choices.py` stehen zahlreiche benannte Karten-/Prompt-Sonderfälle als
Engine-Lücken-Workaround. Kein Fehler — aber jede neue Engine-Version braucht dort neue Ausnahmen,
und kein Test zählt sie. Beleg: Pass A, Bereich 3. Vorschlag (in 03_VERBESSERUNGEN.md): Sonderfälle
als Register mit Begründung + Auslöse-Zählung führen, damit ein Fall, der nie feuert, auffällt
(Lehre aus #862: tote Regel = kein Effekt).

### B-17 — E1-Lanen-Differenz ungeklärt (nur scheinbarer Widerspruch)
`V12_BRIDGE_UND_MOTOR_2026-10-22.md:21` (−12 % Wall/−20 % CPU, 12/12 identische Hashes, Real-Pod)
vs. `T3_APPCDS_EVIDENCE_LANES_2026-10-23.md:5` („kein messbarer PB-03-Gewinn") — unterschiedliche
Lanes, nicht als Widerspruch belegt. Beleg: Pass A, Bereich 1. Folge: keine; nur festgehalten, damit
niemand die beiden Zahlen gegeneinander ausspielt.

### B-18 — Ungelesen, aber inventarisiert (ehrliche Restliste aus Pass A)
`XmageLosslessHiddenPlan.java` (668 Zeilen) NICHT gelesen; alle 209 Bridge-Testdateien (62.530
Zeilen) nur inventarisiert; Fork-Diff nur stichprobenweise (620 Dateien, +36.739/−520); Upstream nach
`fab0f23b7` (2026-10-20) NICHT GEPRÜFT; `decision/`-/`optimization/`-Importfreiheit nur in
`engine/rules/` + `agents/pilots.py` gegrept, repo-weit NICHT GEPRÜFT. Diese Liste wandert in
`99_OFFEN.md` weiter.

### B-19 — Offene Issues (Stand 2026-10-24, aus dem Auftrag, nicht neu geprüft)
#979 (Fork: 31 engine-unbekannte Precon-Karten — Claudes Lane, „Not for Muse"), #992 (OOM-Fix
`run_full_game_deck_comparison.py`, ~5,25 GB RSS bei 495 Records — NICHT BEGONNEN), #999/#1001
(von Muse erledigt, Hans schließt selbst), #996 (Hash-Rekalibrierung nach Pilot-Änderungen, durch
Phase 2 + 4b erneut ausgelöst), O5/O6/O7 (Owner-Entscheidungen: Transkriptformat, Guides statt
Spezialisten, Guides ins Repo). Offene Issues sind nicht Teil der PR-Tabelle; ihr Status wird in
Pass C/E weitergeführt. #1003 (PR) ist gemergt; #1004/#1005/#1006 sind gemergt — Stand
2026-10-25: #1005 verifiziert (Artefakt-Vergleich), #1004/#1006 teilweise (Tests grün,
Sign-off-Zahlen aus Repo nicht reproduzierbar, s. B-20), Echt-Spiele-Teile nicht nachgespielt.

### B-20 — Phase-Sign-off-Zahlen (#1004/#1006) aus Repo-Artefakten nicht reproduzierbar
Die Sign-off-Zahlen der Phasen 1 und 3a (falsche Seite 76/279→21/279, Geschenke 2/26→26/26;
Blockrunden 19→15) stammen aus Replay-Analysen auf 15 bzw. 24 aufgezeichneten Spielen, deren
Requests und deren Replay-Skript in keinem der beiden PR-Diffs enthalten sind (Diff #1004:
8 Dateien, kein Skript; Diff #1006: 6 Dateien, Fixture-Bump nur +42 Bytes). Das Fixture
`tests/fixtures/pilot_real_requests/real_pod_v1.jsonl.gz` ist ein Korpus-Summary (390 Records,
Seeds [1,2]), nicht die 279 Requests. Verifiziert wurde stattdessen: Unit-Tests
`test_pilot_target_sides.py` + `test_pilot_block_rounds.py` grün (40 passed, Head ee47312a7),
Regel-Code gelesen (Ziel-Seite, Lebens-/Commander-Uhr, BlockRound), Corpse-Augur-Ausnahme und
Collective-Effort-Override im Code gefunden, Squash-Nachricht #1006 bestätigt 19→15.
Folge (Prozess, niedrig): Künftige Phasen-PRs sollten den Replay-Korpus oder das
Replay-Skript committen, sonst bleibt der Sign-off nur auf dem Rechner des Autors prüfbar.
Die Echt-Spiele-Teile (je 24 Paare) sind ebenfalls nicht nachgespielt — die Bodies selbst
nennen den Recorded-Sign-off (≥10 Spiele) als Abnahme, nicht die Gewinnrate.
