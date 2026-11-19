# Brownfield-Bewertung Commander Studio (CPL): Neubau ja oder nein?

Stand: `main` @ `60be9fa8` (2026-11-19 12:15 UTC), Clone mit Tiefe 400 (First-Parent-Historie ab
2026-10-15, 536 Commits). Nur gelesen und statisch gemessen: keine Test-Suite, kein Engine-Lauf,
nichts gepusht, kein Issue/Kommentar. Legende: **[M]** selbst gemessen (Skript/grep/git),
**[D]** Doku oder Issue-Text sagt es, **[V]** Vermutung. Messskripte:
`/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad/costudio/brownfield_tools/`.

## 0. Ergebnis zuerst

**Empfehlung: kein Neubau. Option D „Härten plus drei gezielte Ersatz-Nähte“.**

1. Die Prämisse „alte Codebase“ trifft auf `studio/` nicht zu: das Paket ist **9 Tage alt** (erster
   Commit `b74cbe92`, 2026-11-10; seither 155 PRs, 66.018 eingefügte Zeilen, Nachbearbeitungsquote
   8,3 %) [M]. Was man misst, ist kein gealterter Code, sondern ein schnell gebautes System **ohne
   einen einzigen Konsolidierungsschritt** (0 Refactor-Commits von 536) [M].
2. Die Handwerksqualität ist messbar ordentlich: `mypy strict`, 0 × `Any` in `studio/`, 1.316 von
   1.317 Funktionen mit Rückgabetyp, 2,0 % exakte Duplikation, 0 TODO/FIXME, 1.361 Studio-Tests in
   252 s seriell, 53 von 60 Query-Parametern mit Grenzen [M].
3. Die echten Strukturmängel sind **lokal und benennbar**: (a) drei Cache-Mechanismen ohne
   Abhängigkeitsmodell, (b) vier getrennte Serien-/Partie-Orchestrierer über demselben
   Bridge-Client, (c) zwei Treiber desselben Bridge-Protokolls (PLAY greift auf private Methoden
   zu), dazu (d) ein 12-Modul-Importzyklus um `builder`, (e) kein Antwort-Vertrag zwischen Server
   und Seite, (f) 11,6 k Zeilen JS mit 8 ausgeführten Tests. Drei der sechs jüngsten Defekte sitzen
   genau in (a) bis (c).
4. Ein Greenfield-Kern kostet nach Eichung am bisherigen Tempo **55 bis 90 Lane-Tage** und eine
   vollständige Neu-Abnahme, liefert in der Zeit nichts Neues und schreibt gegen ein Ziel, das sich
   noch bewegt (Schema 1 → 21 in 9 Tagen) und dessen erste echte Abnahme (Owner-Sitzung 1, AK-1 bis
   AK-8) noch aussteht [M/D]. Option D kostet **16 bis 24 Lane-Tage**, beseitigt (a) bis (c) und
   erledigt dabei #1561, #1585, #1586 und die Grundlage für #1593.

## 1. Ist-Bewertung der Architektur

### 1.1 Größen (alle [M])

| Teil | Dateien | Zeilen | Bemerkung |
|---|---|---|---|
| `src/commander_lab` gesamt | 218 | 113.695 | nach S3-Aufräumen (−63.278 Zeilen in #1318, #1329, #1370, #1372) |
| `studio/` Python | 74 | 47.916 | 1.317 Funktionen, 223 Klassen (110 TypedDict, 44 dataclass) |
| `studio/static` JS | 24 | 11.638 | `app.js` 3.161, `tierliste.js` 2.451, `partie.js` 1.617 |
| `engine/` Python | 48 | 21.656 | Runner, Protokoll-Client, Piloten |
| `qualification/` Python (src) | 27 | 28.425 | Harness; `studio/` importiert daraus (s. 1.2) |
| `engine-bridge` Java main | 39 | 25.618 | **alles eigener Code**, ein Paket `org.commanderlab.xmage`; XMage selbst liegt nicht im Repo (`vendor/` 8 KB), sondern als Pin im Fork |
| `engine-bridge` Java test | 217 | 64.881 | „~90 k Java“ = 25,6 k Produktiv + 64,9 k Test |
| Tests Python | 471 | 104.581 (unit) + 39.683 (qualification) | davon Studio: 99 Dateien, 42.788 Zeilen, 1.361 Testfunktionen |
| `scripts/` | 119 | 42.549 | |
| `qualification/` Daten | — | 295 MB | versiegelt; `WS17_SHA256SUMS` 7.545 Zeilen, **0 Pfade unter `src/`** |

Vom Java-Produktivcode gehören 10.232 Zeilen (8 Dateien `XmageFullGame*`) zur produktiven
Full-Game-Lane, 9.824 Zeilen zu älteren Lanes (Midgame, Restoration, Causal, Phase 6,
`JsonlBridge`), die laut `config/rules_engines.json` („no longer the production runtime“) nicht
mehr Laufzeit sind [M]. Größte Einzeldatei: `XmageFullGamePlayer.java` 4.450 Zeilen.

### 1.2 Schichtung und Kopplung (`studio/`)

- **Importgraph** [M]: 312 interne Kanten, davon 42 als Import in Funktionsrümpfen. Auf
  Modulebene kein Zyklus; **mit den Funktions-Importen ein Zyklus aus 12 Modulen**: `builder`,
  `decks`, `universe`, `universe_view`, `universe_choice`, `strength_view`, `tier_snapshot`,
  `tiers`, `roles`, `sources`, `corpus_signals`, `research_import`. Die späten Importe sind genau
  das Werkzeug, mit dem der Zyklus lauffähig gehalten wird (`builder.py` allein 7 Stück).
- **Naben**: `store` Fan-in 55, `builder` 22 (Fan-out 10), `decks` 21, `universe` 14, `strength`
  13 (Fan-out **0**). `web` Fan-out 47, `__main__` 32, `strength_view` 15.
- **Keine Datenzugriffsschicht**: `store.py` ist Schema + Verbindung + 16 Methoden. **488
  `execute`-Aufrufe in 47 von 74 Modulen**, Zeilen als `sqlite3.Row` mit 727 `row["…"]`-Zugriffen.
  Spitzen: `builder.py` 75, `importers.py` 51, `universe.py` 31, `catalog.py` 30.
- **Schichtumkehr**: 5 Studio-Module importieren aus dem Qualifikations-Paket
  (`commander_lab.qualification.current_boundary.bridge_launcher`: `doctor.py:12`,
  `launch.py:296/492`, `paired_comparison.py:43`, `play.py:46`, `simulations.py:31`).
- **Architekturtest** existiert (`tests/architecture/test_layer_boundaries.py`), deckt aber nur
  `engine.*` und `models` ab, nichts in `studio/`.

### 1.3 Funktionslänge und Komplexität (`studio/`, [M], eigene AST-Zählung)

Median 14 Zeilen / CC 4; p90 69 Zeilen / CC 17. CC > 20: 103 Funktionen (7,8 %), CC > 50: 19
(1,4 %); länger als 100 Zeilen: 81 (6,2 %), länger als 200: 19.

| CC | Zeilen | Stelle | Einordnung |
|---|---|---|---|
| 223 | 1.936 | `web.py:518 create_app` | **Messartefakt**: Closure mit 118 Routen; Median je Route 12 Zeilen, Maximum 49 |
| 100 | 297 | `strength.py:2156 score_pool` | Fachkomplexität, reine Funktion |
| 73 | 253 | `decks.py:650 parse_decklist_text` | Parser |
| 67 | 302 | `ranking_check.py:328 check_ranking` (12 Parameter) | Prüfwerkzeug |
| 67 | 235 | `strength_view.py:1160 compute` | Lesemodell |
| 66 | 168 | `combos.py:567 _spellbook_shells_section` | |
| 65 | 192 | `paired_series.py:947 resume_series` | **Orchestrierung** |
| 65 | 256 | `similar_decks.py:501 browse_decks` (11 Parameter) | |
| 63 | 345 | `importers.py:1698 import_playgroup_atlas` | Import |
| 63 | 263 | `tokens.py:31 deck_tokens` | |
| 61 | 232 | `swap.py:159 swap_candidates` (11 Parameter) | |
| 59 | 192 | `paired_comparison.py:807 parallel_window_player` (**19 Parameter**) | **Orchestrierung** |
| 58 | 116 | `edhrec_capture_proof.py:55 verify_captures` | |
| 56 | 145 | `paired_comparison.py:335 _summarize` | Statistik |
| 54 | 190 | `paired_series.py:1190 simulator_readiness_audit` | |
| 53 | 167 | `deck_modules.py:286 compile_modules` | |
| 53 | 186 | `packages.py:829 deck_doctor_remedies` | |
| 52 | 184 | `__main__.py:813 _run` | CLI-Verteiler |
| 51 | 136 | `simulations.py:291 extract_game_log_telemetry` | |
| 48 | 206 | `play.py:694 _run` | **Protokolltreiber, s. 1.8** |

Zum Vergleich `engine/`: `full_game_pilot/choices.py:619 _decide_boolean` CC 148 / 403 Zeilen,
`priority.py:41` CC 85, `policy.py:52` CC 82 [M]. Das ist Pilot-Entscheidungslogik (MATERIAL,
`AGENTS.md` §10) und nicht Gegenstand eines Studio-Umbaus.

**Duplikation** [M] (Fenster aus 6 normalisierten Zeilen): `studio/` 2,0 % (dateiübergreifend
0,3 %), JS 0,8 %, `engine/` 1,6 %, Studio-Tests 4,6 %. Exakte Kopien sind kein Problem. Die
relevante Duplikation ist **semantisch** und wird von so einer Messung nicht erfasst: zwei
Protokolltreiber, vier Orchestrierer, drei Caches (1.4, 1.7, 1.8).

### 1.4 Cache- und Datenepoche-Logik

Drei Mechanismen nebeneinander [M]:

1. `cache.py` (145 Zeilen): Schlüssel = Dateistempel des Stores (`cache.py:62-81`: Pfad,
   Änderungszähler, Größe, mtime, WAL). 14 Aufrufstellen. **Jeder bestätigte Schreibvorgang
   verwirft alles** (so dokumentiert, `cache.py:4-9`), auch Werte, die nur von Importdaten abhängen.
2. `memo.py` (111 Zeilen): Schlüssel = „Datenepoche“, ein heuristischer Fingerabdruck aus
   `COUNT/MAX/SUM` über 13 Tabellen (`store.py:1024-1051`). 3 Aufrufstellen. Die Datei sagt selbst,
   was sie nicht sieht (`memo.py:17-20`: Änderung bestehender Zeilen per Hand; `memo.py:22-24`:
   Netz-/Sync-Ordner), dazu eine 2-Sekunden-Sperre für frische Dateien (`_STAT_GUARD_NS`).
3. Einzelstücke: `functools.lru_cache` (7 Stellen), `builder._combo_partners` mit eigenem
   Lock (`builder.py:713`), `StudioStore._epoch_cache` (`store.py:1058-1067`).

Belegte Schwächen:
- `builder.py:276-287` (`_corpus_hits`): der Kommentar begründet die Wahl des Dateistempels damit,
  dass ein Importer Kartennamen ändern kann, **ohne dass die Datenepoche sich bewegt**. Die Epoche
  ist also nach eigener Aussage nicht tragfähig genug für diese Zahl; welcher Cache richtig ist,
  entscheidet der Autor je Funktion von Hand.
- Kein Schutz gegen Veränderung geteilter Werte: „The caller must treat the returned value as
  read-only“ (`cache.py:85`, `memo.py:31`); eine einzige Stelle kopiert (`web.py:445`
  `copy.deepcopy`). Fehlerrisiko: ein Aufrufer, der ein gecachtes dict ergänzt, verfälscht alle
  späteren Antworten bis zum nächsten Schreibvorgang. Kein Test dagegen gefunden [M: grep], daher
  UNKNOWN, ob es heute vorkommt.
- Sperr-Hierarchie nur als Prosa (`cache.py:89-92` „Today: … never the other way round“).
- Gemessene Wirkung [D: #1561]: `POST /api/strength` 0,07 s → 5,2–5,6 s nach einem Favoriten-Klick
  bei byte-identischer Antwort (11,8 MB).

Urteil: fachlich vorsichtig (lieber neu rechnen als veraltet liefern), strukturell die schwächste
Stelle des Pakets. 256 Zeilen Kern, 17 Aufrufstellen: klein genug für einen sauberen Ersatz.

### 1.5 Datenmodell

- Schema 21 (`store.py:17`), 44 Tabellen im Schema-Text (dazu 7 `_new`-Tabellen in der
  Schema-17-Migration), 25 `CREATE INDEX`, 52 `REFERENCES`, 7 `CHECK`, 20 `WITHOUT ROWID`,
  `PRAGMA foreign_keys=ON` (`store.py:822`). Kein WAL (kein `journal_mode` im Code) [M].
- Der ganze Schema-Text läuft bei **jedem** Öffnen (`store.py:823`), und jede Anfrage öffnet eine
  eigene Verbindung (92 × `open_store()` in `web.py`). Gemessen auf einem leeren Store: 0,97 ms je
  Öffnen+Schließen (n = 200) [M]; auf dem 254-MB-Store UNKNOWN, vermutlich ähnlich [V].
- **Migrationen**: Kette aus `if current < N` in `_prepare` (`store.py:833-861`) mit Schritten
  für 10, 12, 16, 17, 18; 19 bis 21 sind rein additiv. Tests für 12, 13, 14, 16, 17 vorhanden
  (`test_studio_schema_migration.py`, `test_studio_store.py:600/933`, `test_studio_labels.py:124`).
  Kein Rückweg, keine Sicherung vor einer Migration im Code; `backup.py` (231 Zeilen) gibt es seit
  2026-11-18 als eigenen Befehl.
- **Schema-Tempo**: Version 1 am 2026-11-10, Version 21 am 2026-11-18 [M: `git log -G`]. Das
  Modell wird noch gefunden.
- **Invarianten-Lücke**: `observation` hat nur einen Ersatzschlüssel (`store.py:142-155`,
  `AUTOINCREMENT`), keine natürliche Eindeutigkeit. Die Import-Dubletten (#1548) wurden im Importer
  abgefangen, nicht im Schema; „Bestehende Zeilen werden nicht gelöscht“ [D: Commit `60be9fa8`].
  `corpus_deck.legality_audit` wird geschrieben, aber von nichts gelesen [D: #1549].
- **Typisierung**: 0 × `Any`, dafür 674 × `dict[str, object]`, 141 × `Mapping[str, object]`;
  340 von 1.317 Funktionen (26 %) geben `dict[str, object]` oder eine Liste davon zurück; 1.278
  `.get("…")`, 675 `isinstance(` [M]. Formal streng, praktisch „Wörterbuch als Datentyp“: der
  Typprüfer sieht keine Feldnamen. Ausnahme: `strength.py` arbeitet mit dataclasses
  (`StrengthSettings`, `PoolContext`, `CardStrength`).
- Stille Ersatzwerte: `simulations.py:53-72` (`_as_int`/`_as_float`, Vorgabe 0, 18 Aufrufe) und
  `simulations.py` `rounds=_as_int(exec_res.get("rounds"), 10)` (ein unbekannter Wert wird 10);
  85 × `or 0` in `studio/`. Ob eine dieser Stellen die Regel „unbekannt nie 0“ in einer sichtbaren
  Zahl verletzt, ist UNKNOWN (nicht einzeln geprüft); es ist die Stelle, an der man suchen sollte.

### 1.6 Web-Schicht (`web.py`, 2.454 Zeilen)

- 114 Routen-Dekoratoren in einer einzigen Closure `create_app` (118 innere Funktionen) [M].
  Die Routen selbst sind dünn; die Datei ist „God-Modul“ im Sinn der Kollision, nicht der Logik:
  67 Commits in 9 Tagen, höchster Wert im Repo, und sie steht in der Kollisionsliste
  (`docs/STUDIO_AGENT_ONBOARDING.md` §3).
- Eingaben gut: 39 Pydantic-Body-Modelle, 101 `Field(`-Grenzen, 53 von 60 `Query(` mit Grenzen;
  Host-Prüfung, Schreib-Marker `x-studio`, CSP, `no-store` (`web.py:541-558`).
- **Ausgaben ohne Vertrag**: 116 Routen geben `dict`/`list` zurück, 0 `response_model`,
  `openapi_url=None`. Zwischen Server und den 11,6 k Zeilen JS gibt es keine maschinenlesbare
  Schnittstelle.
- **Fehlervertrag über Ausnahmetypen**: 51 × `except KeyError` → 404, 35 × `except ValueError` →
  422 (135 `HTTPException`; mit Status als Literal gezählt: 70 × 404, 47 × 422, 10 × 409, 2 × 504). Ein `KeyError` aus einem
  Programmierfehler wird so zur Meldung „nicht gefunden“. Beispiel für die Folge:
  `web.py:642-645` unterscheidet zwei 404-Fälle über `str(error).strip("'") == profile`.
- 92 × dasselbe `store = open_store(); try: …; finally: store.close()`.

### 1.7 Simulationspfad und JVM-Lebenszyklus

Über demselben Client (`engine/rules/full_game.py:542 _RawFullGameClient`) gibt es **vier
Ausführungswege** [M]:

| Weg | Stelle | Mechanik |
|---|---|---|
| Engine-Batch | `engine/rules/full_game_batch.py:656/723` | Process- oder Thread-Pool |
| Studio-Serie | `simulations.py:1039` + `:1203 _process_chunk` | Threads → je Stück ein Python-Kindprozess (`python -m commander_lab.studio play-batch`) → JVM; Fortschritt über stdout-Zeilen |
| Gepaarte Serie | `paired_comparison.py:902/973` | Threads im selben Prozess → JVM; eigene Stück-Planung je Look-Fenster |
| Interaktive Partie | `play.py:477` | ein Thread, eigener Protokolltreiber |

Dazu drei Verwalter mit je eigenen Sperren, eigenem Abbruch, eigener Wiederaufnahme und eigenem
Ablageformat: `SimulationBatchManager` (`simulations.py:1321`), `PairedSeriesManager`
(`paired_series.py:653`, drei Locks in `:439-441`, PID-Lock-Datei, JSONL-Fortschritt),
`InteractivePlayManager` (`play.py:1023`). Gemessene Folge [D: #1585]: gepaart 350 Partien/h gegen
595 im Batch auf derselben Maschine; [D: #1586]: Fortschritt nur je Stück. Beide Issues sind
Symptome derselben fehlenden gemeinsamen Ausführungsschicht.

Gut: Identitätsnachweis je Seed (semantischer Transkript-Hash, `full_game.py:1875`),
`bridge_jar_sha256` und Bridge-Zustand an jedem Ergebnis, eigene Fehlerklassen statt Niederlage.

### 1.8 PLAY-Pfad und Bridge-Grenze

- **Draht-Protokoll**: versioniert (`protocol_version 2.0.0`, `config/rules_engines.json`),
  JSON-Zeilen über stdin/stdout, Schema-Verzeichnis `schemas/engine_protocol`, 17 Nachrichtentypen
  im Java-Verteiler (`XmageFullGameJsonlBridge.java:74-94`), Entscheidungen nur als `option_id`
  aus `legal_options`. Die Grenze selbst ist das bestdefinierte Stück des Systems.
- **Zwei Treiber desselben Protokolls**: der Runner (`full_game.py:1482 _open_game`, `:1528
  _drive`) und `play.py:694-899 _run`, der Start, Handshake, Deck-Import, Spielanlage und die
  Entscheidungsschleife noch einmal ausschreibt. Dabei ruft Studio-Code private Methoden des
  Runners auf (`play.py:701 runner._validated_policy`, `:715 _validate_handshake`, `:722
  _deck_payload`, `:871 XmageFullGameRunner._build_result`, `:811 client._transport_failure`), der
  Client ist als `object` typisiert, 18 der 57 `type: ignore` des Pakets stehen in `play.py`.
  `play.py:128-161` überschreibt zusätzlich zwei private Methoden per Unterklasse
  (`# type: ignore[override]`) und schluckt Fehler beim Ereignis-Export (`except Exception: pass`).
  Fehlerrisiko: eine Protokolländerung muss an zwei Stellen nachgezogen werden, der Typprüfer hilft
  an keiner der beiden.
- **Verdeckte Information hängt am Studio-Code**: Die Schwärzung der KI-Hände für den Mensch-Sitz
  liegt in Python (`games.py:548`, `:579`; `play.py:540`, `:587`). Das ist AK-5 und `AGENTS.md` §5;
  jeder Umbau dieser Stelle braucht den vorhandenen Lecktest.
- **Seite**: Zustandsabfrage im Takt (400 ms / 1.500 ms / 150 ms, [D: #1593]); `boardclick.js`
  (226 Zeilen) ist als reine Funktion gebaut und wird per `node` gegen eine Fixture getestet.
- **Bridge (Java)**: 31 Commits unter `engine-bridge/src/main` seit 2026-10-15, davon 3 seit dem
  Studio-Start [M]. `XmageFullGameSession.java` synchronisiert über `synchronized` und einen
  Engine-Thread mit `SETTLE_TIMEOUT = 75 s` (`:1153`). Tiefere Bewertung der Java-Qualität: UNKNOWN
  (nur Größe und Struktur gemessen).

### 1.9 Frontend

24 klassische Skripte ohne Module und ohne Build (`index.html:9` und `:76-92` laden 18 davon), 3.073 ×
`h()`, 2 × `innerHTML` [M]. `app.js`: ein globales `state` mit 70 Feldern und 122 Zuweisungen,
198 Funktionen, größte `renderSimulations` 245 Zeilen; `tierliste.js` 194 Funktionen und 97
Konstanten auf oberster Ebene. Nebenläufigkeit ist durchdacht (`app.js:404-455`: Speicher-Kette,
Änderungszähler, Konflikterkennung).

**Testbarkeit ist die Schwachstelle**: von 1.361 Studio-Testfunktionen führen **8** JS über `node`
aus; **74** prüfen JS/HTML nur als Text per Regex (30 davon in `test_studio_static_guards.py`) [M].
Das passt zur Fehlerdichte: `app.js` hat mit 10 von 64 die meisten Fix-Commits einer Datei,
`tierliste.js` 5 von 40.

### 1.10 Testlage

- Studio: 99 Dateien, 42.788 Zeilen, Verhältnis Test zu Code 0,89; 252 s seriell laut
  `tests/pytest_shard_weights.json` (gesamt 795 s, 377 Dateien) [M].
- Echte SQLite in 88 von 100 Dateien, HTTP über `TestClient` in 153 Tests, nur 1 Datei mit Mocks,
  171 `monkeypatch`-Stellen in 33 Dateien. **Tautologie-Anteil: nicht belegbar hoch.** Näherung:
  5 Testfunktionen ohne `assert`/`raises` im Rumpf; 74 reine Quelltext-Prüfungen (5,4 %), die
  Schreibweise statt Verhalten sichern.
- **Kopplung an Interna**: 70 Testdateien führen selbst SQL gegen das Schema aus (553 `execute`),
  85 Zugriffe auf private Namen in 22 Dateien [M]. Das Schema ist der faktische Vertrag.
- Kernpfade gegen die echte Engine: `test_human_seat_play_1169.py` (2.208 Zeilen) überspringt ohne
  Engine und läuft im Workflow `studio-human-seat-real-engine.yml`; 42 Testfunktionen nennen
  nachgebaute Clients oder Executor (`Fake…`). Abdeckungsgrad in Prozent: UNKNOWN (nicht gemessen, keine Suite gestartet).
- Flakiness: in der Historie ein Fund (`7ff89f60`, gzip-mtime in einer Test-Fixture) und eine
  Kanonisierung (`d9496feb`). Rate aus CI-Läufen: UNKNOWN (CI-Historie nicht ausgewertet).

### 1.11 Churn, Fehlerdichte und die Defekte der letzten Tage

Studio-PRs seit 2026-11-10 [M]: 155, davon 88 feat, 22 fix (14 %), 6 perf, 0 refactor. Hotspots
(Commits / fix-artige): `web.py` 67/3, `app.js` 64/10, `__main__.py` 41/3, `tierliste.js` 40/5,
`index.html` 30/3, `builder.py` 27/2, `strength_view.py` 24/4, `store.py` 24/0, `strength.py`
18/4, `signals.py` 18/4. Fünf der zehn sind dokumentierte Kollisionsdateien.

| Defekt | Beleg | Einordnung |
|---|---|---|
| Cache verwirft nach jedem Schreibvorgang alles | #1561; `cache.py:4-9` | **Architektursymptom**: Entwurfsentscheidung ohne Abhängigkeitsmodell (1.4) |
| Dubletten im Import | #1548, `60be9fa8`; `store.py:142-155` | **Architektursymptom**: fehlende Eindeutigkeit im Schema, im Importer geflickt (1.5) |
| Gepaart 350 gegen 595 Partien/h, Fortschritt je Stück | #1585, #1586 | **Architektursymptom**: vier Ausführungswege (1.7) |
| Datenbericht rechnet je Commander den ganzen Pool neu | #1562, `f0286769` | mildes Symptom: kein leichtes Lesemodell, schwere Funktion für eine Zählung benutzt |
| Join-Reihenfolge | #1560, `bbe1eba4` (12 Zeilen + Plan-Wächter) | normaler Bug; SQL in 47 Modulen macht ihn schwerer zu finden |
| Reihenfolge gleichzeitiger Ereignisse im Log | #1595, `d9496feb` | Grenz-Symptom: Reihenfolge an der Bridge nicht kanonisch, in Python kanonisiert |
| Engine-Hänger nach `declare_attackers`, 4 von 80 Partien | #1584 | normaler Bug an der schwierigsten Stelle; Ursache UNKNOWN (Diagnose geschwärzt). Ein Studio-Neubau behebt ihn nicht |
| Zeitstempel in Test-Fixture | `7ff89f60` | normaler Test-Bug |

Bilanz: drei klar strukturell, zwei mild, drei normal. Die strukturellen sitzen in genau den drei
Nähten, die Option D ersetzt. Keiner der acht ist ein Argument für einen Neubau der übrigen 90 %.

**Wer hat was geschrieben?** Aus Git nicht belegbar: 75 % der eingefügten Studio-Zeilen stehen in
Commits ohne modellgenauen Trailer (33 % „Claude“ ohne Version, 25 % Merge-Commits, 17 % ohne
Trailer); eindeutig zugeordnet sind 3,4 % und 3,2 % [M]. Ein Zusammenhang zwischen Autor und
Qualität ist damit UNKNOWN und trägt keine Entscheidung.

### 1.12 Der frühere Brownfield-Entwurf (2026-10-05)

Commit `85e376c2`, 894 Zeilen, liegt unverändert auf `main` als
`docs/architecture/commander-simulator-next-brownfield-architecture.md` (Status im Kopf weiter
„PROPOSED / pre-Freeze“) [M]. Er behandelt den **Simulator-Kern**, nicht das Studio (das es erst
ab 2026-11-10 gibt).

| Vorschlag | Stand heute |
|---|---|
| Option A „Provider-Prozess-Hybrid, Python-Steuerung“ empfohlen; B „alles in Java“ nur bei Bedarf; C „eigene Regel-Engine“ verworfen | **umgesetzt und eingefroren** (Freeze-ADR 2026-10-10, D1: XMage; `PRODUCTION_PROVIDER = XMAGE`) |
| JSON-Zeilen über stdin/stdout, versioniert | umgesetzt (Protokoll 2.0.0) |
| Pydantic an Vertrauensgrenzen | umgesetzt in `engine/`, `models/`, `web.py`-Eingaben; nicht bei Antworten |
| Piloten außerhalb der Engine, nur Wahl unter legalen Optionen | umgesetzt (D2/D17) |
| „Ein Spiel = ein Prozess“, dauerhafte JVM nur nach Äquivalenznachweis | Freeze-ADR hält AF11 fest (`:125`, `:189`); das Studio spielt mehrere Partien je JVM. Deshalb `BRIDGE_AHEAD_OF_QUALIFICATION` und `SIMULATED_RESULT` |
| Auswertung in Parquet/DuckDB | **nicht umgesetzt**: keine solche Abhängigkeit; SQLite plus gz-JSONL. Ein Verwerfungsbeleg wurde nicht gefunden (UNKNOWN, warum) |
| „CLI zuerst, Web später und umkehrbar“ | überholt durch den Owner-Entscheid vom 2026-11-10 (Studio BUILD/PLAY/SIMULATE) |
| Eigenes Production-Repository, offene Lizenz | nicht umgesetzt: `AGENTS.md` §1 „Do not create the Production Repository“; Lizenz `LicenseRef-Proprietary`; Sichtbarkeit Owner-Sache (#1108) |
| Ergebniszustände `SUPPORTED_DECISION / INCONCLUSIVE / INVALID_OR_UNSUPPORTED` | teilweise (`SUPPORTED_DECISION` in 4 Dateien, `INCONCLUSIVE` in 0; Studio nutzt `NOT_DECIDED`) |
| Spike C „Pilot-Qualitäts-Tor“ | offen, heute G-SIM Punkt 2 |
| Forge als Referenzspalte | fallengelassen (D1) |

Lehre: Die Grundarchitektur wurde vor sechs Wochen schon einmal als Brownfield entschieden, vom
Owner unterschrieben und hält. Was fehlt, ist nicht eine neue Grundarchitektur, sondern die
Innenordnung des seither angebauten Studios.

## 2. Was nicht verhandelbar ist und was es für einen Umbau kostet

| Rahmen | Quelle | Was er für einen Neubau bedeutet |
|---|---|---|
| XMage allein entscheidet Regeln; keine Erste-/Zufalls-/Standardoption | `AGENTS.md` §2 | Jede neue Seite oder jeder neue Server kann unbemerkt Legalität nachbauen (Brett-Klick, Vorspulen, Deck-Prüfung). Der heutige Stand ist an diesen Stellen geprüft; neu Gebautes nicht |
| Studio-Bridge-Gate, `BRIDGE_AHEAD_OF_QUALIFICATION` ehrlich | §10 | Der Zustand ist quer verdrahtet: 10 src-Dateien, 7 JS-Dateien, 8 Testdateien; `SIMULATED_RESULT` in 17 src-Dateien [M]. Jede davon muss neu entstehen und neu belegt werden. Bridge-Änderungen brauchen NEUTRAL/BEHAVIOUR-Nachweis und PB-03 |
| Owner-Vorbehalte: Fork-Push/Repin, `qualification/`, WS17, 5/6 Sitze, Sichtbarkeit, Bezahldienste | §8 | `WS17_SHA256SUMS` bindet 0 Pfade unter `src/`: ein Studio-Umbau berührt die Siegel nicht. Aber `pyproject.toml` und `requirements/lock.txt` sind siegelgebunden: **keine neue Abhängigkeit ohne Owner-Go**. „Perfekt neu“ heißt also weiter FastAPI, Pydantic, `sqlite3`, JS ohne Build. ORM, TypeScript, Bundler, UI-Framework wären je ein Owner-Entscheid plus Neuversiegelungs-Frage |
| Sitz-Sperre 2 bis 4 | E-Tabelle 2026-11-18 | Heute an drei Stellen erzwungen (`launch.py:37/710`, Serien-Routen, `compare-decks`); muss mit Test wiederkommen |
| Verdeckte Information | §5, AK-5 | Schwärzung liegt im Studio-Python (1.8) |
| Datenkontinuität | Scope „Backup“ | Der Owner-PC-Store ist die einzige Kopie von Deck-Verlauf, Markierungen, Serien. Ein neues Schema heißt Migration von 254 MB / 913.063 Zeilen `corpus_deck_card` plus Nutzerzustand unter Windows, mit Sicherung und Owner-Zeit. 70 Testdateien hängen am heutigen Schema |
| Windows-Owner-PC, Release-Artefakt, keine Telemetrie | Scope „Release und Betrieb“ | Prozess-, Lock- und Pfadcode (`full_game.py:508-522` zwei Plattformzweige, PID-Locks) ist die Art Code, die beim Neuschreiben unter Linux grün und unter Windows kaputt ist |
| Kernregeln: Gewicht `simulation` = 0, n/N + Herkunft, „unbekannt“ nie 0, Kohorten getrennt, keine Preise, Chulane | Scope, E2 | Durch Tests gesichert (`test_studio_simulation_weight_zero.py`, Preis-Wächter `test_studio_static_guards.py:67`, 210 × „unbekannt“ in JS). Tests dürfen nicht gelöscht oder geschwächt werden (§4, §9): ein Neubau muss 1.361 Tests **umziehen**, und jede Änderung an bestehenden Tests färbt `ci-definition-integrity-shadow` rot |
| Merge-Gate, Kreuz-Review, Kollisionsregel „nichts verschieben oder umbenennen“ | §10, Onboarding §3 | Großflächiges Verschieben kollidiert mit der Regel und mit den Pfadfiltern der Workflows (Workflow-Änderung = MATERIAL) |

Kurz: Die Siegel selbst machen einen Studio-Umbau nicht teuer. Teuer machen ihn das
Abhängigkeits-Verbot, die Test-Umzugspflicht, die Datenmigration am Owner-PC und die quer
verteilten Ehrlichkeits-Regeln.

## 3. Optionen

**Eichung** [M/V]: Der Studio-Aufbau 10. bis 19.11. waren 155 PRs und 109.478 eingefügte Zeilen
(Code plus Tests) in 9 Tagen. Bei 3 bis 5 parallelen Lanes (aus Branch-Präfixen geschätzt, [V])
sind das **rund 36 Lane-Tage (27 bis 45)**. Ein Lane-Tag = eine Agent-Lane über einen Kalendertag
einschließlich Review und CI. Token absolut: UNKNOWN (keine Verbrauchsdaten); unten als Vielfaches
dieses Referenzaufwands R.

| | A Behalten und härten | B Strangler breit | C Greenfield-Kern `studio/` | **D Hybrid (Empfehlung)** |
|---|---|---|---|---|
| Idee | Mängel an Ort und Stelle flicken | alle Kernmodule hinter Schnittstellen neu | BUILD, SIMULATE, PLAY neu; Bridge, Engine, Qualifikation bleiben | A für das meiste, Neubau nur für drei Nähte |
| Lane-Tage | 12–18 (±40 %) | 30–45 (±50 %) | 55–90 (±60 %) | 16–24 (±40 %) |
| Wanduhr | 5–8 Tage, 2 Lanes | 3–5 Wochen, 2–3 Lanes | 3–5 Wochen, 4 Lanes, Feature-Stopp | 6–10 Tage, 2 Lanes |
| Token (× R) | 0,3–0,5 | 0,8–1,2 | 1,5–2,5 | 0,45–0,65 |
| Regressionsrisiko | niedrig | mittel (lange Doppelführung) | hoch (alles neu abzunehmen) | niedrig bis mittel, je Naht mit Identitätsnachweis |
| Owner-Aufwand | keiner zusätzlich | 1 Entscheid, sonst keiner | Feature-Stopp, Migration am PC, komplette Neu-Abnahme (beide Sitzungen neu, 4–6 h [V]) | 1 Entscheid; Sitzung 1 wie geplant |
| In der Zeit nicht lieferbar | nichts | Features um 30–50 % langsamer | alles: S2 bis S6 verschieben sich um die volle Dauer | nur Arbeit an den drei Nähten |
| Strukturmängel danach | (a) bis (c) gemildert, nicht beseitigt; Zyklus bleibt | beseitigt | beseitigt, neue unbekannt | (a) bis (c) beseitigt; Zyklus und Web-Ordnung per Wächter und „bei Berührung“ |

### Option A: Behalten und härten
- Erste drei Pakete: (1) #1561 als Markierung „nur Importdaten / Nutzerzustand“ in `cache.py`;
  (2) #1586, dann #1585 innerhalb von `paired_comparison.py`; (3) `web.py`: Store als
  Abhängigkeit, Fachausnahmen statt `KeyError`/`ValueError`.
- Abnahme: Wartezeit nach Klick < 0,2 s bei gleicher Antwort; gepaart ≥ 560 Partien/h mit gleichen
  Hashes; 86 `except`-Zuordnungen auf Fachausnahmen.
- Abbruch: wenn Paket 2 ohne gemeinsame Ausführungsschicht nicht auf Batch-Niveau kommt, wechseln zu D.
- Schwäche: die Anzahl der Wege bleibt (3 Caches, 4 Orchestrierer, 2 Treiber); die nächsten
  Features zahlen wieder.

### Option B: Strangler über alle Kernmodule
- Erste drei Pakete: (1) Antwort-Vergleich über alle Leserouten auf einer Store-Kopie; (2)
  Datenschicht `studio/data/` über dem **unveränderten** Schema, beginnend bei `builder` (75
  SQL-Stellen); (3) Cache-Schicht.
- Reihenfolge danach: Orchestrierung, PLAY-Sitzung, Frontend-Module.
- Abnahme: je Modul gleiche Eingabe → byte-gleiche Antwort; 488 SQL-Stellen außerhalb der
  Datenschicht → 0.
- Abbruch: wenn nach 10 Lane-Tagen weniger als ein Drittel der SQL-Stellen umgezogen ist.
- Schwäche: 47 Module anfassen, um SQL zu verschieben, ohne dass der Owner etwas davon sieht; hohe
  Kollision mit laufenden Lanes; der Nutzen der Datenschicht ist bei einem Ein-Nutzer-SQLite-Werkzeug
  begrenzt.

### Option C: Greenfield-Kern
- Erste drei Pakete: (1) Ziel-ADR, eingefrorener HTTP-Vertrag aus den 114 Routen, Goldantworten;
  (2) neues Schema 22 mit Migrationswerkzeug und Rückweg; (3) BUILD neu bis zur Antwortgleichheit.
- Abnahme: alle Goldantworten gleich; alle 1.361 Tests umgezogen und grün; Serien-Identität je
  Seed; AK-1 bis AK-8 neu am Owner-PC.
- Abbruch: Meilenstein „BUILD antwortgleich“ nach 20 Lane-Tagen nicht erreicht; oder ein
  Transkript-Hash weicht unerklärt ab.
- Schwächen, mit Beleg: schreibt gegen ein bewegtes Ziel (21 Schema-Versionen in 9 Tagen); die
  erste Owner-Abnahme fehlt noch, man würde also neu bauen, ohne zu wissen, was den Owner stört;
  die neuen Technikoptionen sind durch das Abhängigkeits-Verbot dieselben wie heute; die gemessene
  Qualität des Bestands rechtfertigt den Verlust nicht (1.3, 1.10).

### Option D: Hybrid (empfohlen)
**D-0 Messnetz (2–3 Lane-Tage), zuerst.** (i) Antwort-Vergleich: 25 bis 30 Leserouten gegen eine
Store-Kopie, SHA-256 je Antwort, vorher/nachher; (ii) Architekturtest für `studio/`: kein Zyklus
über die heutigen 12 Module hinaus (Zahl darf nur sinken), kein Import aus `qualification.*`
außer über eine Fassade; (iii) Zählwerte aus Abschnitt 1 als Datei, damit „besser“ messbar ist.

**D-1 Cache-Schicht neu (3–4).** Ein Mechanismus statt drei: jeder Eintrag erklärt seine
Tabellengruppe („Importdaten“, „Nutzerzustand“, „beides“); Schreibrouten erklären, was sie ändern;
Werte unveränderlich oder kopiert. Ersetzt `cache.py` und `memo.py`, erledigt #1561 und ist die
Grundlage für #1563. Abnahme: `/api/strength` nach Favoriten-Klick < 0,2 s, byte-gleich; nach
Import jede betroffene Antwort neu; Test, der ein gecachtes Objekt zu ändern versucht und scheitert.

**D-2 Ausführungsschicht für Serien (5–7).** Ein Spiele-Pool: je Worker ein Prozess mit
langlebiger JVM, Warteschlange, Rückruf je beendeter Partie, ein Abbruch- und
Wiederaufnahme-Vertrag. Batch-Serie und gepaarte Serie werden Kunden davon; die Statistik
(`paired_comparison._summarize`, O'Brien-Fleming, Intervalle) bleibt unangetastet. Erledigt #1585
und #1586. Abnahme: gleiche Seeds → gleicher Transkript-Hash, Sieger, Entscheidungszahl, n von N
mit N ≥ 40; gepaart ≥ 560 Partien/h auf der 4-Kern-VM (heute 350); Studio-Orchestrierer 3 → 1.

**D-3 Ein Protokolltreiber (3–5).** Öffentliche Sitzungs-Schnittstelle in
`engine/rules/full_game.py` (öffnen, nächste Entscheidung, antworten, Ergebnis), typisiert;
`play.py` und der Runner benutzen dieselbe. Abnahme: 0 private Zugriffe aus `studio/` (heute 5),
`type: ignore` in `play.py` 18 → höchstens 2, Echt-Engine-Test des Mensch-Sitzes grün, Lecktest
grün. Danach lässt sich #1593 (Melden statt Abfragen) an einer Stelle bauen.

**Danach, „bei Berührung“ (3–5, gestreckt):** `web.py` in Router je Fläche mit Store-Abhängigkeit
und Fachausnahmen (entschärft die Kollisionsdatei); Antwort-Typen für die zehn meistgenutzten
Routen; reine Logik aus `app.js`/`tierliste.js` in `node`-getestete Dateien nach dem Muster
`boardclick.js`; Eindeutigkeit für `observation` als Schema 22 (Owner-Entscheid 3).

Abbruchkriterien D: eine Naht überschreitet ihr Budget um mehr als 50 %; eine Hash-Abweichung
bleibt nach zwei Tagen unerklärt (dann zurück auf den alten Weg, Naht bleibt Schalter); Owner-Sitzung
1 zeigt Produktmängel, die wichtiger sind (dann D-3 und „bei Berührung“ verschieben).

### Modul-Urteil (für A, B und D gleich)

| Urteil | Module | Begründung |
|---|---|---|
| **Gut genug, bleibt** | `strength.py` | reine Rechnung, Fan-out 0, dataclasses, 3.366 Testzeilen |
| | `store.py` Schema | 52 Fremdschlüssel, getestete Migrationen, 70 Testdateien hängen daran |
| | `paired_comparison.py` Statistikteil, `card_outcomes.py`, `castability.py` | Fachlogik mit Tests; nur die Ausführung ist das Problem |
| | `games.py` (Aufzeichnung, Schwärzung), `launch.py`, `backup.py`, `doctor.py` | klar abgegrenzt |
| | `boardclick.js`, `search.js`, `vorspulen.js`, `ui.js` | klein, teils per `node` getestet |
| | `engine-bridge/`, Piloten, `qualification/` | außerhalb des Auftrags, durch Gate und Siegel gebunden |
| **Profitiert am meisten** | `cache.py` + `memo.py` | D-1 |
| | `simulations.py`, `paired_series.py`, `play_batch.py`, Ausführungsteil von `paired_comparison.py` | D-2 |
| | `play.py` (`_run`, `_RecordingRunner`) | D-3 |
| | `web.py` | Struktur, nicht Inhalt |
| | `builder.py` (Fan-in 22, 75 SQL, 7 späte Importe), `strength_view.py` (Fan-out 15) | Kern des Zyklus; schrittweise entflechten, nicht neu schreiben |
| **Erst Testnetz, dann anfassen** | `app.js`, `tierliste.js`, `partie.js` | höchste Fix-Zahl, 8 ausgeführte Tests |
| **Kandidaten zum Entfernen (prüfen nach §9)** | `spellbook_shells.py`, `subarchetypes.py` | kein Importeur unter `src/`, nur Skripte und Tests [M] |
| | ältere Lanes: 9.824 Zeilen Java, rund 5.050 Zeilen Python (`tactical`, `bridge`, `phase85`, `structural`) | nicht Laufzeit; Entfernen nur, wenn kein `qualification/`-Datensatz den Pfad nennt (Lead/Owner) |

### Laufende Pakete

| Paket | Empfehlung |
|---|---|
| #1561 Cache über Schreibvorgänge | **jetzt, als D-1** bauen (neue Schicht statt Flicken in `cache.py`) |
| #1563 teure Leserouten puffern | **warten bis D-1**, dann klein (nur Aufrufstellen) |
| #1586 Fortschritt je Partie | **jetzt**, als erster Schritt von D-2 (Rückruf in `run_batch`) |
| #1585 langlebige Worker-JVMs | **jetzt, als D-2**; nicht mehr in `plan_look_window_chunks` hineinflicken |
| #1584 Engine-Hänger | **jetzt, unabhängig**: Diagnose entschwärzt beschaffen; blockiert die Aussagekraft jeder Serie an diesem Tisch und wird von keinem Umbau behoben |
| #1591 `skipForcedDecisions` in PLAY | **jetzt** (Schalter; Owner-Entscheid steht im Issue) |
| #1592 KI-Pause | **jetzt** (Anzeige/Server, keine Struktur) |
| #1593 Melden statt Abfragen | **warten bis D-3**, dann an einer Stelle |
| #1545 Datenstand je Quelle, #1549 Korpus-Audit, #1553 deutsche Namen | **jetzt**: berühren Importer und Datenbericht, kein Schema, keine der drei Nähte |

## 4. Empfehlung und Owner-Entscheidungen

**Empfehlung des Architekten: Option D, Start mit D-0 und D-1 sofort, D-2 vor Owner-Sitzung 1,
D-3 danach. Kein Greenfield, kein breiter Strangler.** Begründung in einem Satz: Der Bestand ist
jung, messbar ordentlich und an drei benennbaren Stellen falsch gebaut; diese drei Stellen neu zu
bauen kostet ein Viertel eines Neubaus, erledigt vier offene Issues gleich mit und lässt den Weg
zur Abnahme (S2 bis S6) offen.

Was die Empfehlung kippen würde: Owner-Sitzung 1 zeigt, dass PLAY oder BUILD als Produkt
grundlegend anders sein müssen (dann betrifft der Neubau die Seite, nicht den Kern); oder D-2
erreicht die Hash-Identität nicht (dann liegt das Problem tiefer als die Orchestrierung).

**Entscheidungen, die nur der Owner treffen kann:**

1. **Neubau oder nicht.** A / B / C / D. Empfehlung D.
2. **Konsolidierungsfenster.** D-1 und D-2 fassen Kollisionsdateien an. (a) zwei Lanes bauen die
   Nähte, die übrigen liefern weiter (empfohlen); (b) drei bis fünf Tage Feature-Stopp für alle;
   (c) kein Fenster, nur „bei Berührung“ (dann wird es Option A).
3. **Schema 22 mit Eindeutigkeit.** Ein Schema-Schritt, der Dubletten bereinigt und verbietet,
   braucht eine Migration des Stores am Owner-PC mit Sicherung davor. (a) ja, zusammen mit
   Owner-Sitzung 1; (b) später; (c) nein, additiv bleiben und Dubletten nur beim Import abfangen.
4. **Abhängigkeiten.** Bleibt es bei „keine neue Abhängigkeit“ (dann kein TypeScript, kein
   Bundler, kein ORM; Empfehlung: ja, bleibt), oder soll für das Frontend-Testnetz ein Werkzeug
   zugelassen werden (`pyproject.toml` ist siegelgebunden)?
5. **Reihenfolge gegenüber Owner-Sitzung 1.** (a) D-1 und D-2 vorher, weil der Owner sonst die
   5-Sekunden-Wartezeit und die langsame gepaarte Serie misst (empfohlen); (b) Sitzung 1 sofort
   auf heutigem Stand, Umbau danach nach AK-8.

## 5. UNKNOWN: was ich nicht bewerten konnte

- **Laufzeitverhalten**: keine Suite, kein Engine-Lauf, kein Server gestartet (Auftrag). Alle
  Zeiten außer dem Store-Öffnen (0,97 ms, leerer Store) stammen aus Issues.
- **Testabdeckung in Prozent** und **Flakiness-Rate** (keine CI-Historie ausgewertet).
- **Store am Owner-PC**: Schema-Stand, Größe, Inhalt, Dauer einer Migration unter Windows.
- **Windows-Verhalten** insgesamt.
- **Java-Bridge**: nur Größe, Struktur, Synchronisationsstellen; keine Code-Prüfung. Ursache von
  #1584. Diff des Forks gegen Upstream.
- **Pilot-Qualität** (`full_game_pilot/*`, CC bis 148): nicht fachlich bewertet, MATERIAL.
- **Autorschaft je Modell** (75 % der Zeilen nicht zuordenbar).
- **Token-Kosten absolut** und die echte Zahl paralleler Lanes (3 bis 5 ist geschätzt).
- **Ob die stillen Ersatzwerte** (`_as_int`, `or 0`, `rounds`-Vorgabe 10) eine sichtbare Zahl
  verfälschen.
- **Ob geteilte Cache-Werte heute irgendwo verändert werden.**
- **Totcode-Inventar** über die zwei genannten Module hinaus.
- **Frontend im Browser** (Bedienung, Barrierefreiheit, Bildschirmgrößen).
- **`gap_plan.md`**: unter `docs/research/studio_abschluss_20261118/` nicht vorhanden (dort:
  README, `design_options.md`, `ist_lage_cpl.md`, `ist_lage_dbs.md`, `play_qol.md`,
  `simulate_methods.md`, `simulate_projects.md`); nicht gelesen.
- **Issues**: #1558, #1561, #1563, #1584–#1586, #1591–#1593, #1545, #1549, #1553 nur im
  Kopftext (je 1.500 Zeichen) gelesen; Claim-Tabelle #1167 nicht gelesen.
- **Historie vor 2026-10-15** (Clone-Tiefe 400) und das Repository `deckbuild-studio`.
- **Warum Parquet/DuckDB** aus dem Entwurf vom 2026-10-05 nicht kam.
