# Q1-a Inventur: was am Entfernen nach E15 Q1 hängt

Stand: `main` @ `0fb8fce19a3c88167bb9a7c6188aff9de00dee1c` (2026-11-20). Issue #1664 (Refs #1656, #1612).
**Nur Bericht, kein Produktcode.** Alle Zahlen stammen aus den Kommandos in Abschnitt 2 und Anhang A
(`git grep`, `wc -l`) und ergeben bei Nachlauf auf diesem Stand dieselben Werte. Wo etwas nicht belegt
ist, steht UNKNOWN. Schätzungen sind als Schätzung gekennzeichnet und nennen ihre Rechnung.

Quellen: `docs/STUDIO_CHARTA_V2.md` (§4 Entfernen-Liste, §5 Q1/Q11), `docs/OWNER_DECISIONS_STUDIO_20261118.md`
E15, Issues #1664/#1665/#1666/#1659, Claim-Stand in #1167 (Kommentar 2026-11-20 05:30).
Hinweis zum Dateinamen: das Issue nennt `q1_removal_inventory.md`; auf Anweisung des Co-Lead heißt die Datei
`q1a_inventur_entfernen.md`.

## 1. Ergebnis in Kürze

1. **Keine direkte Sperre.** In `qualification/`, `src/commander_lab/qualification`, `tests/qualification`,
   `candidate-qualification/`, `engine-bridge/`, `pb03-runtime-qualification.yml`,
   `production-qualification.yml` und `WS17_SHA256SUMS` nennt keine Stelle ein Q1-Ziel, `simulation_run`,
   die Tierliste, ein Rating oder `studio` (je 0 Treffer, Befehl und Zahlen in 3.1). Die älteren Lanes (Q11)
   verweisen also nicht auf die Q1-Ziele; es gibt nichts, was dort mitzulöschen oder zu schützen wäre.
2. **Fünf indirekte Sperren** (3.2): Architektur-Ratsche mit Fixture (sinkt eine Zahl, schlägt der Test fehl),
   `windows-runtime.yml` (nennt `test_studio_simulations.py` und `paired_series` beim Namen), die Pfadfilter
   zweier Workflows mit `deck_variant.py`, `simulation_run` als Träger des Siegel-Stands der Bridge, und
   `game_pool.py` (nutzt `play_batch` weiter).
3. **Die Charta-Liste zerfällt in zwei Teile.** Als Q1-b tragfähig sind Gesamtrating v1, Rubrik-v1-Signale,
   Rating-Layers, Turnier-Conversion, zweite S–D-Skala (und relative Stufen), Gewicht `simulation` und der
   Heuristik-Vorfilter (K1 bis K7). **Nicht in Q1-b** gehören `simulation_run`/`simulation_card` und die
   Tabelle `tier_snapshot` (Schema, K-2; B1 #1657 schreibt gerade neue Spalten in `simulation_run`),
   `memo.py` (D-1) und die alten Orchestrierer (D-2 P5, #1652 offen). `subarchetypes.py` ist ein
   unabhängiges Blatt und kann jederzeit separat gehen.
4. **Umfang K1 bis K7:** etwa 7.750 Zeilen (rund 3.750 Quelltext, rund 4.000 Tests), Schätzung nach 5.
   Das ist etwa das Fünffache der 1.500-Zeilen-Grenze aus dem Issue; Empfehlung: sechs PRs (9).
5. **Größtes fachliches Risiko:** `StrengthSettings` wirft bei unbekanntem Komponenten-Schlüssel
   (`strength.py:653`, `ValueError("unknown component")`). Jedes gespeicherte `strength_profile.spec` enthält
   alle Komponenten (`to_dict`, `strength.py:785-787`), also auch `simulation`, `rubric` und
   `tournament_conversion`. Wird die Komponente gestrichen, wird jedes alte Profil `valid: false`. Das ist ein
   Datenrisiko, kein Schema-Bump; es braucht vor dem ersten Streichen eine Toleranzregel (8, R1).
6. **Rubrik v2 verliert beim Entfernen von `overall_rating.py` ihren einzigen Verbraucher** (`card_understanding`
   wird nur dort und für den Cache-Schlüssel `web.py:540` gelesen). B3 (#1659) oder ein eigener kleiner Pfad
   muss die Spalte „Kartenverständnis (Modellurteil)“ liefern, bevor K1 gelöscht wird.
7. **Die Abnahme „Antwort-Manifest unverändert bis auf die entfernten Felder“ ist mit dem vorhandenen
   Werkzeug nicht prüfbar:** `scripts/studio_response_manifest.py` vergleicht Status, Länge und SHA-256 des
   Antwortkörpers, kein Feldvergleich (`compare_records`, Zeilen 655-675); `test_studio_response_manifest.py:42-45`
   erwartet fest 30 Routen. `/api/strength` ändert sich absichtlich und wird immer als abweichend gemeldet.
8. **Namensfallen** (3.3): `/api/layers`, `layer_overview`, `source_layers.py` und
   `test_studio_import_all_layers.py` sind Datenebenen, nicht Rating-Layers, und bleiben. Das Issue nennt die
   Testdatei fälschlich in seiner Auswahlliste.
9. **Entscheidungen für den Co-Lead** (10): Umfang Turnier-Conversion (nur Modul/Route/Panel oder auch
   Komponente und Signal-Import), Umfang „zweite Skala“ (Stufenbuchstaben der Verbreitung und relative
   Stufen S–F, ob auch „Gleiche Funktion“), Verbleib des Rubrik-v1-Datenordners, ob die Funktion
   `tier_snapshot` schon in Q1-b geht, Verbleib von `scripts/compute_topdeck_conversion.py`.

## 2. Methode und Reproduzierbarkeit

- Stand: Commit `0fb8fce19a3c88167bb9a7c6188aff9de00dee1c` (`origin/main` am 2026-11-20, nach dem Merge von #1669; der
  erste Messlauf auf `724ce682` ergab dieselben Treffer- und Dateizahlen, nur Zeilennummern in `builder.py`,
  `test_studio_static_guards.py` und `test_studio_builder.py` haben sich verschoben und sind neu gemessen). Nachlauf immer
  gegen diesen Commit (Anhang A), nicht gegen den späteren Stand von `main`.
- Je Ziel ein Suchmuster `K1` bis `K11` (Anhang A, Befehl `git grep -n -I -E '<Muster>' -- <Pfad>`). Die
  Treffer- und Dateizahlen in 5 stammen aus `git grep -n | wc -l` und `git grep -l | wc -l` über
  `src/commander_lab/studio`, `scripts`, `tests`, `docs`. Trefferzeilen sind **Fundstellen, kein Löschumfang**;
  der Löschumfang in 5 ist getrennt als Schätzung ausgewiesen (ganze Dateien per `wc -l`, Blöcke aus
  gemessenen Zeilenbereichen, Rest als Trefferzeilen).
- Die Muster sind absichtlich eng (Symbole, keine Wörter wie `layers`). Bekannte Fehltreffer und
  Namensfallen stehen in 3.3; ihre Fundstellen sind in Anhang B mitgezählt und dort gekennzeichnet.
- Test-Urteile (6) stützen sich auf Funktionsbereiche (Zeilen Anfang-Ende) aus einem Skript, das jeden
  Treffer der nächsten vorangehenden `def` zuordnet.
- Nicht ausgeführt (NOT_RUN): keine Tests, kein Server, kein Antwort-Manifest, keine echte Studio-DB, kein
  Browser, keine Echt-Engine. Aussagen über Verhalten gegenüber dem Owner-Store sind UNKNOWN.

### Zahlen vorher (Stand `0fb8fce1`)

| Größe | Wert | Herkunft |
|---|---:|---|
| Python-Module `src/commander_lab/studio/*.py` | 83 Dateien, 53.868 Zeilen | `cat … \| wc -l` |
| Routen in `web.py` | 117 | `grep -cE '^\s+@app\.(get\|post\|put\|delete\|patch)\('` |
| `static/` | 39 Dateien, 14.505 Zeilen | `cat … \| wc -l` |
| `tierliste.js` / `.html` / `.css` | 2.453 / 94 / 195 Zeilen | `wc -l` |
| `tests/unit/test_studio*.py` | 104 Dateien, 50.975 Zeilen | `ls`, `cat … \| wc -l` |
| `tests/unit/*.py` insgesamt | 360 Dateien | `ls` |
| `StudioStore.SCHEMA_VERSION` | 21 (`store.py:17`) | Datei |

Routen und Aufrufer (n = Aufrufstellen im Quelltext von `static/`, ohne Tests):

| Route | `web.py` | Aufrufer in `static/` | Weitere Verweise |
|---|---|---|---|
| `GET /api/rating-layers` | 877 | 1 (`app.js:2657`) | Manifest-Skript 144, Cache-Art `answer:rating_layers` (`cache.py:187`), 8 Testzeilen |
| `GET /api/tournament-conversion` | 920 | 2 (`tierliste.js:2247`, `daten.js:349`) | Manifest 148, `answer_cache.file_answer`, 14 Testzeilen |
| `POST /api/prefilter` | 1580 | 1 (`app.js:1359`) | 7 Testzeilen |
| `GET /api/strength/snapshot` | 846 | 0 | 2 Testzeilen (`test_tier_snapshot_1420.py:507,543`) |
| `GET /api/universe/spread` | 1103 | 1 (`tierliste.js:1510`) | 30+ Testzeilen (n/N bleibt, siehe K5b) |
| `POST /api/strength` | 860 | 4 (`app.js:2668,2680`, `tierliste.js:1619,1741`) | Antwort verliert Felder (K1, K3, K5, K6) |

## 3. Sperren

### 3.1 Direkte Sperren: Negativbefund

Befehl (je Pfad; ein Muster, das alle Q1-Ziele, `simulation_run`/`simulation_card`, `studio`, Tierliste und
Stärke-Index umfasst):

```
ALL='overall_rating|layers_view|rating[-_]layers|tournament[_-]conversion|tier_snapshot|subarchetypes|studio[./]memo|prefilter_lists|HEURISTIC_MODEL|simulation_run|simulation_card|import_rubric|SIGNAL_RUBRIC|Gesamtrating|Tierliste|tierliste|commander_lab[./]studio|StudioStore|Stärke-Index|strength_index'
git grep -n -I -E "$ALL" 0fb8fce1 -- <Pfad> | wc -l
```

| Pfad | Dateien im Baum | Treffer |
|---|---:|---:|
| `qualification/` | 7.542 | 0 |
| `src/commander_lab/qualification/` und `tests/qualification/` | 121 | 0 |
| `candidate-qualification/` | 10 | 0 |
| `engine-bridge/` | 259 | 0 |
| `.github/workflows/pb03-runtime-qualification.yml` | 1 | 0 |
| `.github/workflows/production-qualification.yml` | 1 | 0 |
| `WS17_SHA256SUMS` | 7.545 Zeilen | 0 |
| `scripts/run_midgame_capability_probe.py` | 1 | 0 |

Folgerung: **nichts in `qualification/`, PB-03, WS17, `engine-bridge/` oder den älteren Lanes verweist auf ein
Q1-Ziel.** Das Entfernen verlangt dort keine Änderung und darf dort nichts berühren. Weitere, weniger enge
Muster (`\bstudio\b`, `\brating(s)?\b`, `simulation_run`) ergeben in `qualification/`, `src/commander_lab/qualification`,
`tests/qualification`, `engine-bridge/` ebenfalls 0 (`studio`, `rating`) bzw. nur fachfremde Wörter
(„Simulation“ als Java-Begriff `createSimulationForPlayableCalc`, „tier“ als „native tier suite“; Liste per
`git grep -n -I -i -E '\btier(s|list)?\b|\bsimulat(ion|ed)\b' -- qualification candidate-qualification engine-bridge`).
Ein Fehltreffer des `\bSIMULATION\b`-Musters liegt in `candidate-qualification/ws47-successor-v1.0.5/WS47_WORKSTREAM_CONTRACT.md:1`
(Titel „COMMANDER SIMULATION FOUNDRY“): nicht anfassen, kein Bezug.

Die Gegenrichtung ist real: `studio/` verwendet die Qualifikation lesend (siehe 3.2).

### 3.2 Indirekte Sperren (jede ist ein Hindernis oder eine Pflicht-Änderung im selben PR)

| # | Sperre | Beleg | Betrifft | Folge |
|---|---|---|---|---|
| S1 | **Architektur-Ratsche.** Die Cycle-Liste und die erlaubten Importe von `commander_lab.qualification` stehen in einer Fixture; der Test schlägt auch bei **Abnahme** fehl (der neue Wert ist dann in die Fixture zu schreiben, mit `history`-Eintrag) | `tests/architecture/test_layer_boundaries.py:44`, `:122-160`; `tests/fixtures/studio_architecture_baseline.json:15` (`tier_snapshot`), `:16` (`tiers`), `:22-28` (`simulations -> …bridge_launcher: 1`, `paired_comparison -> …: 1`, `doctor`, `launch`, `play`) | K9 (`tier_snapshot` und `tiers` liegen im 13er-Zyklus), K5b (`tiers`), alte Orchestrierer (`simulations`, `paired_comparison`) | Jeder dieser Schnitte ändert die Fixture im selben PR; kein Löschen ohne diese Zeile |
| S2 | **`windows-runtime.yml`** nennt Studio-Dateien beim Namen | `.github/workflows/windows-runtime.yml:111` (`import commander_lab.studio.web, …play, …paired_series, …launch`), `:113` (`pytest tests/unit/test_studio_engine_provisioning.py tests/unit/test_studio_simulations.py`), `:24` (Pfadfilter `tests/unit/test_studio_*.py`) | alte Orchestrierer (`simulations.py`, `paired_series`), K8 | Wer `simulations.py` oder dessen Test entfernt, ändert diesen Workflow (MATERIAL, Workflow-Änderung) |
| S3 | **Pfadfilter mit `deck_variant.py`** | `.github/workflows/studio-human-seat-real-engine.yml:24,56`, `windows-runtime.yml:36` | K7 | `deck_variant.py` bleibt (nur Studio-Aufrufer `builder.prefilter_lists` geht); wird es entfernt, ändern sich zwei Workflows |
| S4 | **`simulation_run` trägt den Siegel-Stand der Bridge** (`bridge_jar_sha256`, `bridge_qualification_state`; „ALIGNED_WITH_SEALED_EPOCH“, `covered_by_sealed_epoch`) | `store.py:339-340`, `store.py:781-786` (Migration 17→18), `builder.py:1472-1522`, `importers.py:1235`, `tests/unit/test_bridge_qualification_and_studio_1401.py:293-348,434-440,665` (Migrationstest, Fail-closed-Rücklesen) | K8 | Streichen der Tabelle verlegt den Träger der Siegel-Deckung; das ist ein Schema- und Beweisthema (K-2/B2), nicht Q1-b. Der Stand steht daneben im Spiel-Protokoll (`card_outcomes.py:352-365`) |
| S5 | **`game_pool.py:138` importiert `play_batch`**; der Pool steht hinter einem Schalter, der Echt-Engine-Beleg ist offen (#1652) | `game_pool.py:48,138`; `paired_comparison.py:877`; `__main__.py:720,1093,1100`; `scripts/check_studio_series_identity.py:50` (`BatchSimulation`), `scripts/measure_throughput_steady_state.py:40` (`BatchRecordingRunner`) | alte Orchestrierer | Erst nach D-2 P5 und Owner-PC-Lauf; nicht in Q1 |

Weitere Hindernisse, die keine Sperre im strengen Sinn sind, aber im selben PR zu ändern sind: das
Antwort-Manifest-Skript (nur zwei Zeilen fallen: `scripts/studio_response_manifest.py:144` `/api/rating-layers` und
`:148` `/api/tournament-conversion`; `:138` `/api/layers` ist eine Datenebene und `:143` `POST /api/strength` bleibt, nur
seine Antwort ändert sich) samt `test_studio_response_manifest.py:42-62` (fest 30 Routen, danach 28); `tests/pytest_shard_weights.json` (veraltete Einträge
kosten nur Balance, `tests/pytest_shards.py:13-15,31`; die Datei ist laut `test_ci_definition_integrity.py:806-811`
eine „benign test change“) und `scripts/verify_required_check_definitions.py:1110` (nennt die Datei nur als
Pfad).

### 3.3 Namensfallen und Fehltreffer (Urteil: behalten)

| Gegenstand | Warum es nicht zum Ziel gehört | Beleg |
|---|---|---|
| `GET /api/layers`, `import_all.layer_overview`, `layer_overview_cached`, Cache-Art `layer_overview` | **Datenebenen** (Zeilen je Importschicht), nicht Rating-Layers | `web.py:685-694`, `web.py:544-553`, `cache.py:169` |
| `source_layers.py` (183 Zeilen) | Quellen-Schichten mit Stand-Datum | `web.py:99-100`, `source_layers.py:151` |
| `tests/unit/test_studio_import_all_layers.py` | „Layers added to `import-all`“: Tagger-Rollen, Rulings; **kein** Rating-Layer | Kopf der Datei, Tests ab Zeile 39 |
| `static/ui.js:284-333` (`dataState`, lokales `layerTable`) und `static/daten.js:87-132,307-356`, `overview.js:234-240` | Datenstand-Tabellen; nur `ui.js:335-384` (`layerNode`, `layerTable`, Export) ist Rating-Layer | siehe K3 |
| `import_all.py:219,306`, `source_layers.py:151`, `daten.js:106` | lokale Variable `layers.append(` / `layers.map(` | Zeilen |
| Komponenten `TOURNAMENT` und `TOURNAMENT_LISTS` | EDHTop16-/Korpus-/TopDeck-Listen, bleiben; nur `TOURNAMENT_CONVERSION` ist Ziel K4 | `strength.py:206-208` |
| `deck_variant.py` (329 Z.), `scripts/deck_variant_prefilter.py` (306), `test_deck_variant_prefilter.py` (331), `test_plan_detectability_wording.py`, `docs/DECK_VARIANT_WORKFLOW.md` | eigenständiger CLI-Weg; nur der Studio-Aufrufer (K7) geht | `builder.py:27`, Importeure: `git grep deck_variant` |
| Datenklasse `HEURISTIC_MODEL` (`store.py:32`) | wird von `castability.py:461`, `evidence.py:471` und `research_import.py:272` weiter gebraucht; nur `prefilter_lists` verwendet sie als Antwort-Etikett (`builder.py:2096,2102`) | Fundstellen |
| `SIMULATION` in `cache.py:86,115,116` und `simulations.py:53` | Cache-Gruppe `Group.SIMULATION` für Tabellen, nicht das Gewicht | `cache.py:86` |
| `SNAPSHOT`/`STALE`-Wörter in `test_ws223_cardinality_regression.py`, `test_xmage_full_game.py`, `test_xmage_variable_player.py`, `test_full_game_series_session.py`, `test_whole_deck_policy_meta.py`, `test_studio_sources.py`, `test_studio_roles_import.py`, `scripts/run_external_b4*.py`, `scripts/data_wave1/db_guard.py` | andere „Snapshot“-Bedeutungen (Engine-Zustand, Quellen, Rollen); **kein** `tier_snapshot` | weite Mustersuche, nicht in K9 |
| „layers“ in `src/commander_lab/qualification/current_boundary/generic_construction.py:222-228`, `midgame_rows.py:1494-1496`, `tests/qualification/…:59,2603`, `engine/rules/full_game_pilot/policy.py:1` | Magic-Regel-Ebenen (6/7b) und „decision layers“ der Engine | Zeilen |
| `"overall"` in `test_studio_card_duel.py:133`, `test_qualify_game_batching.py`, `test_h4_verify_materialization_evidence.py` | fremdes Wort (Verbots-Liste, Gesamturteil eines Gates) | Zeilen |
| Skala „Stärke-Index S bis D“ (`tierliste.html:65`, Schnitte `DEFAULT_CUTS` `strength.py:457`) | der **bleibende** Stufen-Index; nur die zweite Skala geht | Zeilen |

## 4. Was Rubrik v2 und B1/B3 berühren (Berührungspunkte)

- **Rubrik v2 bleibt** (Q1, Issue-Hinweis): `src/commander_lab/studio/card_understanding.py` (237 Z.),
  `scripts/import_card_understanding.py` (228 Z.), Daten `data/card_understanding/` (1,8 MB), Rater-Rohdaten
  `data/research/chulane_rubric_v2_20261118/` (6,0 MB). Tests: `test_studio_strength_followup.py:702-901`
  (Loader und Importer, rund 200 Zeilen) bleiben, nur `:251-701` gehen (6).
- **Einziger heutiger Verbraucher** von `card_understanding`: `overall_rating.py` (Zeilen 6, 45-46, 324, 511-513,
  554-593) und `web.py:38,540` (Cache-Schlüssel `card_understanding.stamp()`). Nach K1 gibt es keinen
  Leser. Die Spalte „Kartenverständnis (Modellurteil)“ aus #1665 Punkt 3 braucht einen neuen Pfad (B3-Komponente
  plus ein Server-Feld oder eine Route). Das ist die erste Abhängigkeit von K1 (7).
- **B1 (#1657, beim Co-Lead):** Dateien `play.py` (`prepare_game`), `card_outcomes.py`, `store.py`,
  `simulations.py`, `web.py` (`/api/outcomes*`), `static/kartenauswertung.js`. Überschnitt mit K1 bis K7: nur
  `web.py` (Textkonflikt beim Routen-Block, keine inhaltliche Abhängigkeit). **Inhaltlich überschneidet B1 mit
  K8** (`store.py`, `simulations.py`), nicht mit Q1-b.
- **B3 (#1659):** Komponente `static/zahl.js` (Vorschlag im Issue), eingesetzt in den Kreislauf-Flächen. Q1-b
  braucht sie für die Rubrik-Spalte (URTEIL) und die Pool-Ansicht „Nutzung n/N“ (K5).
- **Fremd-Änderungen an denselben Dateien:** PR #1669 (Zukauf-Pool, `builder.py`, `app.js`) ist im hier
  gemessenen Stand `0fb8fce1` bereits gemergt; die Zeilenangaben dieses Berichts gelten danach (`app.js` enthält
  K3, `showLayers`/`ratingLayers` Zeilen 2643-2661, und K7, Vorfilter-Knopf 1352-1410; `builder.py` enthält K7
  und K8). Die Abstimmung #1369 (Tierliste v3, `agent:muse`, offen) betrifft `tierliste.js` (K1, K3, K4, K5).
  Das ist vor dem Bau zu klären.

## 5. Inventur je Ziel

Kürzel: `S/` = `src/commander_lab/studio/`, `U/` = `tests/unit/`. Trefferzahlen nach Anhang A:
Zeilen / Dateien, jeweils src (nur `S/`), scripts, tests, docs. Einzelzeilen: Anhang B.

### K1 Gesamtrating v1 (`overall_rating.py`, Umschalter „Gesamtrating“)

| Aspekt | Befund |
|---|---|
| Eigene Dateien | `S/overall_rating.py` **661** Z. |
| Treffer | src 114/6 (davon 20 in der eigenen Datei), tests 98/2, docs 38/9 |
| Quellcode-Verweise | `S/web.py:57` (Import), `:535-542` (`with_overall` um die Antwort von `/api/strength`, Cache-Art `strength_overall`); `S/cache.py:178` (Register) |
| UI | `static/tierliste.js`: Block 188-296 (reine Helfer, 109 Z.), 694-873 (Zellen, Spalten, „Warum hier“, Methode, 180 Z.), 2276-2453 (Umschalter Nutzung/Gesamtrating, 178 Z.), dazu 33 verstreute Zeilen (63-91, 166, 175, 336-338, 890, 918-921, 1007, 1378, 1636, 1757, 1956, 2256); `tierliste.html:37` (`overall-panel`), `:65-66` (`rk-usage`/`rk-overall`); `tierliste.css:183-193` (11 Z.) |
| Routen | keine eigene; Felder `overall`, `overall_meta`, `overall_rank` in der Antwort von `POST /api/strength` (Antwort-Manifest ändert sich) |
| Store | keine Tabelle; Cache-Art `strength_overall` |
| Daten | `data/card_understanding/*.jsonl` bleibt (Rubrik v2) |
| Tests | `U/test_studio_strength_followup.py:251-701` (451 Z.) **löschen**; `:702-901` **behalten** (Rubrik-v2-Loader/Importer); `U/test_studio_static_guards.py:638-1262` (rund 625 Z.; Helfer `_overall_node_prelude`, `_render_node_prelude`, Tests der Umschalter, Zellen, Methode) **löschen**, aber `test_why_box_names_the_further_signals_and_never_shows_zero_percent` (`:782-806`, 25 Z.) **umschreiben**, denn er nutzt `_overall_node_prelude` (`:786`) und prüft `indexShares`, das bleibt |
| Marker-Kopplung | Node-Tests schneiden `tierliste.js` per Textmarken: `js.index("// ---------- overall rating …")` (`static_guards:650`), `"const SORTS = ["` (`:648`), `"// ---------- rating layers"` als Endmarke (`:949,1072`), `"function indexShares(item) {"` (`:616,654`). Beim Streichen bleiben die Marken der Nachbar-Tests zu erhalten oder mit anzupassen |
| Doku | `docs/OWNER_DECISIONS_STUDIO_20261118.md` (9), `docs/research/TIERLISTE_ZWEITER_INDEX_PLAN_20261118.md` (14), `docs/STUDIO_SCOPE.md` (2), `docs/STUDIO_CHARTA_V2.md` (3); `AGENTS.md:29` (G-SIM-Satz). Entscheid-Dokumente und `AGENTS.md`/`STUDIO_SCOPE.md` zieht der Governance-Pfad (#1667) nach, nicht der Builder |
| Sperre | keine direkte; Pflicht: B3 liefert den Ersatzpfad für die Rubrik-v2-Spalte (4) |
| Schätzung Löschumfang | Quelltext **≈ 1.190** (661 + 467 + 33 + 12 + 1 + 2 + 11), Tests **≈ 1.050 bis 1.075** (451 + 600 bis 625). Herkunft: `wc -l`, Zeilenbereiche, Trefferzeilen außerhalb der Blöcke |

### K2 Rubrik-v1-Signale (`research_import.import_rubric`, Komponente `rubric`)

| Aspekt | Befund |
|---|---|
| Eigene Dateien | keine; Teile von `S/research_import.py` (308 Z.): Kopf 10-14, Konstanten 32-48, Lesen/Importieren 163-308 (rund 167 Z.); `import_tagger_roles` (71-162) **bleibt** |
| Treffer | src 78/9, tests 88/7, docs 7/2 |
| Quellcode | `S/strength.py:213,231,249,254,270,336,354,380,393-402 (rubric_value),447,564,959,981`; `S/strength_view.py:468-516` (`rubric_note`, `_rubric_observations`), `:55,553,556,596,1004,1015,1016,1494-1500` (Hinweis bei positivem Gewicht), `:1649-1657` (Panel-Texte), `:2042`; `S/signals.py:177-183` (`SIGNAL_RUBRIC`, `_SD`, `_RATERS`); `S/import_all.py:412,557-560` (Schritt), `S/repo_import.py:210,226` (`find_rubric_folders`); `S/ranking_check.py:108-130,142,396-418,843-884` (`vs_rubric`) |
| UI | `static/tierliste.js:43,1180-1182,1196,1707-1709` (Zeile „Raster-Bewertung“, `subjective`) |
| Store | Zeilen in `card_signal` (Signale `rubric_h_mean`, `rubric_h_sd`, `rubric_raters` je Commander) und je Import eine `source`-Zeile (Datenklasse `HEURISTIC_MODEL`, SHA-256); `strength_profile.spec` JSON mit `weights.rubric`. Ob der Owner-Store solche Zeilen hat: UNKNOWN (Owner-Store nicht geprüft) |
| Daten | `data/research/chulane_rubric_20261114/` (4 Dateien, 276 KB; `summary.csv` 923 Z., `ratings.csv` 2.737 Z.) ist die Eingabe; **nicht** mit Rubrik v2 verwechseln (`chulane_rubric_v2_20261118/`) |
| Tests | `U/test_studio_rubric.py` (416 Z.) **löschen**, Ausnahme `:367-381` (`…every_preset_keeps_the_rubric_at_zero_and_simulation_and_layers_too`): Kern geht in den neuen K6-Test; `U/test_studio_import_from_repo.py:241-281` (`test_from_repo_imports_the_rubric_once…`) **löschen/umschreiben**; `U/test_studio_ranking_check.py:524-581` (`agreement_with_the_rubric`) **umschreiben**, falls `vs_rubric` fällt; `U/test_studio_strength_v3.py:55-75` (Presets mit Rubrik 0) **umschreiben**; `U/test_studio_strength_v3_view.py:392-406` (Hinweis bei Rubrik-Gewicht) **löschen**; `U/test_studio_import_all.py:256` (eine Zeile) anpassen |
| Sperre | keine direkte; Profil-Toleranz (R1) muss vorher stehen |
| Schätzung | Quelltext **≈ 360** (167 + 26 + 70 + 7 + 4 + 75 + 12), Tests **≈ 535** (416 + 41 + 58 + 20) |

### K3 Rating-Layers (`layers.py`, `layers_view.py`, `/api/rating-layers`)

| Aspekt | Befund |
|---|---|
| Eigene Dateien | `S/layers.py` **743** Z., `S/layers_view.py` **105** Z. (zusammen 848) |
| Treffer | src 125/17, scripts 1/1, tests 141/9, docs 5/2 (mit Fehltreffern, 3.3) |
| Importeure | `layers.py` ← `layers_view.py:16` und `strength_view.py` (`import layers_view`, `:36`); `layers.py` importiert `strength` (`:55-72`) |
| Quellcode | `S/strength.py:273-306` (`LAYER_*`, `layer_component`), `:504,548,549,635,729-743,754-760,802,869-871,912-914,1811,1812,2132,2189,2214` (`layer_weights`, `pod_size`, `active_layers`); `S/strength_view.py:158-166` (`LayerSummaryBlock`), `:763-834` (`_layer_result`, `rating_layers`), `:1101-1113,1334,1715-1724,1928,2055-2058,2133` (Antwort, Panel, Presets); `S/web.py:877-897` (Route); `S/cache.py:187` (`answer:rating_layers`); `S/ranking_check.py:65,322-324,517,642` (zählt `active_layers`) |
| UI | `static/tierliste.js`: Block 349-427 (79 Z.), dazu Treffer 350,353,396,398,1209,1570,1725,1800 und weitere (grep, bis 68 Zeilen mit dem weiten Muster); `tierliste.html:62` (`layer-controls`), `tierliste.css:46`; `static/app.js:2476,2643-2661` (`showLayers`, `ratingLayers`, Aufruf `/api/rating-layers`); `static/ui.js:335-384` (`layerNode`, `layerTable`, Export `:384`; **nicht** `:284-333`, das ist Datenstand) |
| Routen | `GET /api/rating-layers` (1 UI-Aufrufer, `app.js:2657`); Felder `layers`, `layer_summary`, `settings.layer_weights`, `settings.pod_size` in `/api/strength` und `/api/strength/presets` |
| Store | keine eigene Tabelle. Liest `playgroup_card_atlas` (`layers_view.py:43-88`), die Tabelle **bleibt**: die Komponente `playgroup_observed` braucht sie. `strength_profile.spec`: Top-Level-Schlüssel `layer_weights`, `pod_size` (`from_stored` ignoriert unbekannte Top-Level-Schlüssel, `strength.py:816-818`) |
| Tests | ganz **löschen**: `U/test_studio_layers.py` (1.098 Z.), `U/test_studio_layers_view.py` (361), `U/test_studio_layer_weight_zero.py` (114; die eine `simulation`-Zeile `:85` zieht in den K6-Test). Anpassen: `U/test_studio_perf_equivalence.py:599,600,668,669` (Routenliste), `U/test_studio_labels.py:102-119` (ruft `rating_layers`), `U/test_studio_strength.py:3330,3331,3361`, `U/test_studio_static_guards.py:585` (`layer-controls`) und die Marke `// ---------- rating layers` (K1) |
| Doku | `docs/STUDIO_DECKBUILDER.md` (3), `docs/research/studio_architecture_counts_20261119.md` (2) |
| Sperre | keine; **UI zuerst, dann Route und Module** (7) |
| Schätzung | Quelltext **≈ 1.150 bis 1.230** (848 + ≈ 300 bis 380: strength 34, strength_view ≈ 96, web 21, ui.js 49, app.js 22, tierliste.js 79 bis 147, Rest), Tests **≈ 1.590** (1.573 + ≈ 15) |

### K4 Turnier-Conversion (`tournament_conversion.py`, Turnier-Panel)

| Aspekt | Befund |
|---|---|
| Eigene Dateien | `S/tournament_conversion.py` **360** Z. |
| Treffer | src 37/7, scripts 1/1, tests 65/10, docs 5/3 |
| Quellcode (Kern A) | `S/web.py:71` (Import), `:920-932` (Route, `answer_cache.file_answer`), `S/answer_cache.py:20` (Text); `static/tierliste.js:2177-2253` (`formatGroupCell`, `renderTournamentConversionPanel`, `loadTournamentConversion`, 77 Z.) plus `:60,173,2094,2432`; `static/daten.js:307-356` (Aufruf `:349`, Übergabe `conversion`) |
| Quellcode (Variante B: Komponente und Signal) | `S/strength.py:172,174,208,226,244,265,317,442,461,561,772,773,954,976` (`TOURNAMENT_CONVERSION`, `MIN_CONVERSION`); `S/strength_view.py:58,545,1000,1697`; `S/signals.py:48,139,168,725-790,1285,1327` (`topdeck_card_conversions`-Import, `SIGNAL_CONVERSION`) |
| Routen | `GET /api/tournament-conversion` (2 UI-Aufrufer); Manifest-Skript `:148` |
| Store | Kern A: keine (liest die CSV unter `data/research/topdeck_*`). Variante B: `card_signal`-Zeilen mit Signal `topdeck_card_conversion`; `strength_profile.spec`: `weights.tournament_conversion`, `min_denominators.conversion` |
| Daten | `data/research/topdeck_20261112/`, `topdeck_20261115/` bleiben; `scripts/compute_topdeck_conversion.py` (311 Z.) und `scripts/collect_topdeck_decks.py:689` sind laut Architektur-Lane „Datensammel-Skripte bleiben“ (`charter_architecture.md` §5): **Widerspruch zu einem Entfernen der Auswertung, Entscheid Co-Lead** |
| Tests | ganz **löschen** (Kern A): `U/test_tournament_conversion_1412.py` (460 Z.). Anpassen: `U/test_role_audit_1413.py:154-182` (UI-Marker, `:177`), `U/test_studio_data_page.py:34-118` (`:44,113`), `U/test_studio_perf_equivalence.py:611,792,814,820`, `U/test_studio_static_guards.py:1610`. Variante B zusätzlich: `U/test_studio_strength.py:2295-2454` (160 Z., acht `test_conversion_*`), `U/test_studio_signals_conversion.py` (309 Z.), `:422,442` und `U/test_studio_strength_v3.py:63` anpassen |
| Doku | `docs/research/DATA_CAPTURE_1377_20261115.md` (2), `DECKBUILDER_COMPARISON_RESEARCH_20261116.md` (2), `docs/research/studio_architecture_counts_20261119.md` (1); der Docstring von `tournament_conversion.py:5-7` verweist auf `docs/TOPDECK.md` §6, diese Datei gibt es auf `main` nicht (`ls docs/TOPDECK.md` schlägt fehl): UNKNOWN, wohin die Definition verschoben wurde |
| Sperre | keine |
| Schätzung | **Kern A:** Quelltext ≈ 475 (360 + 81 + 21 + 8 + Rest), Tests ≈ 470 (460 + ≈ 10). **Variante B zusätzlich:** Quelltext ≈ 90, Tests ≈ 470 (160 + 309) |

### K5 Zweite S–D-Skala (laut B3-Text und Lane: Verbreitungs-Stufe S–D, relative Stufen S–F, „Gleiche Funktion“)

`#1659` nennt fünf Skalen: Stärke-Index S–D (`strength.py:457`), **Verbreitungs-Stufe S–D (`tiers.py:82`)**,
relative Stufen S–F, Gesamtrating, Rubrik H. „Zweite S–D-Skala“ ist damit die Verbreitungs-Stufe. „Gleiche
Funktion“ (`rank_group = "function"`) steht nur in der Lane-Liste, **nicht** im Wortlaut von E15; das ist als
**Entscheid Co-Lead** markiert (10), nicht als Tatsache.

**K5a relative Stufen S–F und „Gleiche Funktion“**

| Aspekt | Befund |
|---|---|
| Treffer | src 84/4, tests 52/7, docs 8/1 |
| Quellcode | `S/strength.py:1991-2114` (`RELATIVE_*`, `relative_tier_for`, `relative_tiers`, 124 Z.), Treffer `:495,624,679,680,793,844,849,855,897,1589,1597,1600,1603,1742,2264,2310,2463` (`rank_group`); `S/strength_view.py:108,110,142-155` (`RelativeTiersInfo`),`:201,1233,1276,1313,1314,1379-1385,1746-1749,1931,1978` |
| UI | `tierliste.html:68-76` (`rank-group-toggle`, `tier-mode-toggle`); `tierliste.js` 26 Zeilen (`:664,682,683,892,917,1202,1317,1802,1817,1823,1964-1966,2095-2119,2344,2413-2422`) |
| Store | `strength_profile.spec`: `rank_group` (Wert `function` bleibt gültig oder wird abgebildet); Browser-Speicher des Umschalters (`TIER_MODE_KEY`) |
| Tests | `U/test_studio_strength.py:3266-3323` (zwei Tests, 58 Z.) **löschen**; `U/test_studio_strength_v3_view.py:499-541` (Nutzlast mit Stabilität, relativen Stufen, Gewichtsfamilien) **umschreiben**; `U/test_studio_tierliste_e0.py` (39 Z.): Relativ-Abschnitt `:15-22` löschen, Stabilität, Gewichtsfamilien, Wurfzug **behalten**; `U/test_role_audit_1413.py:166,172`, `U/test_studio_static_guards.py:604,605` anpassen |
| Schätzung | Quelltext ≈ 200 (124 + 20 + 9 + 26 + ≈ 20), Tests ≈ 130 |

**K5b Verbreitungs-Stufe (S–D-Buchstaben aus `tiers.py`)**

| Aspekt | Befund |
|---|---|
| Treffer | src 34/9, tests 47/11, docs 1/1 |
| Quellcode | `S/tiers.py` (181 Z.): `tier_for_share` (67-78), `card_tier` (79-106), `tiers_for_universe` (107-181), `LEVEL_NAMES` (28-37); `S/universe_view.py:33,368,377,384,461,508,513,745` (`CardSpread.level`, `level_name`); `S/web.py:1103-1117` (`/api/universe/spread`), `:1158`; `S/builder.py:1102,1109`; `S/swap.py:208`; `S/__main__.py:1008` |
| UI | `tierliste.html:52-60` (`spread-filter`); `tierliste.js:471,510,968,1510,2356,2365,2392` |
| Store | keine Buchstaben gespeichert (zur Laufzeit gerechnet). **`universe_profile.spec.min_universe` bleibt als Schwelle** (`universe.py:86,101,236-240`, `universe_view.py:84-85,125-126,174-200`), sonst entfällt `below_min_universe` |
| Teil-Entfernung | die Spalte `level`/`level_name` entfällt; **n/N der Verbreitung (`/api/universe/spread`, `universe.denominator`) bleibt**: das ist die Pool-Ansicht „Nutzung n/N“, die Q1-b behält. `TierParams`/`MODEL_VERSION` (`tiers.py:15-59`) wird von `data_report.py:33,542` und `universe_choice.py:35,245` gelesen |
| Tests | anpassen (Buchstaben-Behauptungen): `U/test_studio_counting.py:267-285` (`spread_levels_carry_their_own_names…`), `U/test_studio_decklist_universe.py:372-416,474-498,850-879`, `U/test_studio_universe_web.py:417-434` und weitere Treffer (Anhang B), `U/test_studio_deck_modules.py:218-254`, `U/test_studio_deck_primer.py:111-143`, `U/test_studio_tokens.py:205-233` (Invariante „berührt nie die Stufen“: **behalten**, nur Namen) |
| Sperre | S1 (`tiers` liegt im Zyklus der Fixture) |
| Schätzung | Quelltext ≈ 160 (≈ 100 + 10 + 30 + 11 + 7 + 3), Tests ≈ 60 |

### K6 Gewicht `simulation` im Tierlisten-Index und Stufe 2

| Aspekt | Befund |
|---|---|
| Quellcode | `S/strength.py:214` (`SIMULATION`), `:232` (in `COMPONENTS`), `:250` (Label), `:271` (Datenklasse `SIMULATED_RESULT`), `:304-307` (`UNCOLLECTED_BY_DESIGN`), `:448,565,960,982,1827,2212`; `S/strength_view.py:1631-1638` (Panel-Label und Hilfetext „Simulationsergebnisse zählen nicht in die Tierliste“); `static/tierliste.js:1181,1182,1709` |
| Stufe 2 | **kein Code**: 0 Treffer in `src`, `scripts`, `tests` für „Stufe 2“/„stage 2“ im Tierlisten-Sinn (Treffer sind „E6 stage 2“ der Engine-Statistik). Stufe 2 steht nur in `docs/STUDIO_SCOPE.md:98` und `docs/OWNER_DECISIONS_STUDIO_20261118.md:115-118,441`; `AGENTS.md:29` (G-SIM-Satz). Diese Texte zieht der Governance-Pfad (#1667) nach |
| Store | `strength_profile.spec.weights.simulation` (jedes gespeicherte Profil trägt den Schlüssel, `to_dict`) |
| Tests | `U/test_studio_simulation_weight_zero.py` (152 Z.): `:19-27` (Gewicht 0 in Default und Presets), `:31-65` (nur eine Komponente ist simulationsabgeleitet), `:66-82` (Gewicht 0 ändert nichts), `:83-117` (Gewicht einstellbar) **umschreiben** zu „der Index kennt keine Simulations-Komponente“ (M1-Probe aus #1665); `:118-143` (`stored_simulation_runs_feed_neither_the_index_nor_the_tier_page_counts`) und `:144-152` **behalten** (Invariante bleibt wahr, liest `simulation_run`, siehe K8); `U/test_deck_plan_pilot_2a.py:627-631`, `U/test_studio_strength.py:360,428,448,1498-1504,1700-1724` (nutzt `SIMULATION: 5.0` als Beispiel einer Komponente ohne Daten, braucht eine andere), `U/test_studio_layers.py:890`, `U/test_studio_rubric.py:372` |
| Sperre | keine; Profil-Toleranz (R1) |
| Schätzung | Quelltext ≈ 40, Tests ≈ 100 (Umschreiben, wenig Nettolöschung) |

### K7 Heuristik-Vorfilter

| Aspekt | Befund |
|---|---|
| Quellcode | `S/builder.py:2054-2105` (`_to_rules_deck` 2054-2078 und `prefilter_lists` 2080-2105, rund 52 Z.), `:27` (Import `compare_variant`); `S/web.py:381-384` (`PrefilterBody`), `:1580-1592` (Route) |
| UI | `static/app.js:1352-1410` (Knopf „Vorfilter & Commander-Castability berechnen“, 59 Z., 1 Aufruf `:1359`) |
| Route | `POST /api/prefilter` (1 UI-Aufrufer) |
| Bleibt | `S/castability.py`, `deck_variant.py`, `scripts/deck_variant_prefilter.py`, `DataClass.HEURISTIC_MODEL`; nur die Studio-Oberfläche geht (Sperre S3, 3.3). Die Lane-Zeilenangabe `builder.py:1605-1630` stimmt auf `main` nicht mehr; richtig ist `:2080-2105` (Stand `0fb8fce1`) |
| Tests | `U/test_studio_builder.py:367-372` und `:586-592` (zwei Behauptungen in größeren Tests) **herauslösen**; `U/test_studio_db_a_1404.py:144-242` (`test_repo_baseline_diff_prefilter_and_seed_idempotency`) **teilen** (Vorfilter-Teil `:182,207,227` raus, Rest bleibt) |
| Schätzung | Quelltext ≈ 130 (52 + 18 + 59 + 1), Tests ≈ 55 |

### K8 `simulation_run` / `simulation_card` (**nicht Q1-b**)

| Aspekt | Befund |
|---|---|
| Treffer | src 38/9, tests 23/8, docs 13/5 |
| Schema | `store.py:334-351` (`simulation_run`, 16 Spalten), `:352-365` (`simulation_card`, 10 Spalten, Index `simulation_card_id`), `:282` und `:612,638,651,652,750` (`commander_binding.kind = 'simulation_run'`), `:781-786` (Migration 17→18), `:1074` (`count`-Liste) |
| Schreiber | `S/simulations.py:596-752` (`save_batch_to_store`, 157 Z.), `S/importers.py:1199-1340` (`_import_one_simulation_file`, `import_simulation_report`) |
| Leser | `S/builder.py:1456-1580` (`card_simulations`, `list_simulations`, `pod_matchup_matrix`), `S/evidence.py:187-215,405-416,528` (Evidenz-Schicht `LAYER_SIMULATED`, summiert über Läufe **ohne Deck-Stand**), `S/data_report.py:490-496`, `S/web.py:566,643,1266-1290`, `S/__main__.py:1022` |
| Cache | Gruppe `SIMULATION`, `cache.py:86,115,116` |
| Tests | `U/test_bridge_qualification_and_studio_1401.py` (Migration, Siegel; Sperre S4), `U/test_studio_simulations.py` (473 Z.; Sperre S2), `U/test_studio_commander_binding.py:100-139`, `U/test_studio_db_d_overview_visual.py:374-435`, `U/test_studio_store.py:884-932`, `U/test_studio_data_report.py:531`, `U/test_studio_perf_equivalence.py:843` |
| Berührung B1 | B1 (#1657) fügt **in dieser Woche** nullable `revision_id`/`deck_hash` zu `simulation_run` hinzu (Claim in #1167, 2026-11-20 05:31). Die Tabelle zu streichen, während B1 hineinschreibt, ist ein Konflikt |
| Urteil | **Sperre für Q1-b.** Tabellen gehören zu Schema 22 (K-2, E15 Q9, Export-Datei, Migration mit Altzeilen in den Experiment-Index). UNKNOWN: Zeilenzahl im Owner-Store (Lane: 0 in der Sandbox, nicht von mir geprüft) |
| Schätzung | Quelltext ≈ 450 (32 + 13 Stellen + 157 + 140 + 60 + 25 + Rest); nicht Teil des Q1-b-Umfangs |

### K9 `tier_snapshot` (Tabelle und Funktion) (**Tabelle nicht Q1-b**)

| Aspekt | Befund |
|---|---|
| Eigene Dateien | `S/tier_snapshot.py` **373** Z. |
| Treffer | src 29/9, tests 52/3, docs 3/3 |
| Verwendung | **Heißer Pfad:** `POST /api/strength` → `S/web.py:523` → `strength_view.compute_with_snapshot` (`:1397-1423`) → `tier_snapshot.read_snapshot`; Route `GET /api/strength/snapshot` (`web.py:846-858`, 0 UI-Aufrufer, 2 Testaufrufe); Schreiber: `S/import_all.py:711-730,789` (nur CLI); `S/ranking_check.py:61,273,628,818,1053`; UI `tierliste.js:1681-1713` (`snapshotBadge`); `S/__main__.py:786` |
| Store | `store.py:476-487` (`tier_snapshot`, 9 Spalten, PK `(commander_name, spec_hash)`), `:1076`; `cache.py:117` (Gruppe `SNAPSHOT`, `:87`) |
| Tests | `U/test_tier_snapshot_1420.py` (650 Z.); `tests/fixtures/studio_architecture_baseline.json:15,44,74` (Zyklus, Sperre S1) |
| Urteil | **Tabelle: K-2.** Die Funktion aus Q1-b zu nehmen ist technisch möglich (`compute_with_snapshot` → `strength_view.compute`), aber ein Eingriff in den Pfad aller Stärke-Antworten; **Entscheid Co-Lead**. Der `spec_hash` ändert sich ohnehin mit jedem Entfernen einer Komponente (R2) |
| Schätzung | Quelltext ≈ 500 (373 + 27 + 12 + 30 + 10 + 15 + 25 + 2), Tests ≈ 650 |

### K10 `memo.py` (**nicht Q1-b**)

| Aspekt | Befund |
|---|---|
| Eigene Dateien | `S/memo.py` **111** Z. |
| Verwendung | `S/universe.py:60,467,1110` (zwei `memo.cached`), `S/import_all.py:31,331` (ein `memo.cached`), `S/cache.py:75,496` (`memo.clear()` in der Aufräum-Funktion), `S/web.py:56,1081,1096` (zwei `memo.clear()`), Text `S/store.py:1054`, `S/builder.py:322` |
| Tests | `U/test_studio_memo.py` (213 Z.), `U/test_studio_cache_groups.py:139` |
| Urteil | Gehört zu D-1 („zwei Anker“, `charter_architecture.md` §4 und §5): die drei `memo.cached`-Stellen müssen erst auf `cache.cached` umgestellt sein, **kein Q1-Gegenstand** |
| Schätzung | Quelltext 111 + 10, Tests 213 |

### K11 `subarchetypes.py`

| Aspekt | Befund |
|---|---|
| Eigene Dateien | `S/subarchetypes.py` **294** Z.; `scripts/subarchetype_analysis.py` **428** Z.; `U/test_studio_subarchetypes.py` **367** Z. |
| Importeure | in `src`: **0**; `scripts/subarchetype_analysis.py:36` und der Test; `scripts/spellbook_combos_fetch.py:39` nennt das Skript nur im Text |
| Doku | `docs/research/SUBARCHETYPE_ANALYSIS_1368_20261115.md` (4), `SPELLBOOK_COMBOS_1378_20261115.md` (1) |
| Store/Routen/Cache | keine |
| Urteil | unabhängiges Blatt; kann mit Skript, Test und Gewichts-Eintrag jederzeit separat gehen. „nach Prüfung §9“ der Charta: den Bezug von „§9“ konnte ich in `STUDIO_CHARTA_V2.md` nicht finden (der Satz steht in §4; in `charter_architecture.md` ist §9 die Liste „Wenig kann sofort weg“): UNKNOWN, welche Prüfung gemeint ist |
| Schätzung | Quelltext 294 + 428, Tests 367 |

### Alte Orchestrierer (nach D-2 P5) (**nicht Q1**)

`S/simulations.py` (1.604 Z.: `plan_chunks` `:753`, `BatchSimulation` `:773`, `SimulationBatchManager` `:1373`),
`S/play_batch.py` (231 Z.), Kommando `play-batch` (`__main__.py:337,717-720,1093`), `S/paired_comparison.py`
(1.172 Z., von `paired_series.py` genutzt: bleibt). Routen `POST /api/simulations/batch` und folgende
(`web.py:1287-1373`). Sperren S1, S2, S5. Erst mit D-2 P5 und dem Owner-PC-Lauf; Q1-b fasst sie nicht an.

## 6. Testurteile (jede Datei mit Treffer)

Urteile: **löschen** (ganze Datei), **Abschnitt löschen**, **umschreiben**, **anpassen** (einzelne Zeilen),
**behalten** (Fehltreffer oder Invariante bleibt wahr). Bereiche sind Zeilen Anfang-Ende.

| Datei | Ziel | Urteil | Begründung |
|---|---|---|---|
| `test_studio_layers.py` (1.098) | K3 | löschen | testet `layers.py` rein; Zeilen 1034-1035 lesen den Quelltext von `layers.py`/`layers_view.py` |
| `test_studio_layers_view.py` (361) | K3 | löschen | Route `/api/rating-layers`, Layer-Einstellungen im Panel |
| `test_studio_layer_weight_zero.py` (114) | K3, K6 | löschen | Layer-Gewichte entfallen; Aussage zu `simulation` (`:85`) zieht in den K6-Test |
| `test_tournament_conversion_1412.py` (460) | K4 | löschen | Modul und Route |
| `test_studio_rubric.py` (416) | K2 | löschen | Rubrik-v1-Import und -Komponente; `:367-381` Kern in K6-Test; `:182-194` liest `data/research/chulane_rubric_20261114/` |
| `test_studio_strength_followup.py` (901) | K1 | Abschnitt 251-701 löschen; 702-901 behalten; Rest unberührt | `:251-701` Gesamtrating; `:702-901` Rubrik-v2-Loader/Importer; Hilfen `_row`, `SCORES` (`:255-285`) werden von `:705-790` mitbenutzt: beim Löschen verschieben |
| `test_studio_static_guards.py` (1.817) | K1, K3, K5 | Abschnitt 638-1262 löschen, `:782-806` umschreiben; `:559-610` und `:1596-1600` anpassen | Gesamtrating-Node-Tests; Marker-Kopplung (siehe K1) |
| `test_studio_simulation_weight_zero.py` (152) | K6 | umschreiben; `:118-152` behalten | M1-Probe aus #1665 |
| `test_studio_strength.py` (3.367) | K4B, K5a, K6, K3 | `:2295-2454` (K4B) löschen; `:3266-3323` (K5a) löschen; `:394-462`, `:1495-1521`, `:1685-1730`, `:3324-3367` anpassen; Rest behalten | Komponenten-Listen, Presets, Gewichts-Familien |
| `test_studio_strength_v3.py` (689) | K2, K4, K5a | `:55-75` umschreiben, `:121-145` behalten und erweitern | `:121-145` („Profil vor v3 gespeichert“) ist die Vorlage für den Toleranztest R1 |
| `test_studio_strength_v3_view.py` (541) | K2, K5a | `:392-406` löschen; `:499-541` umschreiben | |
| `test_studio_ranking_check.py` (580), `…_v3.py` (330) | K2, K3, K9 | `:524-581` umschreiben; `…_v3` anpassen (`tier_snapshot`, `layers`) | `ranking_check` bleibt als CLI |
| `test_studio_import_all.py` (331) | K2 | anpassen (`:256`) | Rubrik-Signal als Datenebene |
| `test_studio_import_all_layers.py` | – | **behalten** | Namensfalle (3.3) |
| `test_studio_import_from_repo.py` (313) | K2 | `:241-281` löschen/umschreiben | `find_rubric_folders` |
| `test_studio_signals_conversion.py` (309) | K4B | behalten bis Entscheid K4B; sonst löschen | Signal-Import `topdeck_card_conversions` |
| `test_studio_perf_equivalence.py` (1.527) | K3, K4, K8 | anpassen (`:599,600,611,668,669,792,814,820`) | Routenlisten; `:843` (K8) behalten |
| `test_studio_response_manifest.py` (397) | alle Routen | anpassen (`:42-62`) | fest 30 Routen; gleichzeitig `scripts/studio_response_manifest.py:144,148` (nicht `:138`, das ist `/api/layers`) |
| `test_studio_cache_groups.py` (475) | K1, K3, K6 | anpassen (`_kinds_in_source` `:109-158`: `strength_overall`, `answer:rating_layers`); `:64-98` (Tabelle→Gruppe) nur bei K8/K9 | |
| `test_studio_labels.py` (200) | K3 | anpassen (`:102-119`) | ruft `rating_layers` |
| `test_studio_data_page.py` (198), `test_role_audit_1413.py` (182) | K4, K5a | anpassen | UI-Marker der Seiten |
| `test_studio_tierliste_e0.py` (39) | K5a | umschreiben | nur der Relativ-Abschnitt entfällt |
| `test_studio_counting.py` (494), `test_studio_decklist_universe.py` (1.494), `test_studio_universe_web.py` (1.499) | K5b | anpassen | Stufenbuchstaben der Verbreitung; n/N bleibt |
| `test_studio_deck_modules.py`, `test_studio_deck_primer.py`, `test_studio_tokens.py`, `test_studio_data_report.py` (K5b-Zeile `:170`), `test_studio_scope_per_commander.py` | K5b | behalten, Namen anpassen | Invariante „berührt nie die Stufen“ bleibt wahr |
| `test_studio_builder.py` (1.443), `test_studio_db_a_1404.py` (446) | K7 | anpassen (herauslösen) | siehe K7 |
| `test_deck_variant_prefilter.py`, `test_plan_detectability_wording.py`, `test_studio_castability.py` | K7 | **behalten** | Namensfalle: CLI-Weg und Datenklasse bleiben |
| `test_deck_plan_pilot_2a.py` (632) | K6 | anpassen (`:627-631`) | |
| `test_tier_snapshot_1420.py` (650) | K9 | in Q1-b nicht anfassen | Tabelle K-2 |
| `test_studio_memo.py` (213) | K10 | in Q1-b nicht anfassen | D-1 |
| `test_studio_subarchetypes.py` (367) | K11 | löschen mit `S/subarchetypes.py` und Skript | |
| `test_studio_simulations.py`, `test_bridge_qualification_and_studio_1401.py`, `test_studio_commander_binding.py`, `test_studio_db_d_overview_visual.py`, `test_studio_store.py` | K8 | **behalten** | Sperren S2, S4 |
| `tests/architecture/test_layer_boundaries.py` + `tests/fixtures/studio_architecture_baseline.json` | K5b, K9, Orchestrierer | Fixture-Zeile mit `history`-Eintrag im jeweiligen PR | Sperre S1 |
| `tests/pytest_shard_weights.json` | alle | veraltete Einträge dürfen bleiben; Bereinigung optional | kostet nur Balance |
| `test_ws223_…`, `test_xmage_full_game.py`, `test_xmage_variable_player.py`, `test_full_game_series_session.py`, `test_whole_deck_policy_meta.py`, `test_studio_sources.py`, `test_studio_roles_import.py`, `test_qualify_game_batching.py`, `test_h4_verify_materialization_evidence.py`, `test_studio_card_duel.py`, `tests/qualification/test_pre_freeze_contract_successor.py`, `test_current_boundary_dimension_admission.py`, `test_ws224_name_canary.py` | – | **behalten** | Fehltreffer (3.3) |

## 7. Abhängigkeiten und Reihenfolge

Grundsatz: **Oberfläche zuerst, dann Route, dann Modul.** Wer zuerst die Oberfläche entfernt, lässt das Backend
unbenutzt, aber lauffähig; das spätere Löschen von Route und Modul kann keinen UI-Aufruf mehr brechen.

```
Rubrik-v2-Ersatzpfad (B3 / eigener Pfad) ──► K1
Profil-Toleranz (R1) ──► K2, K6, K4B (Schlüssel in weights/min_denominators), K5a (Wert rank_group)
K1 (rk-overall) ──► K5 (gleiche Elemente in tierliste.html/js: Umschalter-Leiste)
B3 (Zahlen-Vertrag, Pool-Ansicht Nutzung n/N) ──► K5
K3-UI ──► K3-Backend;  K4-UI ──► K4-Route/Modul ──► K4B
K7 unabhängig;  K11 unabhängig
K8, K9, K10, Orchestrierer: außerhalb Q1-b (K-2, K-2, D-1, D-2 P5)
```

- **Was zuerst B3 braucht:** K1 (Rubrik-Spalte, URTEIL) und K5 (Pool-Ansicht mit Klassen). Alle anderen
  Ziele nicht.
- **Was zuerst B1 braucht:** keines der Ziele K1 bis K7 inhaltlich. B1 berührt `web.py` (Merge-Reihenfolge
  beachten), `store.py` und `simulations.py` (nur K8). #1665 nennt B1 als Abhängigkeit; für die Ziele dieser
  Inventur gibt es dafür keinen Beleg außer K8, das hier ausgeschlossen wird.
- **Gemeinsame Quelldateien** (Reihenfolge erzwingt kleine Teilschritte): `strength.py` (K2, K3, K4B, K5a, K6),
  `strength_view.py` (alle), `tierliste.js` (K1, K3, K4, K5a, K5b), `web.py` (K1, K3, K4, K5b, K7).
- **K2, K6 und K4B sind eine Familie:** sie ändern `COMPONENTS`, `DEFAULT_WEIGHTS`, Presets und Panel-Texte
  gemeinsam und den gespeicherten Profil-Schlüssel `weights.*`.
- **Folge-Paket #1666 (Q1-c):** hängt an K6 (der Index darf die Simulation nicht mehr kennen, sonst gibt es
  zwei Orte) und an B1/B2/B3; die Evidenz-Schicht `evidence.LAYER_SIMULATED` (`evidence.py:405-416`) summiert
  heute über Läufe ohne Stand: Q1-c liest je Stand über B1, nicht aus `simulation_run`.

## 8. Risiken (nur benannt, nichts geändert)

| # | Risiko | Beleg | Wirkung |
|---|---|---|---|
| R1 | **Gespeicherte Profile werden ungültig.** Unbekannte Komponenten-Schlüssel in `weights` werfen `ValueError("unknown component")`; ebenso unbekannte `min_denominators`-Schlüssel (`strength.py:687-689`) und `layer_weights`-Namen (`:732`); `from_stored` ignoriert nur **Top-Level**-Schlüssel (`:816-818`) | `strength.py:653`, `:785-787`, `strength_view.py:1453-1486` (`_entry` markiert dann `valid: false`) | Jedes bisher gespeicherte Profil kann nach dem Streichen von `rubric`, `simulation`, `tournament_conversion` ungültig werden; ob der Owner-Store Profile enthält: UNKNOWN. Browser-Einstellungen (`studio.strength.settings`) fallen in `tierliste.js` auf die empfohlenen Werte zurück (Kommentar „remembered settings no longer valid“ nahe `:1975`), `app.js:2680` ebenso. Kein Schema-Bump nötig, aber eine Toleranzregel zuerst |
| R2 | **`tier_snapshot.spec_hash` ändert sich** mit jeder entfernten Komponente (`tier_snapshot.py:41-45`, hasht die Einstellungen) | `tier_snapshot.py` | Alte Snapshots gelten als veraltet (`STALE`-Weg, `STALE_NOTICE`); Zeilen im Owner-Store: UNKNOWN |
| R3 | **`rank_group = "function"`** ist ein gespeicherter Wert (`from_dict`), und eine ältere Browser-Einstellung wird bereits in die Anzeige „Gleiche Funktion“ gewandelt (`tierliste.js` nahe `:1960-1970`) | `strength.py:826-870`, `tierliste.js` | Entfällt „Gleiche Funktion“, müssen alte Werte entweder gültig bleiben oder auf `pool` abgebildet werden |
| R4 | **`min_universe`** steckt im gespeicherten `universe_profile.spec` und bleibt Schwelle | `universe.py:86,236-240` | Beim Entfernen der Buchstaben darf die Schwelle nicht mit verschwinden |
| R5 | **Antwort-Manifest** vergleicht byte-genau (kein Feldvergleich) | `studio_response_manifest.py:655-675` | `/api/strength`, `/api/rating-layers`, `/api/tournament-conversion`, `/tierliste.html`, ggf. `/api/pool` ändern sich absichtlich; die Abnahme „bis auf die entfernten Felder“ braucht einen Feld-Schlüsselvergleich (kleines neues Hilfsmittel oder Testfall), sonst nicht prüfbar |
| R6 | **Marker-gekoppelte Node-Tests** schneiden `tierliste.js` per Textmarken | `test_studio_static_guards.py:616-654,688-697,812-1072`; `test_studio_counting.py:473-490` (`strengthBox`, `groupLabel`) | Jede Teil-Löschung in `tierliste.js` kann Nachbar-Tests brechen; Marken erhalten oder gemeinsam ändern |
| R7 | **Rubrik v2 verwaist** (kein Leser nach K1) | 4 | Spalte „Kartenverständnis“ braucht den Ersatzpfad; sonst unbenutzte Datei und kein Produkt |
| R8 | **Cache-Register** (`cache.py`) und Test `_kinds_in_source` prüfen Arten gegen den Quelltext | `cache.py:178,187`; `test_studio_cache_groups.py:109-158` | Entfernte Arten müssen im selben PR verschwinden (#1665 fordert das ohnehin) |
| R9 | **Fremd-Änderungen** an `app.js`, `builder.py`, `tierliste.js`: Abstimmung #1369 offen; neue PRs verschieben die Zeilenangaben | 4 | Konflikte; vor dem Bau Stand prüfen, Zeilenzahlen mit Anhang A neu messen |
| R10 | **Windows-Lauf** nennt `test_studio_simulations.py` beim Namen | `windows-runtime.yml:24,113` | Löschen von Tests unter `tests/unit/test_studio_*.py` ändert den Pfadfilter nicht, die benannte Datei darf aber nicht verschwinden |

Nichts davon ändert `SCHEMA_VERSION`; R1 bis R4 betreffen gespeicherte Werte, R2 abgeleitete Zeilen.

## 9. Empfehlung für den Schnitt von #1665 (Entfernen) und #1666 (Evidenz R0–R3)

**Umfang Q1-b nach dieser Inventur: K1 bis K7.** Nicht dazu: K8, K9 (Tabelle), K10, alte Orchestrierer.
K11 optional als eigener Mini-PR.

**Zeilenumfang (Schätzung, Summe der Schätzungen in 5):**

| Ziel | Quelltext | Tests | Summe |
|---|---:|---:|---:|
| K1 Gesamtrating | ≈ 1.190 | ≈ 1.060 | ≈ 2.250 |
| K3 Rating-Layers | ≈ 1.190 | ≈ 1.590 | ≈ 2.780 |
| K4 Turnier Kern A | ≈ 475 | ≈ 470 | ≈ 945 |
| K4B Komponente/Signal (optional) | ≈ 90 | ≈ 470 | ≈ 560 |
| K2 Rubrik v1 | ≈ 360 | ≈ 535 | ≈ 895 |
| K5a/K5b zweite Skala | ≈ 360 | ≈ 190 | ≈ 550 |
| K6 Gewicht `simulation` | ≈ 40 | ≈ 100 | ≈ 140 |
| K7 Vorfilter | ≈ 130 | ≈ 55 | ≈ 185 |
| **K1 bis K7 ohne K4B** | **≈ 3.745** | **≈ 4.000** | **≈ 7.750** |

Der Grenzwert aus dem Issue (etwa 1.500 Zeilen Diff) ist damit überschritten. Der Diff besteht überwiegend aus
Löschungen ganzer Dateien (1.869 Zeilen Quelltext und 2.449 Zeilen Tests per `wc -l`), was den Prüfaufwand
senkt, aber nicht die MATERIAL-Einstufung (UI-Texte zu Rating, über 300 Zeilen).

**Vorgeschlagene PR-Teilung** (jeder PR: Teststand grün, kein Zwischenstand mit totem UI-Aufruf):

| PR | Inhalt | Schätzung | Braucht vorher |
|---|---|---:|---|
| Q1-b0 | Profil-Toleranz (`from_stored` ignoriert unbekannte `weights`-/`min_denominators`-/`layer_weights`-Schlüssel, `rank_group="function"` bleibt gültig oder wird abgebildet) mit Test nach dem Muster `test_studio_strength_v3.py:121-145` | ≈ 100 | nichts |
| Q1-b1 | K7 Vorfilter und K4 Kern A (Turnier-Panel, Route, Modul; UI zuerst) | ≈ 1.130 | nichts |
| Q1-b2 | K3 in zwei Commits: UI (tierliste, app.js, ui.js) dann Route, Module, Tests | ≈ 2.780 (überwiegend ganze Dateien) | nichts; Abstimmung #1369 für `tierliste.js` |
| Q1-b3 | K1 Gesamtrating | ≈ 2.250 | **B3 oder Ersatzpfad für die Rubrik-v2-Spalte** |
| Q1-b4 | K2 Rubrik v1 + K6 Gewicht `simulation` (+ K4B, falls entschieden) | ≈ 1.035 (+ 560) | Q1-b0 |
| Q1-b5 | K5a/K5b: eine Stufen-Skala, Pool-Ansicht „Nutzung n/N“ | ≈ 550 | B3, Q1-b3 (gleiche Umschalter-Leiste) |

Alternative, falls sechs PRs zu viel sind: b1 und b4 zusammen, b3 und b5 zusammen (zwei PRs über 2.000 Zeilen,
dann Prüfung per Löschliste). Empfehlung aber: sechs.

**Abnahme-Hinweise zu #1665 (aus der Inventur):**

- „Antwort-Manifest unverändert bis auf entfernte Felder“ ist nur mit einem Feld-Schlüsselvergleich prüfbar (R5).
- „`/api/rating-layers` gibt 404“ ist machbar (Route fällt, FastAPI antwortet 404).
- „Seite zeigt genau eine Stufen-Skala (Test)“: die Test-Fläche ist `tierliste.html` und `tierliste.js`;
  die Marker-Kopplung (R6) ist dabei zu beachten.
- Die Mutationsproben M1 bis M3 aus #1665 greifen an K6 (M1) und K1/B3 (M2, M3); M2/M3 gehören zu Q1-b3.

**Für #1666 (Q1-c, Evidenz R0–R3):**

1. Erst nach K6 (Q1-b4): sonst gibt es zwei Orte, an denen die Simulation „im Index“ steht.
2. **Nicht auf `simulation_run`/`simulation_card` aufsetzen** (K8: Schema 22 streicht sie, B1 schreibt gerade
   hinein), sondern auf die je-Stand-Auswertung von B1 (`card_outcomes`). So kann K-2 die Tabellen später ohne
   Änderung an Q1-c streichen.
3. Die heutige Evidenz-Schicht `evidence.LAYER_SIMULATED` (`evidence.py:405-416,528`) summiert über Läufe ohne
   Stand; sie ist die bestehende Fläche, die Q1-c ersetzt oder umhängt (Berührung, nicht Entfernung).
4. Holm liegt in `src/commander_lab/decision_statistics.py:130` (`holm_adjust`) und wird von
   `engine/rules/full_game_comparison.py:34` genutzt; in `studio/` gibt es 0 Treffer außer einem Text in
   `card_trend.py` (Befehl: `git grep -n -i holm -- src/commander_lab/studio`). Das bestätigt den Lane-Befund aus
   #1666; `studio/` importiert aus `engine/rules` bereits (`__main__.py:570`), die Wiederverwendung hat also
   einen Vorgänger.
5. Siegel-Deckung für R3 („Bridge durch Siegel gedeckt“) liest `commander_lab.bridge_qualification` (nur lesend;
   `card_outcomes.py:29`, `data_report.py:655`); das ist kein Eingriff in `qualification/`.

## 10. UNKNOWN und Entscheidungen für den Co-Lead

| # | Punkt | Optionen / Empfehlung |
|---|---|---|
| E1 | Turnier-Conversion: nur Modul, Route, Panel (Kern A, wie Lane und Issue) oder auch Komponente und Signal-Import (K4B)? | Empfehlung: Kern A in Q1-b1; K4B mit K2/K6 in Q1-b4, weil dieselbe Profil-Toleranz greift. `scripts/compute_topdeck_conversion.py` bleibt (Lane: Datensammel-Skripte bleiben) |
| E2 | „Zweite S–D-Skala“: Verbreitungs-Buchstaben (S–D, `tiers.py:82`) und relative S–F; und „Gleiche Funktion“? | Empfehlung: Buchstaben und relative Stufen entfernen, n/N der Verbreitung behalten; „Gleiche Funktion“ als Einstellung entfernen **nur** wenn der Co-Lead es als Teil von Q1 liest (steht nicht im Wortlaut E15) |
| E3 | Rubrik-v1-Daten `data/research/chulane_rubric_20261114/` (276 KB, 2 Tabellen): löschen oder als Archiv behalten? | Empfehlung: behalten (Forschungsdaten, kein Code); nur der Importer geht. Entscheidung Co-Lead |
| E4 | Funktion `tier_snapshot` schon in Q1-b entfernen (nur Funktion, nicht die Tabelle)? | Empfehlung: nein, mit K-2 gemeinsam; Hot-Path-Eingriff ohne Gewinn für Q1 |
| E5 | Ersatzpfad für Rubrik v2 (Server-Feld oder Route) vor Q1-b3: in B3 oder eigenes Paket? | Empfehlung: kleines Server-Feld in Q1-b3 selbst, Anzeige über B3 |
| UNKNOWN-1 | Inhalt des Owner-Stores (Zeilen in `tier_snapshot`, `simulation_run`, `strength_profile`, `card_signal` Rubrik/Conversion) | nicht geprüft; E15 Q9: der Owner liefert später eine Export-Datei, nie ins Repo |
| UNKNOWN-2 | Bezug von „(nach Prüfung §9)“ bei `subarchetypes.py` in der Charta | nicht auffindbar (K11) |
| UNKNOWN-3 | Ob die Hilfen `_row`/`SCORES` in `test_studio_strength_followup.py:255-285` nach dem Löschen von `:251-701` noch von `:705-790` gebraucht werden | ja nach Sicht des Quelltextes (Verwendung in `:706,707,718-724,743,762-780`); beim Bau verschieben |
| UNKNOWN-4 | Verhalten der geänderten Seiten im Browser, Windows-Lauf, Echt-Engine | NOT_RUN |

## Anhang A: Kommandos (Stand `0fb8fce1`)

Muster (alle ERE; `git grep -n -I -E "<Muster>" -- <Pfad>`):

```
K1  overall_rating|with_overall|overall_meta|OVERALL_|overall_rank|strength_overall|rk-overall|overall-panel|Gesamtrating|overallOf|overallActive|overallColumns|overallWhyBox|overallHint|overallMeta
K2  SIGNAL_RUBRIC|import_rubric|read_rubric|find_rubric_folders|rubric_folder_key|RUBRIC_COMMANDERS|RUBRIC_SUMMARY|RUBRIC_COLUMNS|rubric_note|_rubric_observations|rubric_value|strength\.RUBRIC|\bRUBRIC\b|RUBRIC_H|rubric_h_mean|SUBJECTIVE_RATING|chulane_rubric_2026
K3  layers_view|rating[-_]layers|LAYER_KEYS|LAYER_LABELS|LAYER_SIGNALS|layer_component|layer_weights|DEFAULT_LAYER_WEIGHTS|active_layers|LAYER_PREFIX|classify_pod_scaling|compute_layers|LayerCard|AtlasRecord|layerTable|showLayers|ratingLayers|layer-controls|layerMetas|import layers|studio\.layers|[(, ]layers\.[a-z_]+\(
K4  tournament_conversion|tournament-conversion|TOURNAMENT_CONVERSION|MIN_CONVERSION|analyze_commander_conversion|renderTournamentConversionPanel|loadTournamentConversion
K5a relative_tier|RelativeTier|RELATIVE_|tier_mode|tierMode|tm-rel|tm-abs|rank_group|rankGroup|rg-function|rg-pool|funcMode
K5b tier_for_share|card_tier\b|tiers_for_universe|LEVEL_NAMES|counted-spread|spread-filter|api/universe/spread|pool_spread
K6  strength\.SIMULATION|\bSIMULATION\b|UNCOLLECTED_BY_DESIGN|weights\.simulation|component === "simulation"|key !== "simulation"
K7  prefilter_lists|PrefilterBody|api/prefilter
K8  simulation_run|simulation_card
K9  tier_snapshot|latest_snapshot_summary|compute_with_snapshot|snapshotBadge
K10 memo\.(cached|clear)|import memo|[ ,]memo,|studio import .*memo
K11 subarchetypes|subarchetype_analysis
```

Zahl je Bereich, gegen den festen Commit (so enthält der Baum diesen Bericht nicht, und spätere Änderungen an `main` ändern nichts): `git grep -n -I -E "<Muster>" 0fb8fce1 -- src/commander_lab/studio | wc -l` (Zeilen) und `git grep -l -I -E "<Muster>" 0fb8fce1 -- src/commander_lab/studio | wc -l` (Dateien); entsprechend für `scripts`, `tests` und `docs`. Die Ausgabe trägt das Präfix `0fb8fce1:`; die Zählung ist davon unabhängig. Zeilenzahlen einer Datei: `git show 0fb8fce1:<Datei> | wc -l`.

Ergebnis (Zeilen / Dateien):

| Ziel | src (`studio/`) | scripts | tests | docs |
|---|---:|---:|---:|---:|
| K1 | 114 / 6 | 0 / 0 | 98 / 2 | 38 / 9 |
| K2 | 78 / 9 | 0 / 0 | 88 / 7 | 7 / 2 |
| K3 | 125 / 17 | 1 / 1 | 141 / 9 | 5 / 2 |
| K4 | 37 / 7 | 1 / 1 | 65 / 10 | 5 / 3 |
| K5a | 84 / 4 | 0 / 0 | 52 / 7 | 8 / 1 |
| K5b | 34 / 9 | 0 / 0 | 47 / 11 | 1 / 1 |
| K6 | 22 / 6 | 0 / 0 | 22 / 7 | 2 / 1 |
| K7 | 6 / 3 | 0 / 0 | 7 / 2 | 1 / 1 |
| K8 | 38 / 9 | 0 / 0 | 23 / 8 | 13 / 5 |
| K9 | 29 / 9 | 0 / 0 | 52 / 3 | 3 / 3 |
| K10 | 10 / 4 | 0 / 0 | 22 / 2 | 0 / 0 |
| K11 | 0 / 0 | 5 / 2 | 2 / 2 | 6 / 3 |

Weitere Kommandos:

```
git rev-parse 0fb8fce1                               # 0fb8fce19a3c88167bb9a7c6188aff9de00dee1c
# die folgenden Zeilen mit ausgechecktem Stand 0fb8fce1 ausführen (git checkout 0fb8fce1)
wc -l src/commander_lab/studio/{overall_rating,layers,layers_view,tournament_conversion,tiers,tier_snapshot,memo,subarchetypes,simulations,play_batch,paired_comparison}.py
grep -cE '^\s+@app\.(get|post|put|delete|patch)\(' src/commander_lab/studio/web.py            # 117
git grep -n -I -E "$ALL" 0fb8fce1 -- qualification src/commander_lab/qualification tests/qualification candidate-qualification engine-bridge .github/workflows/pb03-runtime-qualification.yml .github/workflows/production-qualification.yml WS17_SHA256SUMS   # 0 (Abschnitt 3.1)
git grep -n -E "commander_lab\.qualification" 0fb8fce1 -- src/commander_lab/studio        # Gegenrichtung (S1)
git grep -n -i holm 0fb8fce1 -- src/commander_lab/studio                                   # 1 Treffer, nur Text (card_trend.py)
```

## Anhang B: Fundstellen je Ziel (Datei [Anzahl]: Zeilen; `S/` = `src/commander_lab/studio/`, `U/` = `tests/unit/`)

Kürzung: bis 60 Zeilen je Datei im Quelltext, bis 12 in Tests (`…` = weitere; der Befehl liefert alle).
Fehltreffer (3.3): K3 `S/import_all.py:219,306`, `S/source_layers.py:151`, `S/static/daten.js:106`;
K6 `S/cache.py:86,115,116`, `S/simulations.py:53`, `U/test_studio_cache_groups.py:85`.

**K1_gesamtrating**

```
src/scripts:
  S/cache.py [1]: 178
  S/overall_rating.py [20]: 1,8,10,49,52,62,89,170,224,243,335,362,478,481,542,550,561,572,586,629
  S/static/tierliste.css [6]: 183,184,185,186,187,193
  S/static/tierliste.html [2]: 37,66
  S/static/tierliste.js [82]: 63,71,80,81,82,83,84,89,90,91,166,188,189,205,223,226,236,242,244,268,336,337,338,694,695,697,700,701,702,705,707,709,713,715,716,717,719,722,724,729,737,742,747,756,762,768,770,771,775,783,784,785,786,789,795,824,826,828,831,835,…
  S/web.py [3]: 57,540,541
tests:
  U/test_studio_static_guards.py [37]: 650,674,685,690,699,702,704,745,812,832,867,882,…
  U/test_studio_strength_followup.py [61]: 19,251,289,299,301,308,310,322,327,328,334,343,…
```

**K2_rubrik_v1**

```
src/scripts:
  S/import_all.py [2]: 412,560
  S/overall_rating.py [1]: 105
  S/ranking_check.py [2]: 399,400
  S/repo_import.py [1]: 226
  S/research_import.py [28]: 10,11,34,35,36,163,165,167,169,172,178,179,192,195,199,201,208,211,221,228,245,248,255,258,261,262,268,273
  S/signals.py [5]: 177,180,181,182,183
  S/static/tierliste.js [1]: 43
  S/strength.py [17]: 213,231,249,254,270,336,354,380,393,394,397,400,402,447,564,959,981
  S/strength_view.py [21]: 55,468,478,485,490,493,496,502,508,553,556,596,1004,1015,1016,1494,1649,1655,1656,1657,2042
tests:
  U/test_studio_import_all.py [1]: 256
  U/test_studio_import_from_repo.py [4]: 245,264,270,271
  U/test_studio_ranking_check.py [5]: 534,546,550,562,567
  U/test_studio_rubric.py [71]: 31,41,80,81,86,96,115,120,121,124,128,129,…
  U/test_studio_simulation_weight_zero.py [1]: 44
  U/test_studio_strength.py [2]: 427,447
  U/test_studio_strength_v3.py [4]: 70,71,72,73
```

**K3_layers**

```
src/scripts:
  scripts/studio_response_manifest.py [1]: 144
  S/answer_cache.py [1]: 3
  S/cache.py [1]: 187
  S/import_all.py [2]: 219,306
  S/layers.py [19]: 9,14,57,58,63,242,323,325,382,398,533,584,587,663,678,679,680,695,740
  S/layers_view.py [8]: 4,16,45,51,71,94,95,98
  S/ranking_check.py [6]: 65,322,323,324,517,642
  S/source_layers.py [1]: 151
  S/static/app.css [1]: 228
  S/static/app.js [10]: 2476,2643,2645,2647,2652,2656,2657,2658,2659,2661
  S/static/daten.js [1]: 106
  S/static/tierliste.css [2]: 46,88
  S/static/tierliste.html [1]: 62
  S/static/tierliste.js [8]: 350,353,396,398,1209,1570,1725,1800
  S/static/ui.js [6]: 305,307,314,327,369,384
  S/strength.py [34]: 79,274,279,280,281,287,293,299,301,504,548,549,635,729,730,731,736,743,754,755,758,760,802,869,870,871,912,913,914,1811,1812,2132,2189,2214
  S/strength_view.py [20]: 36,775,776,782,801,1101,1107,1111,1113,1334,1715,1716,1717,1719,1724,1928,2055,2056,2058,2133
  S/web.py [4]: 877,878,891,893
tests:
  tests/pytest_shard_weights.json [1]: 293
  U/test_studio_labels.py [1]: 104
  U/test_studio_layer_weight_zero.py [7]: 16,81,83,84,86,105,106
  U/test_studio_layers.py [97]: 14,15,16,17,18,19,470,494,498,503,505,522,…
  U/test_studio_layers_view.py [26]: 15,100,117,125,145,183,204,254,259,265,266,268,…
  U/test_studio_perf_equivalence.py [4]: 599,600,668,669
  U/test_studio_rubric.py [1]: 373
  U/test_studio_static_guards.py [1]: 585
  U/test_studio_strength.py [3]: 3330,3331,3361
```

**K4_turnier**

```
src/scripts:
  scripts/studio_response_manifest.py [1]: 148
  S/answer_cache.py [1]: 20
  S/static/daten.js [1]: 349
  S/static/tierliste.js [6]: 60,2187,2245,2247,2251,2432
  S/strength.py [14]: 172,174,208,226,244,265,317,442,461,561,772,773,954,976
  S/strength_view.py [3]: 58,1000,1697
  S/tournament_conversion.py [6]: 5,15,30,112,242,246
  S/web.py [6]: 71,920,921,926,928,931
tests:
  tests/pytest_shard_weights.json [1]: 352
  U/test_role_audit_1413.py [1]: 177
  U/test_studio_data_page.py [2]: 44,113
  U/test_studio_perf_equivalence.py [4]: 611,792,814,820
  U/test_studio_signals_conversion.py [4]: 261,269,292,307
  U/test_studio_simulation_weight_zero.py [1]: 46
  U/test_studio_static_guards.py [1]: 1610
  U/test_studio_strength.py [34]: 422,442,2300,2301,2305,2308,2317,2318,2321,2323,2333,2335,…
  U/test_studio_strength_v3.py [1]: 63
  U/test_tournament_conversion_1412.py [16]: 12,171,200,202,203,238,301,317,341,361,364,368,…
```

**K5a_relativ_funktion**

```
src/scripts:
  S/static/tierliste.html [4]: 70,71,75,76
  S/static/tierliste.js [26]: 175,664,682,683,892,917,1202,1317,1802,1817,1823,1964,1965,1966,2095,2102,2111,2112,2113,2115,2116,2119,2344,2413,2421,2422
  S/strength.py [34]: 495,624,679,680,793,844,849,855,897,1589,1597,1600,1603,1742,1998,1999,2007,2008,2009,2010,2014,2015,2016,2027,2030,2031,2033,2036,2039,2046,2058,2264,2310,2463
  S/strength_view.py [20]: 108,110,142,147,153,201,1233,1276,1313,1314,1379,1380,1381,1382,1385,1746,1747,1749,1931,1978
tests:
  U/test_role_audit_1413.py [2]: 166,172
  U/test_studio_rubric.py [1]: 221
  U/test_studio_static_guards.py [2]: 604,605
  U/test_studio_strength.py [34]: 809,822,851,874,875,876,878,1004,1021,1037,1202,1205,…
  U/test_studio_strength_v3.py [1]: 80
  U/test_studio_strength_v3_view.py [10]: 460,462,499,513,526,528,529,530,531,532
  U/test_studio_tierliste_e0.py [2]: 11,21
```

**K5b_verbreitung**

```
src/scripts:
  S/__main__.py [1]: 1008
  S/builder.py [2]: 1102,1109
  S/static/tierliste.html [1]: 52
  S/static/tierliste.js [7]: 471,510,968,1510,2356,2365,2392
  S/strength_view.py [2]: 66,1032
  S/swap.py [1]: 208
  S/tiers.py [9]: 28,30,37,126,138,149,153,166,171
  S/universe_view.py [8]: 33,368,377,384,461,508,513,745
  S/web.py [3]: 1103,1111,1158
tests:
  U/test_studio_counting.py [15]: 75,162,270,275,277,278,283,340,363,368,370,388,…
  U/test_studio_data_report.py [1]: 170
  U/test_studio_deck_modules.py [2]: 226,243
  U/test_studio_deck_primer.py [2]: 119,132
  U/test_studio_decklist_universe.py [6]: 375,395,404,513,859,860
  U/test_studio_scope_per_commander.py [1]: 116
  U/test_studio_static_guards.py [1]: 1596
  U/test_studio_strength.py [1]: 1181
  U/test_studio_strength_followup.py [1]: 173
  U/test_studio_tokens.py [2]: 213,222
  U/test_studio_universe_web.py [15]: 130,176,229,239,278,361,424,439,575,642,707,716,…
```

**K6_sim_gewicht**

```
src/scripts:
  S/cache.py [3]: 86,115,116
  S/overall_rating.py [1]: 104
  S/simulations.py [1]: 53
  S/static/tierliste.js [2]: 1181,1709
  S/strength.py [11]: 214,232,250,271,307,448,565,960,982,1827,2212
  S/strength_view.py [4]: 1633,1634,1635,1637
tests:
  U/test_deck_plan_pilot_2a.py [3]: 628,630,631
  U/test_studio_cache_groups.py [1]: 85
  U/test_studio_layer_weight_zero.py [1]: 85
  U/test_studio_layers.py [1]: 890
  U/test_studio_rubric.py [1]: 372
  U/test_studio_simulation_weight_zero.py [8]: 20,21,24,26,27,37,38,41
  U/test_studio_strength.py [7]: 428,448,1501,1700,1714,1717,1724
```

**K7_vorfilter**

```
src/scripts:
  S/builder.py [1]: 2080
  S/static/app.js [1]: 1359
  S/web.py [4]: 381,1580,1581,1585
tests:
  U/test_studio_builder.py [4]: 367,586,587,590
  U/test_studio_db_a_1404.py [3]: 182,207,227
```

**K8_simrun**

```
src/scripts:
  S/__main__.py [1]: 1022
  S/builder.py [5]: 1469,1475,1498,1503,1512
  S/cache.py [2]: 115,116
  S/data_report.py [3]: 491,493,496
  S/evidence.py [2]: 192,195
  S/importers.py [3]: 1273,1275,1300
  S/simulations.py [7]: 5,601,699,701,726,734,738
  S/store.py [13]: 282,334,352,353,365,612,638,651,652,750,781,784,1074
  S/web.py [2]: 566,643
tests:
  U/test_bridge_qualification_and_studio_1401.py [8]: 304,315,322,333,348,434,440,665
  U/test_studio_commander_binding.py [2]: 110,117
  U/test_studio_data_report.py [1]: 531
  U/test_studio_db_d_overview_visual.py [3]: 385,393,402
  U/test_studio_perf_equivalence.py [1]: 843
  U/test_studio_simulation_weight_zero.py [3]: 104,111,118
  U/test_studio_simulations.py [3]: 9,276,278
  U/test_studio_store.py [2]: 929,930
```

**K9_snapshot**

```
src/scripts:
  S/__main__.py [1]: 786
  S/cache.py [1]: 117
  S/import_all.py [5]: 38,96,711,730,789
  S/ranking_check.py [5]: 61,273,628,818,1053
  S/static/tierliste.js [2]: 1681,1710
  S/store.py [2]: 476,1076
  S/strength_view.py [4]: 1397,1409,1411,2127
  S/tier_snapshot.py [6]: 162,200,207,333,337,370
  S/web.py [3]: 69,523,853
tests:
  tests/fixtures/studio_architecture_baseline.json [3]: 15,44,74
  tests/pytest_shard_weights.json [1]: 349
  U/test_tier_snapshot_1420.py [48]: 24,293,297,299,315,317,322,332,333,334,335,340,…
```

**K10_memo**

```
src/scripts:
  S/cache.py [2]: 75,496
  S/import_all.py [2]: 31,331
  S/universe.py [3]: 60,467,1110
  S/web.py [3]: 56,1081,1096
tests:
  U/test_studio_cache_groups.py [1]: 139
  U/test_studio_memo.py [21]: 11,21,82,96,107,117,124,127,139,140,145,154,…
```

**K11_subarch**

```
src/scripts:
  scripts/spellbook_combos_fetch.py [1]: 39
  scripts/subarchetype_analysis.py [4]: 6,16,17,36
tests:
  tests/pytest_shard_weights.json [1]: 336
  U/test_studio_subarchetypes.py [1]: 11
```
