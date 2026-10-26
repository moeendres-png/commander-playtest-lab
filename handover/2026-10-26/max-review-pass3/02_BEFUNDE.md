# Pass 3 — Befunde (Pass B) — Arbeitsstand 2026-10-26

Evidenzklassen: DIRECTLY_VERIFIED = selbst gesehen/gelaufen; CODE_DERIVED = aus gelesenen Code abgeleitet; UNKNOWN = nicht belegt, nie PASS. Schwere ist eine Pass-3-Einschätzung, kein Urteil über die PR-Autoren.

## Hoch

(noch keine — bewusst leer, bis eine Pass-3-Messung oder ein gelesener Codepfad einen hohen Befund trägt. Ein leerer Hoch-Block ist ehrlicher als ein aufgeblasener.)

## Mittel

### B-01 — 36-Seed-Referenz ist am HEAD stale (eigene Regel der Datei)
- Beleg: `docs/performance/REFERENCE_36_SEEDS_2026-10-26.md` gilt für Lab `b528082d5`; `git diff b528082d5..6fb26071 -- src/commander_lab/engine/rules/full_game_pilot src/commander_lab/agents engine-bridge/src/main` = 3 Dateien, 75 Insertionen: `payment.py` +65, `priority.py` +9, `choices.py` +1 — das ist #1027 (Target-Discount). Die Datei selbst sagt, die Referenz halte nur, solange Pilot-Code, Bridge-Quellen und Pin unverändert sind. DIRECTLY_VERIFIED (Diff-Befehl, 2026-10-26).
- Folge: Wer am HEAD gegen diese Referenz misst, misst gegen einen anderen Piloten. Eine neue Referenz am HEAD ist nötig, bevor #1027-Effekte oder spätere Pilot-Änderungen als "gleich/anders" beurteilt werden. Kein Fehler in der Datei selbst.
- Pass-C-Kandidat: Referenz am HEAD neu erzeugen (36 Seeds, Twin) + Regel, dass jede Pilot-Änderung die Referenz automatisch invalidiert (CI-Check: Referenz-Commit == HEAD oder Warnung).

### B-02 — Mulligan-Modell auf 195 Decks gefittet, Pool ist 173 — kein Refit belegt
- Beleg: `src/commander_lab/agents/pilots.py:320` (Kommentar: 58.500 Hände der 195 Precon-Decks, R² 0,33); Pool heute 173 = 164 + 9 SYNTHETIC (nach #1026, Nature of the Beast entfernt; vorher 195 → 186 → 173). `git log -- src/commander_lab/agents/pilots.py` zeigt als letzte mulligan-relevante Änderung #1002 (Phase 2), danach nur #1013 (Guides als Mess-Arm) — kein Refit-Commit ersichtlich. CODE_DERIVED + git-Log.
- Folge: Das Modell ist nicht falsch bewiesen (lands/spells-generisch, entfernte Decks sind ein kleiner Anteil), aber seine Kalibrierung ist für den aktuellen Pool unbelegt. Refit auf 173 + Keep-Rate-Vergleich ist ein billiger, messbarer Pass-C-Kandidat. Schwere mittel-niedrig, hier mittel eingeordnet, weil Mulligan jede Partie betrifft.

### B-03 — Bridge-Testklasse ohne Einzelnachweis im Pass-3-Build
- Beleg: Pass-3-Build 2026-10-26, `mvn_bridge.log`: `XmageFullGameReplayExportTest` hat eine Running-Zeile, aber keine "Tests run"-Zeile und einen leeren Surefire-Report; Gesamt: 1081 run / 0 Failures / 0 Errors / 1 Skipped, BUILD SUCCESS. In Pass 2 hatte dieselbe Klasse 4 INIT_FAILED-Fehler. Ob sie jetzt grün, leer oder übersprungen ist, ist aus den Artefakten NICHT ableitbar. DIRECTLY_VERIFIED (Log + Reports).
- Folge: Der Gesamt-Build darf nicht als "alle Bridge-Tests grün" zitiert werden, solange diese Klasse keinen Einzelnachweis hat. Pass-C-Kandidat: Surefire-Report dieser Klasse im CI als Artefakt sichern oder die Klasse in einen eigenen, benannten Schritt legen.

### B-04 — DeckImporter: Hash ungeprüft, Duplikate/Banned/Colour-Identity extern
- Beleg: `XmageDeckImporter.java` (504 Z., vollständig gelesen, notes_deckimporter_fork.md): deck_hash nur auf non-blank geprüft, nie gegen Inhalt verifiziert; keine eigene Duplikat-, Banned- oder Colour-Identity-Prüfung — alles ruht auf dem XMage-`Commander`-Validator, dessen Code in Pass 3 NICHT gelesen wurde. CODE_DERIVED (Bridge-Seite).
- Folge: Ein Deck mit falschem Hash oder (falls der Validator eine Lücke hat) mit Duplikaten würde auf Bridge-Seite nicht auffallen. Pass-C-Kandidat: Hash-Verifikation + eigene Duplikat-/Commander-Farb-Prüfung als Fail-closed-Gate vor dem Import (reine Python-Prüfung, keine Rules-Engine, weil es um Deck-Konstruktion geht, nicht um Spiel-Legalität — Abgrenzung zu "XMage = einzige Rules Engine" im Issue-Entwurf sauber begründen).

### B-11 — Korvold-Piloten sind in Live-Spielen tot (6 Klassen, ~530 Zeilen)
- Beleg (direkt nachgeprüft, 2026-10-26): `src/commander_lab/agents/live_routing.py:14-21` (`_RETIRED_KORVOLD_PILOTS`, 6 Namen) + `_validate_family` (ValueError bei expliziter Anfrage, `auto` → GenericCommanderPilot); `agents/__init__.py:2` exportiert `live_routing.build_pilot`, nicht `pilots.build_pilot`; `full_game.py:25`, structural/evals/recorder importieren alle `commander_lab.agents.build_pilot` = Live-Routing. Klassen in `pilots.py:919-1448` (KorvoldPilot + 5 Varianten). Nur `ensemble.py:26` und `tools/service_knowledge.py:8` importieren `pilots.build_pilot` direkt (Legacy-Pfad). DIRECTLY_VERIFIED.
- Folge: Jede Korvold-Verbesserung, die nur über `pilots.build_pilot` getestet wird, ändert kein Live-Spiel — exakt die #862-Falle (toter Code, identische Ergebnisse = kein Effekt). Tests, die Korvold über den Legacy-Pfad grün sehen, geben falsche Sicherheit. Pass-C-Kandidat: Korvold-Klassen als "retired" markieren + Legacy-Pfad in Tests verbieten (oder löschen, mit Hans-/Claude-Go, weil der Name in Docs steht) + ein Test, der beweist, dass Live-Routing Korvold ablehnt. Schwere mittel, Tendenz hoch für die Code-Hygiene, weil 530 Zeilen Spezialisten-Code betroffen sind. Korrektur zum Subagenten-Bericht: es sind 6, nicht 7 Korvold-Klassen (Base + 5 Varianten, grep-verifiziert).

### B-12 — Stiller Katalog-Ausfall: kaputte Kartendaten → leerer Katalog, kein Fehler
- Beleg (direkt nachgeprüft): `src/commander_lab/agents/card_knowledge.py:105-106` und `:218-219`: bei OSError/ValueError wird `{}` zurückgegeben, kein Fehler, keine Warnung im Pfad ersichtlich. Piloten spielen dann nur noch namensbasiert (notes_pilot_rest.md §4/§11, CODE_DERIVED für die Spiel-Folge). DIRECTLY_VERIFIED (Codezeilen), Spiel-Folge CODE_DERIVED.
- Folge: Fail-open statt fail-closed — genau gegen die stehende Regel (nicht unterstützte Pfade fail closed). Ein kaputtes `pilot_card_knowledge.json` nach einem Update würde still schlechtere Spiele erzeugen, ohne dass ein Gate rot wird. Pass-C-Kandidat: Katalog-Laden fail closed (oder mindestens ein lautes Startup-Gate: Kataloggröße gegen Pool prüfen, 0 Einträge = Abbruch).

## Niedrig

### B-05 — Relativer Jar-Pfad in Beispielen führt in die Falle
- Beleg: `scripts/run_full_game_deck_comparison.py:10` und `scripts/run_optimizer_v2_full_game_route.py:9` zeigen `COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar engine-bridge/target/… full-game"`. Die Bridge läuft aber in `.runtime/engine` (resolve_engine_working_directory), dort existiert der relative Pfad nicht → Pass-3-Smoke zuerst BRIDGE_CLOSED, stderr "Unable to access jarfile" (per diag_smoke.py belegt), mit absolutem Pfad PASS. `scripts/benchmark_xmage_full_games.py:187-194` dokumentiert die absolute-Pfad-Regel selbst. DIRECTLY_VERIFIED.
- Folge: Kein Spiel-Schaden (fail closed), aber jeder neue Messende läuft in dieselbe Falle. Fix: Beispiele auf absoluten Pfad umstellen oder eine Warnung, wenn der Pfad relativ ist. Direkt PR-fähig (Docs/Scripts, keine Rules-Änderung).

### B-06 — Deck-Guides sind Parameter, aber nicht in Live-Piloten verdrahtet
- Beleg: `notes_pilot_rest.md` §7: `deck_guides.py` (81 Z., vollständig gelesen) — Guides als Pilot-Parameter, NICHT in Live-Piloten verdrahtet. CODE_DERIVED (Subagent-Lesung).
- Folge: Guide-Arbeit (#1013: Guides als Mess-Arm) ist Messung, nicht Spielstärke, solange die Verdrahtung fehlt. Pass-C-Kandidat: Guide-Verdrahtung als eigener, gemessener Schritt (mit 10+-Seed-Vergleich, sonst kein Stärke-Claim).

### B-07 — Mana-Budget = 1 je Quelle (im Code als Residual vermerkt)
- Beleg: `notes_pilot_core.md`: `_mana_budget`/`_available_mana` in `payment.py:1456-1478`, Residual-Vermerk `payment.py:1516-1535`: Self-Tap-/Sacrifice-Fähigkeiten können das Budget um 1 überschätzen. Payment-Plan modelliert nur {T}/Sacrifice-Self-Quellen mit lesbarem "Add …"-Effekt, kein Convoke/Delve/Improvise/Assist, DFS-Knoten-Cap 20.000. CODE_DERIVED.
- Folge: Bekannter, im Code ehrlich vermerkter Restfehler — kein neuer Befund, aber ein Pass-C-Kandidat mit klarem Messprotokoll (Zahl der betroffenen Zahlungen in echten Spielen zählen, dann fixen).

### B-08 — Zwei Klassen heißen StructuralSimulator
- Beleg: `notes_inventory.md`: `engine/structural/simulator.py` (2.109 Z.) vs. `simulator_fidelity.py` (349 Z.); `structural/__init__.py` exportiert die Fidelity-Variante, `simulator.py` exportiert nur `ENGINE_VERSION`, `commander_cast_cost`, `commander_damage_is_lethal`. CODE_DERIVED.
- Folge: Verwechslungsgefahr für jeden neuen Lesenden; die Adjudizierung (Claude, 2026-10-26: verträglich unter 3 Auflagen) gilt für den Simulator als Filter, nicht als Ranking. Fix: Umbenennen oder ein Modul-Alias mit Deprecation-Hinweis — klein, aber nur mit Hans-/Claude-Abstimmung, weil der Name in Docs/Handoffs steht.

### B-09 — Vergleichs-Paare sind nicht vollständig unabhängig
- Beleg: `notes_pilot_core.md`: `full_game_comparison.py:515-519` dokumentiert selbst, dass Sitz-Rotationen eines Seeds denselben Shuffle teilen — Paare nicht vollständig unabhängig, Intervalle etwas zu schmal, Sign-Test-Urteil unberührt. CODE_DERIVED (im Code dokumentiert).
- Folge: Kein Rechenfehler, aber jede "knappe" Signifikanz am Rande ist schwächer als sie aussieht. Pass-C-Kandidat: Cluster-robuste Intervalle oder Seed-Rotation als Cluster in der Auswertung.

### B-13 — GraveyardPilot == ArtifactPilot == EnginePilot (nur Name anders)
- Beleg (direkt nachgeprüft): `pilots.py:1663-1667` — beide Klassen subklassen `EnginePilot` ohne einen einzigen Override, nur `pilot_name` unterscheidet sich. DIRECTLY_VERIFIED.
- Folge: Drei "Archetypen" im Routing, ein Verhalten. Wer Graveyard- vs. Artifact-Verhalten misst, misst Rauschen. Fix: entweder echte Gewichts-Deltas geben (mit Messung) oder die Archetypen auf EnginePilot zusammenlegen — klein, PR-fähig, aber mit Messung, sonst ist es nur Kosmetik.

### B-10 — Commander-Schaden und -Tax im Pilot-Blick unsichtbar
- Beleg: `notes_bridge.md`: `commander_damage_visible` und `commander_tax_visible` = false in beiden Lanes (Full-Game und Midgame). CODE_DERIVED.
- Folge: Der Pilot kann Commander-Schaden (21er-Regel) und Commander-Tax nicht aus seiner Sicht sehen — er spielt gegen eine Regel, die er nicht beobachten kann. Ob das in echten Spielen zu Fehlentscheidungen führt, ist NICHT gemessen (Pass-B-Messung offen). Als Befund-Kandidat, nicht als bewiesener Spiel-Fehler.

## Info / Offen (kein Urteil)

- Offene Issues am Stand: nur 4 — #1030 (Any in tools/service_knowledge.py), #1029 (Pilot-Mining P1–P11, Bericht noch offen), #1028 (Time-Bomb-Audit, Statik fertig, Kontroll-/Shift-Läufe offen), #979 (Fork: 31 engine-unbekannte Precon-Karten als Printed implementieren, Follow-up zu #920). #979 ist der größte offene Coverage-Posten; seine 31 Karten sind ohne Fork-Arbeit (Claude-Lane, Hans-Go) nicht schließbar.
- #1027-Claim (Bitter Downfall: Zahlungen abgebrochen 23 → 0 in 24 Spielen, alle abgebrochenen Zahlungen 43 → 20, Entscheidungen 72.021 → 70.874) ist aus dem PR-Body übernommen, in Pass 3 NOCH NICHT auf echten Spielen reproduziert (Kette steht aus, JVM-Kapazität mit #1029/UI/#1034 geteilt). Status: NICHT GEPRÜFT, nicht bestätigt, nicht widerlegt.
- #1008-Claim (Slim-Batch-Records, 200-Spiele-Vergleich, Urteil identisch, Runner-Peak-RSS 1824 vs 2391 MB) ebenfalls aus PR/Memory übernommen, in Pass 3 NOCH NICHT reproduziert.
- Meta-Lane PR1–PR6 (#1016, #1017, #1018, #1020, #1021, #1025) gemergt, PR7 (`external_prior`) ausdrücklich NICHT freigegeben (Memory, 2026-10-25) — in Pass 3 nicht neu verifiziert, aber als Grenze für Pass-C-Empfehlungen festgehalten: keine externen Priors als harte Filter vorschlagen.
