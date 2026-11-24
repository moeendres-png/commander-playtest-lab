# K-2b Code-Inventur: Schema 22 als Dateischnitt (`reference` / `studio` / `simulate`)

Stand: 2026-11-24 · Refs #1703, #1668, #1656, #1667  
Geprüfter Stand: `HEAD = 31b60756ff76821ecc9c7c69d690a74305440de4` (`main`, Arbeitsbaum sauber)  
Grundlagen: `docs/STUDIO_CHARTA_V2.md` (§3 Nr. 1 & 3, §5 Q9, §6), `docs/OWNER_DECISIONS_STUDIO_20261118.md` (E15 Q9, Entscheide 2026-11-21 Nr. 6a, „Preise für TAM“), `docs/STUDIO_STATE_EXPORT_FORMAT.md`.  
Evidenzklasse dieser Inventur: `CODE_DERIVED` (alle Zahlen maschinell per AST/SQLite-Inspektion gegen den geclonten Stand verifiziert; Verhalten am Owner-PC und unter Windows: `UNKNOWN`).

---

## 1. Kurzfassung der Befunde

| Befund | Verifizierte Zahl | Bedeutung für Schema 22 |
|---|---|---|
| Tabellen in Schema 21 (`store.py:41-634`) | **52** (davon **13** `WITHOUT ROWID`) | Aufteilung: **1** `meta` je Datei, **32** `reference`, **16** `studio`, **2** `simulate` (Altbestand → K-2d/e), **1** `tier_snapshot` (entfällt) |
| Explizite Indizes / Views / persistente Trigger | **23** Indizes (1 `UNIQUE`), **1** View (`card_fact`), **0** persistente Trigger (+**8** Temp-Trigger in `importing_for`) | `card_fact` bleibt komplett in `reference.sqlite3` (29/93 Studio-Module, 86 Referenzen) |
| Fremdschlüssel in Schema 21 | **47** gesamt | **7/47** dateiübergreifend bei `inventory`/`card_location` in `reference` (**11/47** falls in `studio`); SQLite prüft keine FKs über `ATTACH`-Grenzen |
| Lücken in `state_export.py` (`studio-user-state-1`) | **14** exportiert, **2** in `NOT_EXPORTED`, **3 Nutzertabellen fehlen komplett** | **Kritischer Befund:** `tam_cardmarket_price` (manuelle Owner-Preise, ohne zweite Quelle!) und `experiment`/`experiment_arm` fehlen in `_TABLES` **und** `NOT_EXPORTED` |
| Cross-DB-SQL in `src/commander_lab/studio/` | **17** Abfragen (+**3** `store.py`-Binding-Methoden) in **10/93** Dateien (`inventory` in `reference`); **+20** SQL-Stellen (**+19** `execute`-Aufrufe, +**7** weitere Dateien) falls `inventory` in `studio` | `inventory` + `card_location` gehören klar in `reference.sqlite3` (re-importierbar aus Excel-Workbook, nie im Studio editierbar) |
| Single-File-Pfadannahmen (`studio.sqlite3` / `store.path` / `sqlite3.connect`) | **11/93** Studio-Module (davon **3/93** mit `sqlite3.connect`), **17/127** Studio-Skripte (davon **7/127** mit `sqlite3.connect`) | Betrifft Kernkomponenten: `store.py`, `cache.py`, `memo.py`, `backup.py`, `oneclick.py`, `doctor.py`, `images.py`, `import_all.py`, `simulations.py`, `__main__.py` |
| `sqlite_master`-Inspektionen | **5/93** Studio-Module (**6** Stellen), **3/127** Skripte, **11/497** Studio-Testdateien (**12/497** gesamt; **23/497** Studio-Tests inkl. `PRAGMA`) | `SELECT ... FROM sqlite_master` sieht nur `main`, nicht `ATTACH`-Schemas |
| Betroffene Testdateien (`tests/**/test_*.py`, `N = 497`) | **89/497** `test_*.py` (**90/504** aller `.py` inkl. `studio_synth.py`), davon **85/497** mit direktem `.execute()` | **+19** gegenüber den „70 Testdateien“ der Charta §6. Kategorien: **44 HOCH**, **40 MITTEL** (+1 Helfer), **5 NIEDRIG** |
| D-1-Cache (`cache.py`) & WAL | `cache.py:307,606-615` erzwingt **Rollback-Journal-Modus** und prüft nur **eine** Datei (`store.path`, `PRAGMA data_version`, `database == "main"`) | Blocker für naives `ATTACH` und für WAL; erfordert mehrdateifähigen `store_stamp` + `data_version` je Datei oder getrennte Verbindungen |
| Owner-Store & Windows-Laufzeit | `UNKNOWN` | `windows-runtime.yml` führt aktuell nur **2/128** Studio-Testdateien aus; keine Messdaten zum Owner-PC |

---

## 2. Vollständige Inventur Schema 21 (`src/commander_lab/studio/store.py`)

Konstanten: `SCHEMA_VERSION = 21` (`store.py:17`), `DATABASE_NAME = "studio.sqlite3"` (`store.py:18`).  
Additive Spalten beim Öffnen ohne Schema-Bump (`store.py:899-976, 1053-1056`):
- `simulation_run`: `revision_id`, `deck_hash`, `opponent_ids`, `opponent_set_hash`, `table_size`, `pilot_fingerprint` (`store.py:899-910, 955-965`)
- `simulation_card`: `first_cast_round_games_reached`, `first_cast_round_games_not_reached`, `first_cast_round_q1`, `first_cast_round_median`, `first_cast_round_q3`, `first_cast_round_basis` (`store.py:914-921, 968-976`)
- `tam_price_eur`: `finish`, `set_code`, `collector_number` (`store.py:926-937`)
- `experiment`: `status` (`store.py:940-952`)

**Hinweis zu nicht-SQLite-Beständen:**
- **Kartenverständnis** (`card_understanding.py:30-35, 411-417`, `understanding_field.py`): liegt als JSONL im Repository (`data/card_understanding/card_understanding_v2_1.jsonl` und `data/research/chulane_rubric_v2_20261118/second_run_full_20261122/pooled.jsonl`), keine SQLite-Tabelle.
- **`deck_guides`**: Python-Modul in `src/commander_lab/agents/deck_guides.py`, keine SQLite-Tabelle.
- **PLAY-Sitzungen** (`play.py`): Laufzeitzustand im Arbeitsspeicher + Protokolle unter `games/`, keine SQLite-Tabelle.
- **Experiment- und Serien-Dateien**: Quelldateien unter `games/experiments/<id>/` (`plan.json`, `decision.json`; `deck_series.py:331-340`, `experiments.py:368,558`) und `games/series/<id>/` (`manifest.json`, `journal.jsonl`; `series_record.py:34`).

### 2.1 Alle 52 Tabellen, Fremdschlüssel und Ziel-Zuordnung

Legende Ziel-Datei (empfohlenes **Szenario A**):
- `JEDE` (**1/52**): existiert in jeder SQLite-Datei (je eigenes `schema_version`).
- `reference` (**32/52**): `reference.sqlite3` — aus externen/lokalen Rohquellen re-importierbar, komplett neu baubar.
- `studio` (**16/52**): `studio.sqlite3` — Nutzerzustand, Entscheidungen, Experiment-Index, manuelle Preise; einzige Quelle der Wahrheit für Nutzerarbeit, klein, exportierbar.
- `simulate` (**2/52**): `simulate.sqlite3` — Altbestand, in K-2d/e durch inhaltsadressiertes Partie-Archiv (`game_key`) ersetzt.
- `ENTFÄLLT` (**1/52**): abgeleiteter Cache, entfällt in Schema 22 (Q1/E4/K-2).

| # | Tabelle | `store.py` | `WO ROWID` | Spalten | Fremdschlüssel (`spalte → ziel.spalte`) | `cache.TABLE_GROUP` | `state_export` | Ziel-Datei |
|---:|---|---|---|---:|---|---|---|---|
| 1 | `meta` | `:41` | nein | 2 | — | `meta` | nein | **`JEDE`** (Schlüssel geteilt, s. §2.4) |
| 2 | `source` | `:42-50` | nein | 7 | — | `import` | ja (gefiltert) | **`reference`** (Zweifelsfall Z2) |
| 3 | `card` | `:51-65` | nein | 13 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 4 | `inventory` | `:67-77` | nein | 9 | `card_id → card.card_id`, `source_id → source.source_id` | `import` | nein | **`reference`** (Zweifelsfall Z1) |
| 5 | `card_location` | `:82-92` | **ja** | 8 | `card_id → card.card_id`, `source_id → source.source_id` | `import` | nein | **`reference`** (Zweifelsfall Z1) |
| 6 | `deck` | `:93-97` | nein | 3 | — | `decks` | ja | **`studio`** |
| 7 | `deck_revision` | `:98-106` | nein | 7 | `deck_id → deck.deck_id`, `parent_revision_id → deck_revision.revision_id`, **`source_id → source.source_id`** | `decks` | ja | **`studio`** |
| 8 | `deck_revision_card` | `:107-113` | nein | 4 | `revision_id → deck_revision.revision_id`, **`card_id → card.card_id`** | `decks` | ja | **`studio`** |
| 9 | `deck_branch` | `:114-119` | nein | 3 | `deck_id → deck.deck_id`, `revision_id → deck_revision.revision_id` | `decks` | ja | **`studio`** |
| 10 | `corpus_deck` | `:120-132` | nein | 11 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 11 | `corpus_deck_card` | `:133-141` | **ja** | 6 | `deck_id → corpus_deck.deck_id` | `import` | nein | **`reference`** |
| 12 | `observation` | `:145-158` | nein | 12 | `card_id → card.card_id`, `source_id → source.source_id` | `import` | nein | **`reference`** |
| 13 | `scryfall_card` | `:162-187` | nein | 24 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 14 | `card_printing` | `:190-203` | nein | 12 | `card_id → card.card_id` | `import` | nein | **`reference`** |
| 15 | `card_mark` | `:204-210` | nein | 5 | **`card_id → card.card_id`** | `marks` | ja | **`studio`** |
| 16 | `deck_draft` | `:211-218` | nein | 5 | `deck_id → deck.deck_id` | `decks` | ja | **`studio`** |
| 17 | `deck_module` | `:219-226` | nein | 6 | `deck_id → deck.deck_id` (`ON DELETE CASCADE`) | `decks` | ja | **`studio`** |
| 18 | `deck_module_card` | `:228-234` | **ja** | 4 | `module_id → deck_module.module_id` (`ON DELETE CASCADE`), **`card_id → card.card_id`** | `decks` | ja | **`studio`** |
| 19 | `deck_primer` | `:235-239` | nein | 3 | `deck_id → deck.deck_id` (`ON DELETE CASCADE`) | `decks` | ja | **`studio`** |
| 20 | `scryfall_token` | `:240-251` | nein | 10 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 21 | `scryfall_card_token` | `:253-261` | **ja** | 6 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 22 | `corpus_cohort` | `:263-267` | **ja** | 2 | `deck_id → corpus_deck.deck_id` | `import` | nein | **`reference`** |
| 23 | `universe_profile` | `:270-277` | nein | 6 | — | `profiles` | ja | **`studio`** |
| 24 | `corpus_deck_part` | `:278-282` | nein | 3 | `deck_id → corpus_deck.deck_id` (`DEFERRABLE`), `source_id → source.source_id` | `import` | nein | **`reference`** |
| 25 | `commander_binding` | `:283-290` | **ja** | 4 | — (`CHECK kind IN (..., 'simulation_run', ...)`) | `import` | nein | **`reference`** (`simulation_run`-Kind entfällt K-2e) |
| 26 | `corpus_deck_stat` | `:292-300` | nein | 7 | `deck_id → corpus_deck.deck_id` | `import` | nein | **`reference`** |
| 27 | `card_role` | `:301-306` | **ja** | 3 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 28 | `card_role_claim` | `:307-316` | **ja** | 7 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 29 | `corpus_deck_role` | `:318-323` | **ja** | 3 | `deck_id → corpus_deck.deck_id` | `import` | nein | **`reference`** |
| 30 | `neutral_board_row` | `:324-334` | nein | 8 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 31 | `simulation_run` | `:337-354` | nein | 22 | **`source_id → source.source_id`** | `simulation` | `NOT_EXPORTED` | **`simulate`** (Altbestand → K-2e) |
| 32 | `simulation_card` | `:355-367` | nein | 16 | `run_id → simulation_run.run_id`, **`card_id → card.card_id`** | `simulation` | `NOT_EXPORTED` | **`simulate`** (Altbestand → K-2e) |
| 33 | `experiment` | `:372-395` | nein | 22 | — | `simulation` | **FEHLT!** | **`studio`** (Index + Entscheidungen) |
| 34 | `experiment_arm` | `:397-403` | nein | 4 | `experiment_id → experiment.experiment_id` | `simulation` | **FEHLT!** | **`studio`** |
| 35 | `source_capture_event` | `:405-417` | nein | 11 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 36 | `playgroup_card_atlas` | `:418-475` | nein | 55 | `card_id → card.card_id`, `source_id → source.source_id` | `import` | nein | **`reference`** |
| 37 | `playgroup_top_commander` | `:480-490` | nein | 8 | — | `import` | nein | **`reference`** |
| 38 | `playgroup_final_zone` | `:491-499` | nein | 6 | — | `import` | nein | **`reference`** |
| 39 | `card_signal` | `:500-509` | **ja** | 7 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 40 | `strength_profile` | `:510-514` | nein | 3 | — | `profiles` | ja | **`studio`** |
| 41 | `tier_snapshot` | `:515-526` | nein | 9 | — | `snapshot` | nein | **`ENTFÄLLT`** (Q1/E4/K-2) |
| 42 | `card_label` | `:527-532` | nein | 3 | **`card_id → card.card_id`** | `marks` | ja | **`studio`** |
| 43 | `deck_label` | `:534-539` | nein | 3 | `deck_id → deck.deck_id` | `decks` | ja | **`studio`** |
| 44 | `commander_combo` | `:540-547` | nein | 5 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 45 | `card_ruling` | `:548-556` | nein | 6 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 46 | `card_ruling_source` | `:559-565` | nein | 4 | `source_id → source.source_id` | `import` | nein | **`reference`** |
| 47 | `tam_price_snapshot` | `:571-580` | nein | 8 | — | `import` | nein | **`reference`** (lokaler Scryfall-Bulk) |
| 48 | `tam_price_eur` | `:581-588` | **ja** | 6 | — | `import` | nein | **`reference`** (lokaler Scryfall-Bulk) |
| 49 | `tam_cardmarket_price` | `:594-601` | **ja** | 6 | — | `import` | **FEHLT!** | **`studio`** (manuelle Owner-Eingaben!) |
| 50 | `tam_price_print` | `:604-609` | nein | 4 | — | `import` | nein | **`reference`** (lokaler Scryfall-Bulk) |
| 51 | `tam_cardmarket_guide` | `:613-621` | **ja** | 6 | — | `import` | nein | **`reference`** (Cardmarket-Preisführer) |
| 52 | `tam_cardmarket_guide_snapshot` | `:622-634` | nein | 11 | — | `import` | nein | **`reference`** (Cardmarket-Preisführer) |

*Fett markierte Fremdschlüssel sind dateiübergreifend (7/47).*  
*Nebenergebnis:* `store.count()` (`store.py:1264-1276`) führt nur **38/52** Tabellen in seiner Whitelist (es fehlen `card_location`, `commander_combo`, `deck_module`, `deck_module_card`, `deck_primer`, `meta`, `scryfall_card_token`, `scryfall_token` und alle 6 `tam_*`-Tabellen). `cache.TABLE_GROUP` (`cache.py:109-124`) deckt alle **52/52** Tabellen ab — allerdings stehen `tam_cardmarket_price` noch unter `Group.IMPORT` und `experiment`/`experiment_arm` unter `Group.SIMULATION`.

### 2.2 Alle 23 expliziten Indizes, 1 View, Trigger und PRAGMAs

**Explizite Indizes (23 gesamt: 18 `reference`, 4 `studio`, 1 `simulate`):**

| # | Index | Tabelle | Spalten | `store.py` | Ziel-Datei |
|---:|---|---|---|---|---|
| 1 | `card_name` | `card` | `(oracle_name)` | `:66` | `reference` |
| 2 | `corpus_card_cover` | `corpus_deck_card` | `(card_name, section, quantity, deck_id)` | `:143-144` | `reference` |
| 3 | `observation_card` | `observation` | `(card_name, metric)` | `:159` | `reference` |
| 4 | `observation_source` | `observation` | `(source_id)` | `:161` | `reference` |
| 5 | `scryfall_name` | `scryfall_card` | `(name)` | `:188` | `reference` |
| 6 | `scryfall_front_name` | `scryfall_card` | `(front_name)` | `:189` | `reference` |
| 7 | `deck_module_deck` | `deck_module` | `(deck_id, sort_order, module_id)` | `:227` | `studio` |
| 8 | `scryfall_token_name` | `scryfall_token` | `(name)` | `:252` | `reference` |
| 9 | `scryfall_card_token_oracle` | `scryfall_card_token` | `(oracle_id)` | `:262` | `reference` |
| 10 | `corpus_cohort_deck` | `corpus_cohort` | `(deck_id)` | `:269` | `reference` |
| 11 | `commander_binding_name` | `commander_binding` | `(commander_name, kind)` | `:291` | `reference` |
| 12 | `card_role_claim_scope` | `card_role_claim` | `(role_origin, scope_key, role)` | `:317` | `reference` |
| 13 | `neutral_board_oracle` | `neutral_board_row` | `(oracle_id)` | `:335` | `reference` |
| 14 | `neutral_board_name` | `neutral_board_row` | `(card_name)` | `:336` | `reference` |
| 15 | `simulation_card_id` | `simulation_card` | `(card_id)` | `:368` | `simulate` |
| 16 | `experiment_deck` | `experiment` | `(deck_id)` | `:396` | `studio` |
| 17 | `experiment_arm_revision` | `experiment_arm` | `(revision_id)` | `:404` | `studio` |
| 18 | `idx_playgroup_card_atlas_card_id` | `playgroup_card_atlas` | `(card_id)` | `:476` | `reference` |
| 19 | `idx_playgroup_card_atlas_slug` | `playgroup_card_atlas` | `(slug)` | `:477` | `reference` |
| 20 | `idx_playgroup_card_atlas_status` | `playgroup_card_atlas` | `(fetch_status)` | `:478` | `reference` |
| 21 | `idx_playgroup_card_atlas_name` | `playgroup_card_atlas` | `(card_name)` | `:479` | `reference` |
| 22 | `card_label_label` | `card_label` | `(label)` | `:533` | `studio` |
| 23 | `card_ruling_unique` (`UNIQUE`) | `card_ruling` | `(oracle_id, published_at, comment)` | `:557-558` | `reference` |

**View (1/1):**
- `card_fact` (`store.py:635-653`): `FROM card c LEFT JOIN scryfall_card s ON s.oracle_id = c.oracle_id`. Beide Quelltabellen liegen in `reference.sqlite3` — die View ist vollständig dateiintern in `reference.sqlite3` (genutzt in **29/93** Studio-Modulen, **86** Referenzen).

**Trigger (0 persistent, 8 temporär zur Laufzeit):**
- `store.py:1108-1127` (`StudioStore.importing_for`): legt je `kind` in `('corpus_deck', 'observation_cohort', 'simulation_run', 'neutral_source')` zwei temporäre Trigger `bind_guard_{kind}` (`BEFORE INSERT ON main.{table}`) und `bind_write_{kind}` (`AFTER INSERT ON main.{table}`) sowie `CREATE TEMP TABLE import_commander` (`:1105`) an. **Bruch bei `ATTACH`:** `ON main.{table}` adressiert fest `main`; wenn `corpus_deck`/`observation`/`neutral_board_row` in `reference.sqlite3` liegen, muss das Zielschema (`ref.{table}` oder eigene `reference`-Verbindung) angepasst werden.
- Weitere temporäre Tabellen: `legacy_other` (`store.py:766`, nur Migration `< 10`), `work_list` (`decks.py:308`), `CREATE TEMP TABLE ...` (`universe.py:823`).

**PRAGMAs im gesamten Studio-Code (`src/commander_lab/studio/`):**
- `PRAGMA foreign_keys=ON` (`store.py:885, 1013`), `PRAGMA foreign_keys=OFF` (`store.py:787`, nur Migration `< 17`)
- `PRAGMA defer_foreign_keys=ON` (`state_export.py:525`, Import-Transaktion)
- `PRAGMA data_version` (`store.py:1254`, `cache.py:618`) — **Achtung:** gilt in SQLite pro Schema (`main` allein; für `ATTACH`te DBs muss `PRAGMA <schema>.data_version` gelesen werden!)
- `PRAGMA table_info(...)` (`store.py:889,930,943,956,969,1028,1036`, `state_export.py:131`, `data_report.py:199`)
- `PRAGMA foreign_key_list(...)` (`data_report.py:201`)
- `PRAGMA integrity_check` (`backup.py:56`)
- **`PRAGMA journal_mode=WAL` wird in `studio/` nirgends gesetzt** (nur im getrennten Modul `src/commander_lab/storage/database.py:30`). Im Gegenteil: `cache.py:307, 606-615` lehnt WAL explizit ab.

### 2.3 Dateiübergreifende Fremdschlüssel (7/47 bzw. 11/47)

SQLite erzwingt `FOREIGN KEY`s **nicht** über `ATTACH`-Grenzen (`CREATE TABLE` erlaubt keine schema-qualifizierten `REFERENCES`, und `PRAGMA foreign_keys=ON` gilt nur innerhalb einer Datei).

**Szenario A (`inventory` & `card_location` in `reference.sqlite3` — empfohlen): 7/47 FKs brechen** (40/47 bleiben dateiintern):
1. `deck_revision.source_id` (`studio`) → `source.source_id` (`reference`) (`store.py:104`)
2. `deck_revision_card.card_id` (`studio`) → `card.card_id` (`reference`) (`store.py:109`)
3. `deck_module_card.card_id` (`studio`) → `card.card_id` (`reference`) (`store.py:230`)
4. `card_mark.card_id` (`studio`) → `card.card_id` (`reference`) (`store.py:205`)
5. `card_label.card_id` (`studio`) → `card.card_id` (`reference`) (`store.py:528`)
6. `simulation_run.source_id` (`simulate`) → `source.source_id` (`reference`) (`store.py:353`) *(entfällt mit K-2e)*
7. `simulation_card.card_id` (`simulate`) → `card.card_id` (`reference`) (`store.py:357`) *(entfällt mit K-2e)*

**Szenario B (`inventory` & `card_location` in `studio.sqlite3` — nicht empfohlen): 11/47 FKs brechen** (+4: `inventory.card_id`, `inventory.source_id`, `card_location.card_id`, `card_location.source_id`) und **+20** zusätzliche Cross-DB-SQL-Stellen (**+19** `execute`-Aufrufe) in **7** weiteren Modulen.

### 2.4 Zweifelsfälle und konkrete Empfehlungen

| # | Zweifelsfall | Befund im Code | Empfehlung |
|---|---|---|---|
| **Z1** | `inventory` & `card_location` (`reference` vs. `studio`) | Werden ausschließlich durch `importers.py:338-352` aus dem externen Excel-Workbook vollständig überschrieben (`DELETE` + `INSERT`); 0 Schreibpfade im Studio-UI; in `STUDIO_STATE_EXPORT_FORMAT.md:70-71` (E-A1) bereits als Importtabelle ausgeschlossen; **20** `card_fact/card JOIN inventory`-SQL-Stellen (**19** `execute`-Aufrufe) in 11 Modulen. | **`reference.sqlite3`**. Hält `studio.sqlite3` klein, vermeidet 4 Cross-DB-FKs und 20 Cross-DB-SQL-Stellen; Quelle der Wahrheit der Sammlung bleibt das Excel-Workbook. |
| **Z2** | `deck_revision.source_id → source` | `state_export.py:77,158-161` exportiert bereits die kleine Teilmenge von `source`, auf die `deck_revision.source_id` zeigt. | Eigene kleine `deck_source`-Tabelle in `studio.sqlite3` (oder Inline-Spalten `source_sha256`/`source_title`), um Namenskollision mit `reference.source` zu vermeiden. |
| **Z3** | `card_id` vs. `oracle_id` in `studio`-Tabellen (E-A3) | Die 4 `studio → reference.card`-FKs (`deck_revision_card`, `deck_module_card`, `card_mark`, `card_label`) und `ensure_scryfall_cards` (`store.py:1279-1341`, 4 Aufrufer) existieren nur wegen `card_id` als FK auf `card`. | Umstellung auf `oracle_id` als fachlicher Schlüssel in Schema 22 (`studio.sqlite3`), ohne Cross-DB-FK. `ensure_scryfall_cards` und `state_import_stub` (`state_export.py:42`) entfallen damit komplett; kein Cross-DB-Schreiben beim Deck-/Marken-Speichern. |
| **Z4** | TAM-Preistabellen (`tam_*`, 6 Tabellen) | 5 Tabellen (`tam_price_snapshot`, `tam_price_eur`, `tam_price_print`, `tam_cardmarket_guide`, `tam_cardmarket_guide_snapshot`) sind re-importierbare Ableitungen lokaler Scryfall-/Cardmarket-Dateien (`tam_prices.py:182-205,317-338`). **`tam_cardmarket_price`** (`store.py:594-601`, `tam_prices.py:527-530`) speichert dagegen **manuell eingetragene Preise des Owners**. | 5 Import-Tabellen → **`reference.sqlite3`** (beim Neuaufbau werden `tam_cardmarket_guide*` nur aus bereits lokal vorhandenen Dateien wieder eingelesen, nie automatisch nachgeladen — Owner-Ausnahme Cardmarket gilt nur auf expliziten Befehl, max. 1×/Datei/Tag); **`tam_cardmarket_price` → `studio.sqlite3`** (und in `studio-user-state-2` aufnehmen; Test-Fixtures nur synthetisch, `AGENTS.md` §12). |
| **Z5** | `experiment` & `experiment_arm` | Charta §3 Nr. 1 ordnet „Experiment-Index + Entscheidungen“ explizit `studio` zu. Quelldateien (`plan.json`, `decision.json`) liegen zusätzlich unter `games/experiments/` (`deck_series.py:331-340`), und `experiments.rebuild_index` baut beide Tabellen neu auf. | **`studio.sqlite3`** (wie Charta §3 Nr. 1); Migration führt entweder Export über `studio-user-state-2` oder zwingend `rebuild_index` nach Übernahme von `games/experiments/` aus. |
| **Z6** | `meta`-Schlüssel | Schreibstellen in `src/`: `schema_version` (`store.py:1018,1051`), `user_state_import_sha256` (`state_export.py:43,555`), `field_read.META_FALLBACKS_KEY` (`field_read.py:204`, Import-Fallback-Zähler). | Jede der 3 Dateien hat ihre eigene `meta` (`schema_version`). `user_state_import_sha256` liegt in `studio.meta`; `field_read` schreibt in `reference.meta`. |

---

## 3. Lückenprüfung `src/commander_lab/studio/state_export.py`

Format `studio-user-state-1` (`state_export.py:37`):
- **Exportiert (`_TABLES`, `state_export.py:76-91`, 14 Tabellen):** `source` (nur `deck_revision.source_id`), `deck`, `deck_revision`, `deck_revision_card`, `deck_branch`, `deck_draft`, `deck_label`, `deck_primer`, `deck_module`, `deck_module_card`, `card_mark`, `card_label`, `strength_profile`, `universe_profile`.
- **Explizit ausgeschlossen und gezählt (`NOT_EXPORTED`, `state_export.py:50`, 2 Tabellen):** `simulation_run`, `simulation_card`.
- **Als noch nicht im Schema deklariert (`NOT_IN_SCHEMA`, `state_export.py:46`):** `setting`, `table_preset`.

### Fehlende Nutzertabellen seit Einführung von `state_export.py` (K-2a)

| Tabelle | Hinzugefügt durch | Zustand in `state_export.py` | Verlustrisiko bei Migration über `studio-user-state-1` | Maßnahme vor K-2c |
|---|---|---|---|---|
| **`tam_cardmarket_price`** (`store.py:594-601`) | #1637 WP-10b (manuelle Cardmarket-Preise des Owners) | **Weder in `_TABLES` noch in `NOT_EXPORTED`** | **HOCH — echter Datenverlust.** Es existiert keine zweite Datei-Quelle auf Platte (nur im lokalen Store). | Zwingend vor K-2c in **`studio-user-state-2`** aufnehmen (PK ist bereits `oracle_id`, keine `card_id`-Abhängigkeit; Daten bleiben strikt lokal, nie ins Repo; Tests nur synthetisch). |
| **`experiment`** & **`experiment_arm`** (`store.py:372-403`) | B2 #1658 (Experiment-Index + Owner-Entscheidungen + `status='withdrawn'`) | **Weder in `_TABLES` noch in `NOT_EXPORTED`** | **MITTEL:** Plan-/Entscheidungs-/Rückzugsdateien liegen in `games/experiments/<id>/`, `experiments.rebuild_index` kann den Index neu aufbauen — aber nur wenn `games/experiments/` beim Migrationspfad vorhanden bleibt und `rebuild_index` automatisch läuft. | Entweder in `studio-user-state-2` aufnehmen **oder** explizit in `NOT_EXPORTED` melden und `rebuild_index` als verbindlichen Schritt in K-2c verankern (mit Gleichheitsprüfung gegen Alt-Store). |

*Hinweis zu `studio-user-state-1` für den aktuellen Owner-Export (6a):* Die 3 vorbereiteten Owner-Befehle im Issue #1703 bleiben gültig, prüfen aber `tam_cardmarket_price` und `experiment`/`experiment_arm` noch nicht mit. Vor dem eigentlichen K-2c-Schnitt muss entweder ein kleiner PR `K-2a2` (`studio-user-state-2`) folgen oder der K-2c-Migrator diese Tabellen explizit aus dem gesicherten Alt-Store (bzw. `games/experiments/`) verifizieren und übernehmen.

---

## 4. SQL-, Verbindungs- und Pfad-Inventur (`src/commander_lab/studio/` und `scripts/`)

### 4.1 `src/commander_lab/studio/` (`N = 93` `.py`-Dateien)

- `sqlite3.connect`: **3/93** (`store.py:1004,1008`, `backup.py:54,104,105`, `oneclick.py:1141`)
- `store.connection` / `.connection.execute`: **52/93**
- SQL-Abfragen gegen Studio-Tabellen: **55/93** (davon **34/93** mit `JOIN`, **105** `JOIN`-Zeilen gesamt)
- `sqlite_master`-Abfragen (brechen bei `ATTACH` für Tabellen außerhalb von `main`): **5/93** (`catalog.py:197,362`, `combos.py:502`, `data_report.py:193`, `images.py:95`, `store.py:870`)
- Single-File-Pfadannahmen (`store.path`, `DATABASE_NAME`, `studio.sqlite3`, `SCHEMA_VERSION`): **11/93**:
  - `store.py:17,18,1003,1004,1008,1015-1051` (Schema, Open, Version)
  - `backup.py:16,54,88,103-105,210,215,229` (sichert/prüft nur eine `studio.sqlite3`)
  - `cache.py:301-320,424,515,606-618,628-631` (D-1-Stamp & Write-Window auf genau einer Datei `store.path`)
  - `memo.py:77,94,96` (`store.path` + `-wal`/`-journal`-Signatur einer Datei)
  - `oneclick.py:67,1137-1145` (`DATABASE_NAME = "studio.sqlite3"`, prüft `SELECT COUNT(*) FROM card` direkt per `sqlite3.connect` — **bricht sofort**, wenn `card` nach `reference.sqlite3` wandert)
  - `doctor.py:17,436` (prüft nur Existenz von `data_dir / DATABASE_NAME`)
  - `images.py:35-55` (leitet `images/` aus `store.path.parent` ab — funktioniert weiter, wenn `store.data_dir` eingeführt wird)
  - `import_all.py:860-869` (Fehlerbericht neben `store.path.parent`, Protokollzeile `Datenbank: {store.path}`)
  - `simulations.py:2137-2138,2231-2232` (`StudioStore.open(store.path.parent)`)
  - `__main__.py:884,1020-1022` (`store.path.parent / "cardmarket"`)
  - `sources.py:168,455` (nur Beschreibungstexte)

#### Alle dateiübergreifenden SQL-Abfragen in `src/commander_lab/studio/` (Szenario A: `inventory` in `reference`)

**14 direkte `studio ↔ reference` (bzw. `+ simulate`) JOIN/Subquery-Abfragen in 9/93 Dateien (13 produktive Abfragen in 8/93 Dateien + 1 Legacy-Migrationsabfrage in `store.py`):**

| # | Datei:Zeile | Beteiligte Tabellen/Views | Betroffene DBs |
|---:|---|---|---|
| 1 | `builder.py:170-178` | `deck_branch`, `deck_revision_card`, `card_fact` | `studio` ↔ `reference` |
| 2 | `builder.py:788-794` | `scryfall_card`, `card`, `card_mark` | `reference` ↔ `studio` |
| 3 | `builder.py:989-997` | `card_fact`, `inventory`, `card_mark` (wenn `with_marks=True`) | `reference` ↔ `studio` |
| 4 | `builder.py:2540-2543` | `deck_branch`, `deck_revision_card`, `card_fact` | `studio` ↔ `reference` |
| 5 | `deck_modules.py:83-88` | `deck_module`, `deck_module_card`, `card_fact` | `studio` ↔ `reference` |
| 6 | `decks.py:205-207` | `deck_revision_card`, `card_fact`, `inventory` | `studio` ↔ `reference` |
| 7 | `maturity.py:745-746` | `deck_revision_card`, `card` | `studio` ↔ `reference` |
| 8 | `similar_decks.py:572-574` | `deck_revision_card`, `card_fact` | `studio` ↔ `reference` |
| 9 | `similar_decks.py:797-802` | `deck_revision_card`, `card_fact`, `inventory` | `studio` ↔ `reference` |
| 10 | `simulations.py:1271-1274` | `commander_binding`, `deck_revision_card`, `card_fact` | `reference` ↔ `studio` |
| 11 | `state_export.py:158-161` | `source`, `deck_revision` | `reference` ↔ `studio` |
| 12 | `store.py:757-764` | `commander_binding`, `simulation_run`, `deck_revision`, `deck_revision_card`, `card_fact` (nur Legacy-Migration `< 10`) | `reference` ↔ `simulate` ↔ `studio` |
| 13 | `swap.py:97-98` | `deck_revision_card`, `card_fact` | `studio` ↔ `reference` |
| 14 | `swap.py:234-239` | `card_fact`, `inventory`, `card_mark` | `reference` ↔ `studio` |

**Zusätzlich 3 `simulate ↔ reference.commander_binding`-Abfragen + 3 Binding-Methoden in `store.py` (entfallen mit K-2e):**
- `builder.py:1520,1529` (`simulation_card JOIN simulation_run` + `bound_to("simulation_run", ...)` auf `commander_binding`)
- `builder.py:1564,1570` (`simulation_run` + `bound_to("simulation_run", ...)`)
- `evidence.py:271,276` (`simulation_card JOIN simulation_run` + `bound_to("simulation_run", ...)`)
- `store.py:725-740` (`_bind_unbound`), `:1108-1127` (`importing_for`), `:1166-1179` (`binding_counts`)

**Zusätzlich 1 dateiübergreifender Schreibpfad:**
- `ensure_scryfall_cards` (`store.py:1279-1341`), aufgerufen beim Speichern von Nutzerdaten in `builder.py:2426,2505`, `decks.py:136`, `labels.py:85` — schreibt in `reference.card` aus einem `studio`-Write-Pfad heraus (entfällt bei Z3 / `oracle_id`-Umstellung).

*(Vergleich Szenario B: Läge `inventory` in `studio.sqlite3`, kämen **+20** `card_fact/card JOIN inventory`-SQL-Stellen — **+19** `execute`-Aufrufe, da `combos.py:524,534` zwei Zweige eines `db.execute(sql)` in `:537` sind — in `builder.py:212,440,1226,1247,2330`, `combos.py:524,534`, `decks.py:318,536`, `land_advisor.py:457,782`, `packages.py:164`, `queries.py:24`, `roles.py:819`, `similar_decks.py:237,542,765`, `state_export.py:307`, `tam_prices.py:368`, `universe.py:560` hinzu → 37 statt 17 Cross-DB-SQL-Stellen.)*

### 4.2 `scripts/` (`N = 127` `.py`-Dateien)

- **0/127** Skripte enthalten Cross-DB-SQL (alle Skripte lesen/schreiben ausschließlich `reference`-Tabellen).
- **17/127** Skripte berühren den Studio-Store aktiv (2 weitere — `scripts/pilot_decision_records.py` mit eigener SQLite-Datei und `scripts/studio_architecture_counts.py` mit Docstring-Erwähnung — sind unbetroffen):
  - **7/127** öffnen eine Studio-DB direkt per `sqlite3.connect` (müssen auf `reference.sqlite3` bzw. `StudioStore` umgestellt werden):
    - `scripts/analysis/validate_h_t6_t7.py:493,495,558,599,628,642` (kopiert `studio.sqlite3` und öffnet per `sqlite3.connect`)
    - `scripts/collect_playgroup_card_atlas.py:166,226,765` (Standardpfad `studio.sqlite3`, `sqlite_master` auf `card`/`scryfall_card`/`corpus_deck_card`)
    - `scripts/data_wave1/db_guard.py:31,44,50` (`sqlite_master` Schema-Guard)
    - `scripts/data_wave1/export_collection_ids.py:25,39` (`--db` zeigt auf `studio.sqlite3`)
    - `scripts/data_wave1/validate_s1.py:102`
    - `scripts/map_corpus_oracle_ids.py:20-21,36-37,42,53` (Standardpfad `studio.sqlite3`)
    - `scripts/studio_import_guard.py:79,84` (`sqlite_master`)
  - **10/127** nutzen `StudioStore.open(...)` oder den Dateinamen `studio.sqlite3` ohne direktes `sqlite3.connect`:
    - `scripts/studio_response_manifest.py:89,464,1029` (`DATABASE = "studio.sqlite3"`, kopiert Template-Ordner/Datei)
    - `scripts/import_tam_drive.py:20,47-52,101` (prüft `DATABASE_NAME`)
    - `scripts/build_gap_matrix_from_store.py:6,22,26`
    - `scripts/build_corpus_fill.py:41,91` (direktes SQL auf `store.connection`)
    - `scripts/generate_oracle_role_file.py:32,56,65,73,95` (direktes SQL auf `store.connection`)
    - `scripts/import_chulane_corpus.py:46,48`
    - `scripts/import_scryfall_oracle_tags.py:50,506` (direktes SQL)
    - `scripts/mtgjson_global_inclusion_check.py:308-350` (direktes SQL auf `store.connection`)
    - `scripts/spellbook_combos_fetch.py:59,111,552` (direktes SQL auf `store.connection`)
    - `scripts/subarchetype_analysis.py:37,61-118,154` (direktes SQL auf `store.connection`)

---

## 5. Test-Inventur (`tests/`)

Gesamtbestand: **504** `.py`-Dateien unter `tests/`, davon **497** Testdateien (`test_*.py`) und **7** Hilfs-/Conftest-Dateien (u. a. `tests/unit/studio_synth.py`).

### 5.1 Exakte Zählung (`n/N`)

| Kriterium | `test_*.py` (`N = 497`) | Alle `tests/**/*.py` (`N = 504`) |
|---|---:|---:|
| Studio-Testdateien gesamt | **128/497** | **129/504** |
| Nutzen `StudioStore` | **97/497** | **98/504** |
| **Betroffene Studio-Testdateien gesamt** (mind. 1 Kriterium unten) | **89/497** | **90/504** |
| — davon direktes `.execute()` / `.executemany()` / `.executescript()` | **85/497** | **86/504** |
| — davon `store.connection` / `._conn` | **82/497** | **83/504** |
| — davon `sqlite3`-Import | **29/497** | **29/504** |
| — davon `store.path` / `db_path` / `DATABASE_NAME` / `studio.sqlite3` | **26/497** | **26/504** |
| — davon `PRAGMA` / `sqlite_master` | **23/497** | **23/504** |
| — davon `SCHEMA_VERSION` / `meta.schema_version` | **13/497** | **13/504** |
| — davon D-1-Cache-Interna (`TABLE_GROUP`, `store_stamp`, `_rollback_journal_file`) | **3/497** | **3/504** |
| Nur High-Level-`StudioStore`-API (kein direktes SQL/Pfad/Interna) | **16/497** | **16/504** |
| Nicht-Studio-SQLite-Tests (z. B. `test_phase86_database.py`, unbetroffen) | **4/497** | **4/504** |

*Abgleich mit Charta §6:* Die dort genannten „70 Testdateien mit eigenem SQL“ sind am Stand `31b60756` auf **85/497** `test_*.py` mit direktem `.execute()` (**89/497** inkl. Pfad-/Backup-/Doctor-/Manifest-Tests) angewachsen.

### 5.2 Einfluss-Kategorisierung der 89 betroffenen `test_*.py` (+1 Helfer)

**HOCH — 44/497 `test_*.py`** (testen `SCHEMA_VERSION`, `PRAGMA`/`sqlite_master`, Cache-Interna, `backup`/`state_export`/`schema_migration`/`oneclick`/`response_manifest`, `sqlite3.connect` + Dateipfad, oder ≥ 10 direkte SQL-Aufrufe):
- *Schema, Migration, Store, Export, Backup, Cache, Betrieb (14):* `test_studio_store.py`, `test_studio_schema_migration.py`, `test_studio_state_export.py`, `test_studio_backup.py`, `test_studio_cache_groups.py`, `test_studio_perf_equivalence.py`, `test_studio_memo.py`, `test_studio_oneclick.py`, `test_studio_doctor.py`, `test_studio_response_manifest.py`, `test_studio_sources.py`, `test_bridge_qualification_and_studio_1401.py`, `test_data_wave1_scripts.py`, `test_validate_h_t6_t7.py`.
- *Domänen-Tests mit `SCHEMA_VERSION` / `PRAGMA` / `sqlite_master` / `≥ 10` SQL-Aufrufen (30):* `test_studio_decklist_universe.py`, `test_studio_data_report.py`, `test_studio_universe_web.py`, `test_studio_builder.py`, `test_studio_tam_prices.py`, `test_studio_simulations.py`, `test_studio_strength.py`, `test_studio_experiments.py`, `test_studio_db_b_1404_1417.py`, `test_studio_revision_parent_1727.py`, `test_tier_snapshot_1420.py`, `test_studio_issue_1307.py`, `test_studio_db_d_overview_visual.py`, `test_studio_card_duel.py`, `test_studio_playgroup_atlas.py`, `test_studio_printings.py`, `test_studio_similar_decks.py`, `test_studio_multipart_corpus_import.py`, `test_studio_evidence.py`, `test_studio_land_advisor.py`, `test_studio_roles_import.py`, `test_studio_commander_binding.py`, `test_studio_corpus_audit.py`, `test_studio_db_c_paired_readiness.py`, `test_studio_printing_images.py`, `test_studio_rulings.py`, `test_studio_labels.py`, `test_studio_round2.py`, `test_studio_combos.py`, `test_studio_counting.py`.

**MITTEL — 40/497 `test_*.py` + 1 Helfer (`tests/unit/studio_synth.py`)** (3–9 direkte SQL-/`.connection`-Aufrufe oder `store.path`/`sqlite3` für Setup/Assertions):
`test_import_scryfall_oracle_tags.py`, `test_role_audit_1413.py`, `test_studio_allocation.py`, `test_studio_cache_single_flight.py`, `test_studio_card_outcomes.py`, `test_studio_chulane_textfit.py`, `test_studio_cooccurrence_reference.py`, `test_studio_counted_universe.py`, `test_studio_cut_lab.py`, `test_studio_db_a_1404.py`, `test_studio_deck_diff.py`, `test_studio_deck_facts.py`, `test_studio_deck_to_series_roundtrip.py`, `test_studio_decklist_hardening.py`, `test_studio_draft_card.py`, `test_studio_edhrec_proof_validation.py`, `test_studio_edhrec_snapshot_import.py`, `test_studio_engine_provisioning.py`, `test_studio_field_read.py`, `test_studio_games.py`, `test_studio_german_names_1553.py`, `test_studio_import_all_corpus_link.py`, `test_studio_import_from_repo.py`, `test_studio_land_cycles.py`, `test_studio_list_rows_cache.py`, `test_studio_maturity.py`, `test_studio_number_contract.py`, `test_studio_playgroup_component.py`, `test_studio_roles_expansion_1353.py`, `test_studio_signals_edhtop16.py`, `test_studio_signals_guards.py`, `test_studio_simulation_weight_zero.py`, `test_studio_static_guards.py`, `test_studio_strength_followup.py`, `test_studio_strength_v3_view.py`, `test_studio_swap.py`, `test_studio_tam_view_wp8.py`, `test_studio_tierliste_h_pooled.py`, `test_studio_tierliste_role_gaps.py`, `test_studio_tierliste_wp6.py` (+ `tests/unit/studio_synth.py`).

**NIEDRIG — 5/497 `test_*.py`** (1–2 einfache SQL-Aufrufe):
`test_studio_fingerprint_normalization.py`, `test_studio_import_all_layers.py`, `test_studio_owner_marks.py`, `test_studio_scope_per_commander.py`, `test_studio_tokens.py`.

---

## 6. Architektur-Bewertung: `ATTACH DATABASE` vs. getrennte Verbindungen vs. Rückfallplan

### 6.1 Vergleich der beiden Verbindungsmodelle

| Kriterium | Option A: `ATTACH DATABASE` (1 Verbindung: `main=studio`, `ref=reference`, `sim=simulate`) | Option B: Getrennte Verbindungen (`store.studio`, `store.reference`, `store.simulate`) |
|---|---|---|
| 14 Cross-DB-JOINs in `studio/` | Laufen nach Auflösung der Namenskollisionen (`meta`, ggf. `source`) weiter. | Müssen in 9 Dateien (13 produktive Abfragen in 8 Dateien + 1 Legacy-Migrationsabfrage in `store.py`) auf 2 Abfragen + Python-Join umgestellt werden (überschaubar, da `deck_revision_card` ≤ 100 Karten, `card_mark` klein). |
| 85 Testdateien mit `store.connection.execute(...)` | Unqualifizierte SQL-Aufrufe laufen großteils weiter (außer `meta`, `sqlite_master`, `PRAGMA`, `SCHEMA_VERSION`). | **Alle 85 Testdateien brechen sofort**, sofern `store.connection` entfällt; ohne Übergangsfassade hoher Migrationsaufwand. |
| Fremdschlüssel (`PRAGMA foreign_keys=ON`) | **Keine** Durchsetzung über `ATTACH`-Grenzen; 7 Cross-DB-FKs müssen ohnehin entfallen. | Identisch: 7 Cross-DB-FKs entfallen; jede Datei behält volle dateiinterne FK-Integrität. |
| **D-1-Cache (`cache.py`)** | **Schwerer Umbau nötig:** `store_stamp` muss alle 3 Dateien prüfen, `PRAGMA <schema>.data_version` je Schema, `_Window.authorize()` (`cache.py:586`) akzeptiert heute nur `database == "main"`. | **Sauber:** Jede Datei hat eigenen `store_stamp`, eigenes `PRAGMA data_version`, eigene `Group`-Zuordnung (`Group.IMPORT` ↔ `reference.sqlite3`, `DECKS/MARKS/PROFILES` ↔ `studio.sqlite3`, `SIMULATION` ↔ `simulate.sqlite3`). |
| `VACUUM` (`store.compact()`) | Vakuumiert in SQLite **nur `main`**, nie `ATTACH`te Dateien. | Unabhängiges `VACUUM` je Datei; `reference.sqlite3` lässt sich neu bauen und atomar ersetzen. |
| `sqlite_master`-Abfragen (5 Module, 23 Tests) | Sehen nur `main`, nicht `ref.sqlite_master` / `sim.sqlite_master`. | Klar je Verbindung (`reference.sqlite_master` vs. `studio.sqlite_master`). |
| Multi-DB-Transaktionen & WAL-Atomarität | Kritisch: Transaktion über `main` + `ref` nutzt im Rollback-Journal ein Master-Journal (erhöhte Lock-Konflikte), verliert im WAL-Modus die Crash-Atomarität über Dateien hinweg. | **Keine** Multi-DB-Transaktionen möglich → erzwingt saubere Trennung (nach Z3 entfällt `ensure_scryfall_cards`, damit gibt es keinen Cross-DB-Write mehr). |
| `importing_for()` (`store.py:1108-1127`) | `ON main.{table}` muss auf `ON ref.{table}` umgestellt werden. | Läuft unverändert auf `reference`-Verbindung (`main` dieser Verbindung). |

### 6.2 Empfehlung: Getrennte Verbindungen als Zielmodell

1. **Produktionscode → Option B (getrennte Verbindungen):** `StudioStore` kapselt `data_dir: Path | None`, `studio_conn`, `reference_conn`, `simulate_conn` (lazy). Kein Code darf in einer Transaktion in zwei Dateien schreiben (durch Z3 / `oracle_id` in `studio.sqlite3` sauber erfüllbar).
2. **D-1-Cache (`cache.py`):** `store_stamp` wird auf ein Tupel der Stamps der beteiligten Dateien (`studio`, `reference`, `simulate`) erweitert; `cache.write(store, groups)` beobachtet genau die Zielverbindung der geschriebenen Gruppen (1 Datei je Schreibfenster → `_rollback_journal_file`, `file change counter` und `PRAGMA data_version` bleiben 1:1 beweisbar).
3. **Test-Migration:** In K-2c schrittweise über explizite Zuordnung `store.reference` / `store.studio` in den 44 HOCH-, 40 MITTEL- und 5 NIEDRIG-Testdateien; **nicht** per `ATTACH` im Produktivpfad als Dauerlösung verdecken.

### 6.3 WAL, Locking und Windows-Verhalten (`UNKNOWN` explizit)

- **Aktueller Journal-Modus:** `studio/` nutzt **Rollback-Journal** (SQLite-Standard `DELETE`), **nicht** WAL. `cache.py:307,606-615` prüft explizit `header[18] == 1 and header[19] == 1` und deaktiviert das Caching im WAL-Modus (`store_stamp` gibt `None` zurück). Ein Wechsel auf WAL ist für Schema 22 **nicht** empfohlen.
- **Windows-Risiken (aktuell `UNKNOWN`, da `.github/workflows/windows-runtime.yml:113` nur 2/128 Studio-Testdateien ausführt):**
  1. **Offene Datei-Handles beim atomaren Ersetzen (`reference.sqlite3` neu bauen → `os.replace`):** Unter Windows schlägt `os.replace` / `unlink` mit `PermissionError` fehl, solange noch eine SQLite-Verbindung offen ist.
  2. **`st_mtime_ns` / `store_stamp` / `PRAGMA data_version` unter NTFS:** Verhalten über 3 Dateien unter Windows ist `UNKNOWN` → Pflicht-Test in `windows-runtime.yml` vor K-2c.
  3. **Antivirus / Windows Defender:** Kurzlebige `-journal`-Dateien (und `os.replace` bei `studio.lock`-Herzschlag alle 5 s, `instance_lock.py:173`) können unter Windows sporadische `PermissionError`/`SQLITE_BUSY`-Fehler auslösen.
- **Vorbedingung vor K-2c:** `windows-runtime.yml` um `test_studio_store.py`, `test_studio_cache_groups.py`, `test_studio_state_export.py` und `test_studio_backup.py` erweitern.

### 6.4 Auswirkungen auf `backup.py` (Sicherung & Rückspiel)

`src/commander_lab/studio/backup.py` (`SCHEMA_BACKUP = "studio-backup-1"`, `:18`):
- **Heute:** Sichert genau `studio.sqlite3` (`backup.py:88,103-111` via `src_conn.backup(dst_conn)` + `PRAGMA integrity_check`) plus `games/` (`:113-128`, enthält damit auch `games/experiments/` und `games/series/`). `restore_backup` verlangt exakt `DATABASE_NAME` im Manifest (`:210-215, 229`).
- **Für Schema 22 (`studio-backup-2`):**
  - `studio.sqlite3` ist **Pflicht** (Online-Backup + `PRAGMA integrity_check`).
  - `reference.sqlite3` und `simulate.sqlite3`: standardmäßig mitsichern wenn vorhanden (jeweils eigenes `src_conn.backup(dst_conn)` + `integrity_check`), plus optionales Flag `--user-only` (nur `studio.sqlite3` + `games/experiments/`).
  - `restore_backup` unterstützt abwärtskompatibel `studio-backup-1` (Schema 21) **und** `studio-backup-2` (Schema 22).

### 6.5 Expliziter Rückfallplan (Charta §6)

Nach `docs/STUDIO_CHARTA_V2.md` §6 gilt als Abbruchkriterium: **Paket-Budget > +50 % überschritten** oder **ungelöste Windows-/Cache-Locking-Fehler** oder **unerklärte Hash-Abweichung > 2 Tage**.

**Rückfall: Eine Datei (`studio.sqlite3`) mit Neuaufbau an Ort und Stelle (Schema 22 ohne Dateischnitt):**
- **Voller fachlicher Kernwert von Q9 bleibt erhalten:**
  1. Nutzer-Export `studio-user-state-2` (inkl. `tam_cardmarket_price` und `experiment`/`experiment_arm`) bleibt dauerhafte kleine Sicherung und Rundlauf-Prüfmittel.
  2. Umstellung der Nutzertabellen auf `oracle_id` (E-A3) → Entkopplung von `card_id`/Workbook-Importen, Wegfall `ensure_scryfall_cards` und `state_import_stub`.
  3. Entfernung von `tier_snapshot` (Q1/E4) und Ablösung von `simulation_run`/`simulation_card` durch das inhaltsadressierte Partie-Archiv (`simulate.sqlite3` optional als isolierte zweite Datei nur für SIMULATE, ohne `ATTACH` an `studio.sqlite3`).
  4. **Neuaufbau an Ort und Stelle:** `studio rebuild-store` exportiert Nutzerzustand (`studio-user-state-2`), legt Backup an, erstellt frische `studio.sqlite3`, importiert Referenzdaten aus lokal vorhandenen Dateien neu (insbesondere `tam_cardmarket_guide*` nur aus lokal vorhandenen Dateien, nie automatisch nachgeladen), spielt Nutzerzustand mit SHA-Gleichheitsbeweis zurück und schrumpft die Datei sauber (`VACUUM`).
- **Einsparung:** Kein Multi-File-Umbau von `cache.py`, kein Umbau der 14 Cross-DB-JOINs, kein Umbau von 89 Testdateien und 7 `sqlite3.connect`-Skripten, keine Windows-Multi-File-Locking-Risiken.

---

## 7. Konkreter Fahrplan für K-2c, K-2d und K-2e (nach den 3 Owner-Export-Befehlen)

### Schritt 0 — Owner-Aktion (Entscheid 6a, ohne Upload)
Ausführung der 3 Befehle aus #1703 Kommentar `7066583765` am Owner-PC (optional vorher `studio backup --to <Ordner außerhalb>`):
1. `python -m commander_lab.studio export-state --check`
2. `python -m commander_lab.studio export-state --json`
3. `python -m commander_lab.studio import-state <DATEI> --verify`

Gemeldet werden im Issue #1703 nur Zahlen (`source_schema_version`, Zeilen je Tabelle, `content_sha256`, `n/N` aus `--check`, `not_exported`-Zeile, Exit-Codes). Daraus folgen zwei harte Weichen:
- **Blockierende Verweise > 0:** erst Ursache in der Sammlung/Zuordnung klären, bevor migriert wird.
- **`not_exported` (`simulation_run`/`simulation_card`) > 0 vs. 0:** bei 0 entfällt eine Altbestand-Übernahme; bei > 0 wird der Übernahmepfad in K-2c/K-2e fest eingeplant.

### Schritt 1 — Vorbereitung PR `K-2a2` + Vorab-Aufräumen (MATERIAL Klasse A)
1. **`state_export.py` → `studio-user-state-2`:** `tam_cardmarket_price` aufnehmen (Test-Fixtures strikt synthetisch, `AGENTS.md` §12); `experiment`/`experiment_arm` aufnehmen oder explizit in `NOT_EXPORTED` + `rebuild_index`-Vertrag dokumentieren; Abwärtskompatibilität zum Lesen von `studio-user-state-1` (Fixture-Test).
2. **Windows-Baseline schließen:** `windows-runtime.yml` um `test_studio_store.py`, `test_studio_cache_groups.py`, `test_studio_state_export.py`, `test_studio_backup.py` erweitern.
3. **Oberfläche vor dem Schnitt verkleinern:**
   - `tier_snapshot` (Tabelle, `tier_snapshot.py`, Aufrufer in `strength_view.py`, `import_all.py`, `ranking_check.py`, `web.py`) gemäß Q1/E4 entfernen.
   - `memo.py` ablösen (die 3 `memo.cached`-Stellen in `universe.py:467,1110` und `import_all.py:349` auf `cache.cached` umstellen → nur noch ein Cache-Anker D-1).

### Schritt 2 — K-2c: Schema 22 Dateischnitt (`reference.sqlite3` + `studio.sqlite3`) und Migration (MATERIAL Klasse A + Studio-Daten-Gate #1667)
- **K-2c1 (Store & Cache-Fundament):** `StudioStore` mit `studio.sqlite3` (16 Tabellen, `oracle_id`-Schlüssel, eigene `deck_source` oder Inline-Provenienz statt Cross-DB-FK) und `reference.sqlite3` (32 Tabellen + View `card_fact`); `store.count()` auf alle Tabellen synchronisieren; `cache.py` auf Dateigruppen je Datei umstellen; `backup.py` auf `studio-backup-2`; `oneclick.py`, `doctor.py`, `images.py`, `import_all.py`, `data_report.py` anpassen.
- **K-2c2 (Cross-DB-Abfragen & Skripte):** Die 14 `studio ↔ reference`-JOINs in 9 Modulen (13 produktive Abfragen in 8 Modulen + 1 Legacy-Migrationsabfrage in `store.py`) auf getrennte Abfragen + Python-Join umbauen; `ensure_scryfall_cards` entfernen; die 7 `sqlite3.connect`-Skripte und `studio_response_manifest.py` anpassen.
- **K-2c3 (Migrationsbefehl & Beweis):** CLI `python -m commander_lab.studio migrate-schema-22 [--dry-run] [--copy-to ORDNER]` (fail-closed bei blockierten Karten, Vorab-Backup, Staging-Aufbau, `PRAGMA integrity_check` + `foreign_key_check` + Zeilen-Gleichheit + Rückexport-SHA-256; `tam_cardmarket_guide*` werden dabei ausschließlich aus bereits lokal vorliegenden Dateien übernommen und nie automatisch aus dem Netz nachgeladen).
- **K-2c4 (Test-Suite):** Migration der 89 betroffenen `test_*.py` (44 HOCH → 40 MITTEL → 5 NIEDRIG) + `studio_synth.py`, volle `quality`/`security`/`infrastructure`/`windows-runtime`-Gates.
- **Abbruch-/Rückfall-Prüfpunkt:** Überschreitet K-2c1/K-2c4 das Budget um > 50 % oder schlägt der Windows-Nachweis fehl → geordneter Rückfall auf §6.5.

### Schritt 3 — K-2d: `simulate.sqlite3` als inhaltsadressiertes Partie-Archiv (MATERIAL Klasse A)
- Eigene Datei `simulate.sqlite3` (Schema 22, isolierte Verbindung, keine FKs auf `studio.sqlite3` oder `reference.sqlite3`): `sim_game` (PK `game_key` `studio-game-key-2`), `sim_series_game`, `meta`.
- Vollständig neu erzeugbar aus `games/series/<id>/manifest.json` + `journal.jsonl`; Kontingent statt Pflichtaufbewahrung; Determinismus-Wächter fail-closed bei Hash-Abweichung (`DETERMINISM_VIOLATION`).

### Schritt 4 — K-2e: Ablösung von `simulation_run` / `simulation_card` (MATERIAL Klasse A)
- Restliche Leser (`builder.py:1520-1600`, `evidence.py:271-310`, `data_report.py:491-496`, `web.py:667`) auf B1/`card_outcomes` bzw. `simulate.sqlite3` umhängen; Altbestand-Übernahme nur falls Owner-Export Zeilen > 0 meldet; danach `simulation_run`, `simulation_card`, `commander_binding.kind = 'simulation_run'` und `NOT_EXPORTED` bereinigen.
