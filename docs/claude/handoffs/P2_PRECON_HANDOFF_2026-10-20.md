# Handoff Java-Thread → Master-Thread — P2-Fix, Precon-Befund, PR-Reviews (2026-10-20)

Autor: Claude (Sonnet 5.5, Session `session_013QvmRntBHgANAZLKAnaMDB`). Fortsetzung der Muse-Übergabe
`handover/2026-10-19/` (Branch `muse/claude-handover`). Evidenz liegt in
`docs/claude/handoffs/evidence-2026-10-20/`. Alle Messungen sind lokal (4 Kerne, Last 7–10), also
`LOCAL_OBSERVED`: kein CI-Kredit, Zeiten nur indikativ.

## 0. Handoff-Prompt (zum Einfügen in den Master-Thread)

```
Du übernimmst die Koordination ab dem Stand des Java-Threads vom 2026-10-20 (Claude Sonnet 5.5).
Lies zuerst docs/claude/handoffs/P2_PRECON_HANDOFF_2026-10-20.md auf Branch
claude/optimistic-mayer-1d50ul (commander-playtest-lab) und danach nur bei Bedarf die Evidenz in
docs/claude/handoffs/evidence-2026-10-20/. Regeln wie bisher: XMage ist die einzige Rules Engine,
UNKNOWN ist nie PASS, kein Fallback, Fork-Push/Repin/Seal nur mit Owner-Go, Deutsch, Ergebnis zuerst.

Stand in 6 Punkten:
1. P0 "Patch-Semantik" ist aufgeklärt (nachgemessen): Die Abweichungen (Seed 5, Seed-10-Crash) kommen
   NICHT von CardImpl/Nested-Copy/Trigger, sondern von (a) sechs durch leere Stubs ersetzten echten
   Karten (Turbulent Dreams/Fen/Moor/Springs/Steppe/Wilderness) und (b) P1 GameState.getPlayersInRange
   Fast-Path (inRange ist ein Zug-Snapshot ohne Ausgeschiedene; der Fast-Path nimmt bei
   RangeOfInfluence.ALL alle). Zusätzlich ist P2 (CardImpl.getAbilities(Game) liefert die interne Liste)
   nachweislich unsicher: 20 Fehler in Mage.Tests (RoomCardTest/ShayCormacTest, u.a.
   ConcurrentModificationException), obwohl 36/36 Seeds identisch bleiben. 36 Seeds reichen als
   Gleichheitsnachweis NICHT; Mage.Tests muss mitlaufen.
2. Verifizierter Kandidat (auf altem Pin 348b37db, Engine 1.4.61): Nested-Copy-Vermeidung +
   TriggeredAbilities-Pre-Check + AbilitiesImpl.singleton, OHNE P1, OHNE P2: 36/36 Seeds identisch zur
   Baseline (Seed 10 läuft), Mage.Tests 7198 Tests / 0 Fehler. Mit den 48 neuen Karten (ohne die sechs
   Turbulent-Rewrites) ebenfalls 36/36 identisch. Als Patches:
   docs/claude/handoffs/evidence-2026-10-20/fork-commits/0001-*.patch und 0002-*.patch.
   NICHT im Fork gepusht (Push wurde vom Berechtigungssystem blockiert, siehe Abschnitt 6).
3. Portierung: 0001 lässt sich sauber auf mage#64 (043579bb, Engine 1.4.62) cherry-picken (nur Textebene
   geprüft). Dort ist KEINE Verifikation gelaufen. Vor Übernahme: 1.4.62 bauen, Mage.Tests (CI zählt
   dort 7459), 36-Seed gegen 1.4.62-Baseline. Die Regeln: bestehende Karten nie durch vereinfachte ersetzen,
   P1 und P2 bleiben draußen.
4. Issue #920 ist falsch gerahmt: "195/195 ENGINE_FAILURE" kam aus dem Test-Skript (dasselbe Deck auf allen
   4 Plätzen; Validator "distinct deck identities per seat" lehnt das vor dem JVM-Start ab). Es fehlen am
   Pin nur 53 Kartennamen (nicht 221/316). 173/195 Decks importieren am Pin ohne jeden Patch. In einer
   Stichprobe (25 echte 4er-Pods aus verschiedenen Precons, nur Pin-Karten) liefen 19 durch, 6 scheiterten
   (6 verschiedene Auslöser in 4 Fehlerfamilien, Abschnitt 4). Das ist die eigentliche Precon-Arbeit.
5. PR-Stand (live geprüft): #916 gemergt, #919 und mage#62 gemergt (nach Fix durch andere Threads),
   #915/#917/#918 geschlossen, #914 offen/Draft, Lab#923 (Repin v9 auf 043579bb) offen, mage#64 Draft.
6. Entscheidungen für Hans stehen in Abschnitt 6 des Handoff-Dokuments (Precon-Strategie, Push-Freigabe,
   Portierung auf 1.4.62, Verifikationsstandard).

Deine nächsten Schritte (in dieser Reihenfolge, sofern Hans nichts anderes sagt):
a) Abschnitt 6 mit Hans klären. b) Portierung 0001 auf mage#64 und Verifikation (Mage.Tests + 36 Seeds)
beauftragen. c) Precon-Sweep über alle 173 importierbaren Decks mit 4 verschiedenen Decks pro Pod
beauftragen (Skripte in evidence/scripts), Fehlerfamilien priorisieren. d) Issue #920 umschreiben, sobald
Hans entschieden hat. e) PB-03/Requalifizierung erst nach Portierung und Repin v9.
Aufpassen: Es laufen parallel mehrere Claude-Threads (Update-Thread session_0153bNHctMixicqvsvEr49B6 auf
claude/project-thread-4f9csz, claude/project-thread-5a2pp2) und Muse. Vor Pushes den Besitzer prüfen.
```

## 1. Ergebnis (Kurzfassung)

| Frage | Antwort | Evidenz |
|---|---|---|
| Was verursachte Seed-5-Abweichung und Seed-10-Crash der Muse-Fork-JAR? | Sechs ersetzte Karten (Turbulent-Lands). Ohne diese Rewrites sind Seed 5 und 10 baseline-identisch. | `DIRECTLY_VERIFIED` (Seeds 5, 10; `cards_only` ≠ Baseline, `cards_noturb` = Baseline) |
| Was ändert Seed 10 im Core? | P1 allein: 4406 statt 4327 Decisions, Sieger [1] statt [4]. | `DIRECTLY_VERIFIED` (Seed 10); Ursache `CODE_DERIVED` |
| Ist P2 sicher? | Nein. Allein verursacht P2 20 Fehler in 21 Tests (Pin: 0). | `DIRECTLY_VERIFIED` |
| Sind Nested-Copy und Trigger-Pre-Check sicher? | Auf allen geprüften Ebenen ja: 36/36 Seeds, Mage.Tests 7198/0 Fehler, einzeln 0 Fehler in Room/Shay-Tests. Kein Beweis, nur Evidenz. | `DIRECTLY_VERIFIED` (Seeds, Tests); Trigger-Reinheit `CODE_DERIVED` |
| 29/35 Mismatches der Übergabe? | Nicht reproduziert (ich habe den Muse-Fork-Stand nicht als Ganzes über 36 Seeds laufen lassen). Auf 2 Seeds sind es genau die zwei oben genannten Ursachen. | Teilweise nachgemessen |
| 221 fehlende Karten? | Falsch. Am Pin fehlen 53 Namen; alle 53 registriert der Fork-Patch (als SYNTHETIC-Stubs). | `DIRECTLY_VERIFIED` (echte Card-DB) |
| Warum 195/195 ENGINE_FAILURE (#920)? | Test-Skript: dasselbe Deck auf allen 4 Plätzen. | `DIRECTLY_VERIFIED` (Rohmeldung lokal reproduziert) |

## 2. Source Lock (live, 2026-10-20 ~10:20 UTC)

- CPL `origin/main` `0a6ce76` (Merge #922). Gegenüber `f994bd1` (K1) keine Änderung an `src`, `engine-bridge`,
  `scripts`, `config` (nur Workflows und Tests). Alle meine Läufe: Python-Stand = `f994bd1`/`0a6ce76`.
- Pin in `config/rules_engines.json` auf main: `348b37db5cf64f4ed503e8d37b776d5edc70e6d5` (Engine 1.4.61).
- Lab#923 (offen): Repin v9 auf `043579bb` (Engine 1.4.62, mage#64 Head). Die Muse-Patches sind darin nicht enthalten.
- Mage `master` jetzt `16dc17ea` (Merge von #62). Die Übergabe nennt `10a73922`: überholt. Master ist kein
  Vorfahr der Pin-Linie; der Pin liegt auf `claude/project-thread-md70sq` (Head des geschlossenen mage#61).
- Fork-Head `10931648` aus der Übergabe existiert auf GitHub nicht; `5dbff3a3` (P2-Commit) ebenfalls nicht.
  Nur die Patch-Dateien unter `handover/2026-10-19/fork-patches/` (Branch `muse/claude-handover`) sind greifbar.

## 3. Patch-Semantik: Messreihe

Orakel: 4er-Pod der Smoke-Decks (`REAL_DECK_PATHS`), Seeds 5 und 10. Builds: Pin 348b37db, Bridge aus
`engine-bridge/` (main), Varianten durch Austausch der geänderten Klassen im Bridge-JAR.
Baseline Seed 5 `32da567973…` (3727 Decisions, Sieger [3]); Seed 10 `445ca6bc0d…` (4327, [4]).
Die Hashes weichen von Muse ab, weil Muse mit dem Lab-Stand `muse/precon-pilot-improvements` misst; relativ
vergleichbar bleibt nur Variante gegen Baseline mit gleichem Python-Stand.

| Variante | Seed 5 | Seed 10 |
|---|---|---|
| alle 5 Core-Hunks | = Baseline | **abweichend** (4406, [1]) |
| nur Nested-Copy | = | = |
| nur P2 | = | = |
| nur Trigger-Pre-Check | = | = |
| nur P1 | = | **abweichend** (4406, [1]) |
| nur Karten-/Set-Patch (Muse, mit Turbulent-Rewrites) | **abweichend** (3711) | **FAILED** |
| Karten-/Set-Patch ohne die 6 Rewrites | = | = |
| Kandidat (Nested + Trigger + singleton), offizieller Maven-Build | = | = |

36-Seed-Läufe (Baseline gegen Kandidat, `benchmark_xmage_full_games.py compare`):
- Kandidat `fix2` (Nested + Trigger + singleton): **identical 36/36**, alle `ok`.
- Kandidat + 48 neue Karten ohne Turbulent-Rewrites: **36/36 identisch**, alle `ok`.
- Zwischenlauf mit P2 (`fix1`): 29/29 verglichene Seeds identisch, trotz kaputter Mage.Tests. Die Seeds sehen
  P2 nicht.
- CPU-Zeit Kandidat −6,7 % (fix2) bzw. −12,0 % (mit Karten) gegenüber Baseline auf belasteter Maschine:
  Richtung plausibel, Betrag nicht belastbar. Kein Qualifikationsbeleg.

Mage.Tests (7198 Tests, lokal, 125 skipped wie in CI):
- Kandidat (Nested + Trigger + singleton): 0 Failures, 0 Errors.
- Mit P2: 20 Errors (19 `RoomCardTest`, 1 `ShayCormacTest.testRemoveWard`). Ursache: `ShayCormacEffect.apply`
  entfernt Abilities aus `permanent.getAbilities(game).stream().forEach(...)`; mit P2 ist das die lebende
  interne Liste, ConcurrentModificationException. Auf dem Pin: 21/21 grün.

Ursache P1 (`CODE_DERIVED`): `PlayerImpl.updateRange` berechnet `inRange` einmal pro Zug über `PlayerList.getNext/Previous`,
das ausgeschiedene Spieler überspringt. `getPlayersInRange(…, excludeLeavedPlayers=false)` filtert über diesen
Snapshot. Der Fast-Path für `RangeOfInfluence.ALL` nimmt stattdessen alle Spieler in `players`, also auch
frühere Verlasser. Sein Kommentar ("alle in Reichweite per Definition") ist falsch.

Ursache Turbulent (`DIRECTLY_VERIFIED` im Patch-Text): `fork-patch-cards-n-z.patch` überschreibt bestehende Klassen
`TurbulentDreams` (Sorcery → Land ohne Fähigkeiten) und `TurbulentFen/Moor/Springs/Steppe/Wilderness`
(Mana-Fähigkeiten und ETB-Bedingung entfernt).

Nicht Teil des Kandidaten: P1, P2, die sechs Rewrites, `PERF_OPTIMIZATION_REVIEW.md` (veraltete Aussagen).

### Zwei ungeprüfte Annahmen, die im Kandidaten stecken
- Nested-Copy: Die Behauptung "Flag nur in `createSimulationForPlayableCalc` gesetzt" ist per `grep` belegt. Dass
  Mutationen während der Mana-Berechnung in der geteilten Simulation nirgends nachwirken, ist nur durch 36 Seeds +
  Mage.Tests gestützt, nicht bewiesen.
- Trigger-Pre-Check: Alle 1325 `checkEventType`-Implementierungen im Pin-Baum sind per Skript klassifiziert
  (1290 reine Typ-Vergleiche, 35 Ausreißer von Hand geprüft: rein). Die Integritäts-Checks, die den frühen
  Rücksprung bemerken würden, sind abgeschaltet und nur durch Quelltext-Änderung einschaltbar.

## 4. Precon (#920)

Messungen am unveränderten Pin (kein Fork-Patch):
- Karten-DB: 6350 Namen in den 195 Decks, **53 fehlen**, 218 der 221 Namen aus der Übergabeliste sind vorhanden.
  Fork-Patch registriert alle 53. Die Übergabeliste bleibt unerklärt (vermutlich andere Abfragemethode).
- Zusätzlich 5 Namen mit Doppelseiten-Identität (`Esika, God of the Tree // The Prismatic Bridge` u. a.): der Lab-Loader
  liefert den kombinierten Namen, XMage löst nur die Vorderseite auf, `CARD_IDENTITY_MISMATCH`. Betrifft 4 Decks.
- Importierbar ohne Patch: **173/195**. Blockiert: 18 durch fehlende Karten, 4 durch DFC-Identität.
- Stichprobe: 25 Pods à 4 verschiedene Decks (nur importierbare Decks, Seed 1, Pin-JAR): **19 ok, 6 gescheitert**.

| Fehlerfamilie | Auslöser | Pods |
|---|---|---|
| Kosten mit Auswahl, Engine bietet an, kann nicht bezahlen (`XMAGE_ACTION_EXECUTION_FAILED`) | Ghave (Counter entfernen), Necron Overlord (X, X Artefakte tappen), Grim Hireling (X Treasures opfern) | 3 |
| Modaler Zauber "choose one or more" (Escalate) | Collective Effort | 1 |
| DFC-Identität | 4 Decks (Name-Mapping Lab vs. XMage) | 1 |
| `DECISION_ADVANCE_TIMEOUT` (75 s) in `DistributeCountersEffect.apply` | Hang oder Langsamkeit unter Last: UNKNOWN, 2× reproduziert | 1 |

Lange-Schwanz-Erwartung: Jede Familie ist Bridge-Arbeit (`engine-bridge/**`, Requalifizierung). Anzahl weiterer Familien
unbekannt (`UNKNOWN`), bis alle 173 Decks gespielt sind.

### Optionen (Aufwand ist Schätzung, keine Messung)
- A. **Filtern + vollständig sweepen (empfohlen als Erstes):** Pod-Generator, 173 Decks in ca. 44 Pods,
  ca. 2 h Maschinenzeit bei 2 parallelen Pods, danach Triage nach Familie. ½–1 Tag. Ergebnis: echte Deck-Passquote.
- B1. **18 Decks mit SYNTHETIC-Stubs:** Commit liegt fertig (0002). Karten spielen nicht wie gedruckt. Nur mit
  Kennzeichnung und nie als Regelevidenz nutzbar. Aufwand: ca. 0, aber Wert niedrig.
- B2. **53 Karten voll implementieren:** nach Aufwand sortiert ergeben 11 Karten 11 Decks, 19 Karten 14 Decks,
  34 Karten 17 Decks, 53 Karten 18 Decks (viele Doctor-Who-Karten). Grobe Schätzung 3–6 Personentage inkl. Tests.
  Erst nach A sinnvoll.
- C. **Bridge-Familien beheben:** pro Familie 0,5–2 Tage inkl. Requal-Bezug (Schätzung), Reihenfolge nach betroffenen Decks.
- Meine Empfehlung: A → C (nach Häufigkeit) → B2 nur für Decks, die sonst laufen; B1 nicht als Ergebnisbasis.

Kommentar mit diesen Fakten steht auf Issue #920. Der Issue-Text selbst ist unverändert.

## 5. PR-Reviews (Kommentare gepostet, 2026-10-20)

- #915 K3: nicht mergefähig. Leak-Test vergleicht handgeschriebene Sets, Feldnamen existieren im Redactor nicht, toter Code, Reuse-first fehlt. Inzwischen geschlossen.
- #916 K4: mergefähig, K4 bleibt PARTIAL. Inzwischen gemergt.
- #917 K5: Gerüst ohne Runner, überzogener Docstring. Inzwischen geschlossen.
- #918 K6: Tests rufen keinen Produktionscode auf, erfundene Event-Namen. Inzwischen geschlossen.
- #919 und mage#62: Workflow war ungültig (`env`-Kontext im Job-Level-`env`, `actionlint`); Fix durch andere Threads gemergt.
  mage#62: rote Mage.Verify-Checks lagen auf master-Basis `10a73922`, nicht am PR.
- #914: Head `a5afdcfb`, Draft; es fehlt weiter der ≥10-Seed-Pilot-Vergleich auf dem PR (Pilot-Änderung) und die Werte stehen nur als
  Kommentar. Nicht geprüft in dieser Session.

## 6. Entscheidungen und offene Punkte für Hans

1. **Fork-Push:** Mein Push von `perf-fix2` (zwei Commits auf Pin-Basis) auf `claude/optimistic-mayer-1d50ul`
   wurde vom Berechtigungssystem blockiert (`Modify Shared Resources`). Der Go aus der Unterhaltung reichte dem
   Klassifikator nicht. Ich habe nicht umgangen. Entweder Berechtigungsregel für `git push` im mage-Fork ergänzen
   oder die Patches `fork-commits/0001`/`0002` im Master-Thread anwenden und pushen. **Gesichert nur als Patch-Dateien**;
   die lokalen Commits (`b7c3a62f`, `7070d167`) liegen im flüchtigen Container.
2. **Portierung auf 1.4.62:** nur 0001 (Perf), nicht 0002 (Karten) und nie P1/P2/Turbulent. Verifikation dort fehlt.
3. **Precon-Strategie:** A zuerst, dann C? B1 gewünscht oder nicht?
4. **Verifikationsstandard für Perf-Patches:** 36 Seeds allein sind nachweislich blind für P2. Vorschlag: Seeds + volle
   Mage.Tests + je Hunk ein Einzel-Orakel, als Gate für jede Fork-Perf-Änderung.
5. **Issue #920:** Titel/Text auf "Precon-Pods: Bridge-Fehlerfamilien" umstellen (Hans' Go auf Text steht aus, ich habe nur kommentiert).
6. **mage master rot:** `Mage.Verify` (15 Fehler in 91131 Karten, 3 Set-Fehler) war auf master `10a73922` rot. Mit Merge von #62
   steht master weiter auf dieser Basis. Der Update-Thread meldet Verify grün auf `043579bb`; für master offen.

## 7. Reproduktion und Artefakte

`evidence-2026-10-20/`:
- `fork-commits/0001-*.patch` (Perf, 3 Dateien), `0002-*.patch` (48 Karten + 10 Set-Dateien, SYNTHETIC)
- `rejected-patches/` P1, P2, Muse-Rewrites der 6 Turbulent-Karten
- `precon_pod_sweep.json` (25 Pods mit Ursachen), `precon_import_blockers.json`, `precon_pin_check.json`, `precon_fork_cover.json`
- `seed_hashes_pin_vs_candidates.json` (Hashes Baseline und Kandidat, 36 Seeds)
- `scripts/`: `make_variant.sh` (Klassen-Overlay in Bridge-JAR), `split_hunks.py`, `run_oracle.sh`, `partial_cmp.py`,
  `precon_pod.py`, `CardCheck.java`/`CardIdent.java` (Card-DB-Abfrage), `variant_test.sh`/`full_tests.sh` (Mage.Tests)

Nicht archiviert, weil es die Fehler-Redaktion der Lab-Pfade aushebelt: lokale Debug-Hilfen (Monkeypatch auf
`failure_privacy.diagnostics_digest`, Klassen-Overlay für `XmageFullGamePlayer`, das beim Abbruch den Ability-Namen in eine Datei
schreibt). Vorgehen: Monkeypatch lokal, nur im Analyse-Lauf, nichts speichern oder posten.

Bauweise: `mvn -B -ntp -DskipTests install -pl :mage-deck-constructed,:mage-game-commanderfreeforall,:mage-game-commanderduel -am`
im Pin-Checkout (4:24 min), danach `mvn -DskipTests package` in `engine-bridge/`.
`benchmark_xmage_full_games.py run --jar … --seeds 1-36 --workers 2 --private-card-repository` (ca. 45 min je JAR bei Last).
Hinweis: Die Klassen der Overlay-JARs und des Maven-Builds unterscheiden sich byteweise (Grund nicht untersucht, vermutlich
Compiler-Optionen); die 36-Seed-Läufe liefen auf Overlay-JARs, für den Maven-Build des Kandidaten sind nur Seeds 5 und 10 gemessen (identisch).

## 8. Korrekturen an Annahmen aus der Muse-Übergabe

- "P2 ist zu 80 % der Übeltäter / 83 % der Spiele": falsch für die Mismatches; P2 ist trotzdem unsicher.
- "unmodifiable wrapper": `AbilitiesImpl.unmodifiable` existiert nicht; die 176 mutierenden Aufrufer betreffen `getAbilities()`,
  nicht `getAbilities(Game)`; der Fix für P2 ist Entfernen.
- "Nicht die neuen Karten (JAR B hat sie nicht, läuft aber)": Fehlschluss; das Karten-Patchset war der Hauptverursacher.
- "221/316 fehlende Karten", "95 vereinfachte" (Issue #920 sagte ca. 45): tatsächlich 53 fehlend, 48 neue Klassen.
- "Seed 10 crasht im Core": der Crash kam aus den Karten; P1 verursacht dort nur eine Abweichung.
- Die Umgebung des Handovers (`~/workspace`, `/tmp`) war in der Cloud-Session nicht vorhanden; die Daten kamen später per Branch.
