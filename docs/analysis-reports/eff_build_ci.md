# Effizienz-Lane #1558: Builder-Ladegeschwindigkeit und CI-Laufzeit

Stand 2026-11-18, Quelle `origin/main` = `51185f2d8`. Nur Messung, Analyse und Plan: keine
Repo-Änderung, nichts gepusht oder gepostet. Die Vorlage `play_store/studio.sqlite3` ist unverändert
(SHA-256 vorher = nachher `2029752a…27e08`); Store-Kopie und Scratch-Worktree sind gelöscht.

## 0. Kurzfassung

**Builder.** Statische Auslieferung und Prozessstart sind kein Problem (FCP 50–170 ms, erste Antwort
1,7 s nach Prozessstart). Die Wartezeit steckt an vier Stellen:

1. **Aufwärmphase nach Serverstart: 29 CPU-Sekunden.** Währenddessen lädt die Startseite 16,6 s statt 2,1–2,5 s.
   10 s davon kostet eine einzige SQL-Form mit ungünstiger Join-Reihenfolge. Prototyp (2 Zeilen, kein
   Schema): 29,2 → 18,8 CPU-s, alle 37 geprüften Antworten byte-identisch.
2. **Jeder Schreibvorgang wirft alle Caches weg**, auch ein Favoriten-Klick: das nächste `/api/strength` braucht
   5,2–5,6 s statt 0,07–0,09 s, obwohl die Antwort byte-identisch bleibt (Hash gemessen).
3. **`/api/data-report` kalt: 40–42 s** (erster Aufruf der Tierliste nach jedem Schreibvorgang und nach jedem UTC-Tageswechsel).
4. **Ungepufferte Lese-Endpunkte**: `/api/evidence` 0,8–1,1 s, `/api/pool` 0,3 s, `/api/rating-layers` 0,3 s bei jedem Aufruf.

Gzip bringt lokal nichts (Loopback, gemessen), fehlende FK-Indizes sind im Lesepfad nicht der Engpass.

**CI.** Ein Code-PR wartet im Median 260 s auf `quality` (n=15), weil der `packaging`-Job (Median 229 s) fast
immer der längste ist; ohne `packaging` sind es 160 s (n=5), Doku-PRs 125 s (n=8). `infrastructure` braucht 140 s,
`security` 123 s. Queue-Zeit 3 s, Pip-Cache trifft, Rerun-Quote 1,3 %. Hebel: Packaging-Test (ein Test = 68 s von 152 s),
Shard-Gewichte (Slots real 114–199 s statt je 152 s), Secret-Scan (63 s seriell in `security`).
Erreichbar für Code-PRs: etwa 260 → 150 s, ohne einen Test zu streichen. Fast alles davon ist MATERIAL, zwei Punkte Owner-Gate.

---

## A) Messtabelle

Maschine: 4 Kerne, 16 GB, Linux-VM, Python 3.13.18 (CI: 3.12), SQLite 3.53.1, Chromium 1243 headless.
**Last:** Die parallele Engine-Messung (4 JVMs) hielt die Maschine ab etwa 23:08 bei Load 4–10. Absolute
Millisekunden ab dort sind dadurch nach oben verzerrt (Faktor UNKNOWN); Vergleiche, die direkt hintereinander
liefen, bleiben gültig. „Last“ ist der 1-Minuten-Wert aus `uptime`/`os.getloadavg()` zum Messzeitpunkt.
Messskripte: `/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad/costudio/eff/`
(`srv.py`, `bench.py`, `prof.py`, `prof_warm.py`, `prof_dr.py`, `sqltrace.py`, `sqlexp.py`, `sqlexp2.py`,
`after_write.py`, `manifest.py`, `pw.js`, `fetch_ci.py`, `an_ci.py`; Rohdaten als JSON daneben).

### A1 Start und Import

| Messung | Wert | n | Last | Befehl |
|---|---|---|---|---|
| Import `commander_lab.studio.web`, Projekt-`.pyc` fehlen | 1,41 s | 1 | 2,3 | `timeit.py … python3 -c "import commander_lab.studio.web"` |
| Import `…web`, warm | Median 0,88 s (0,84–1,01) | 5 | 2,3 | wie oben |
| Import `…studio.__main__`, warm | Median 0,59 s | 5 | 2,2 | wie oben |
| `fastapi+uvicorn+pydantic` allein / leeres Python | 0,37 s / 0,014 s | 5 | 2,2 | wie oben |
| Importierte Module (`__main__`+`web`+`uvicorn`) | 933, davon 175 `commander_lab` (68 `studio`); Selbstzeit 726 ms: `commander_lab` 313, `fastapi` 100, `openpyxl` 52 (kumulativ 140), `numpy` 48 | 1 | 2,2 | `python3 -X importtime -c "import …"` |
| Prozessstart → erste Antwort `GET /`, DB-Datei aus dem Seitencache verdrängt | 1,88 / 1,66 / 1,63 s | 3 | 2,5 / 1,7 / 1,4 | `srv.py coldstart 3 evict` (`posix_fadvise DONTNEED`) |
| Prozessstart → erste Antwort `GET /`, Dateicache warm | 1,89 / 1,83 / 1,67 s | 3 | 2,0–2,4 | `srv.py coldstart 3 warm` |
| Erstes `/api/status` direkt nach dem Start | 0,83 / 0,46 / 0,39 s (verdrängt), 0,31 / 0,40 / 0,39 s (warm) | 3+3 | wie oben | `srv.py` |
| Aufwärm-Thread (`_warm_caches`) bis CPU-Ruhe | 28,1–29,8 CPU-s; RSS danach 570–579 MB | 9 Starts | 1,4–5,9 | `srv.py` (CPU aus `/proc/<pid>/stat`) |
| Aufwärm-Thread mit Join-Reihenfolge-Prototyp | 18,8 CPU-s | 1 | 2,9 | `proto_check.py` |
| `StudioStore.open()`+`close()` je Anfrage | Median 1,0 ms | 200 | 9,1 | Inline-Skript |
| `store.data_epoch()` ungepuffert | Median 175 ms | 5 | 9,1 | Inline-Skript |

### A2 Endpunkte (lokaler Server, `urllib`, seriell)

„kalt“ = erster Aufruf nach abgeschlossener Aufwärmphase, „warm“ = 5 weitere Aufrufe. Alle 37 Antworten waren über
6 Aufrufe byte-identisch (SHA-256). Last 3,9–6,2. Befehl: `python3 bench.py base`. Commander: Chulane, Deck `chulane` (83 Karteneinträge).

| Endpunkt | Status | Bytes | kalt ms | warm Median ms | warm Max ms | Last |
|---|---|---|---|---|---|---|
| `GET /` | 200 | 4.990 | 4 | 3 | 6 | 3,9 |
| `GET /app.js` | 200 | 207.852 | 3 | 3 | 4 | 3,9 |
| `GET /api/status` | 200 | 7.537 | 115 | 102 | 117 | 3,9 |
| `GET /api/commanders?collection=true` | 200 | 22.242 | 21 | 19 | 21 | 3,9 |
| `GET /api/pool?commander=…` | 200 | 1.445.548 | 263 | 295 | 338 | 3,9 |
| `GET /api/layers?commander=…` | 200 | 10.953 | 4 | 3 | 4 | 3,9 |
| `GET /api/cohorts?commander=…` | 200 | 31.360 | 4 | 3 | 4 | 3,9 |
| `GET /api/allocation` | 200 | 498.644 | 16 | 14 | 19 | 3,9 |
| `GET /api/evidence?view=commander&…` | 200 | 5.530.417 | 841 | 1088 | 1138 | 4,0 |
| `GET /api/data-report` | 200 | 254.170 | **42409** | 32 | 37 | 4,2 |
| `POST /api/strength` | 200 | 11.757.879 | 113 | 74 | 89 | 4,2 |
| `GET /api/strength/snapshot?…` | 404 (kein Snapshot in der Kopie) | 43 | 7 | 3 | 4 | 4,2 |
| `GET /api/rating-layers?…&pod_size=4` | 200 | 1.426.274 | 330 | 317 | 403 | 4,2 |
| `GET /api/universe/options?…` | 200 | 36.870 | 4 | 3 | 3 | 4,2 |
| `GET /api/universe/counted?…` | 200 | 4.354 | 103 | 106 | 123 | 5,1 |
| `GET /api/universe/profiles` | 200 | 2 | 4 | 3 | 3 | 5,1 |
| `GET /api/roles/audit?…` | 200 | 10.818 | 131 | 138 | 141 | 5,1 |
| `GET /api/tournament-conversion?…` | 200 | 93.330 | 110 | 102 | 117 | 5,1 |
| `GET /api/decks/chulane/history` | 200 | 178 | 3 | 3 | 3 | 5,1 |
| `GET /api/revisions/{rev}` | 200 | 31.046 | 58 | 58 | 63 | 5,1 |
| `GET /api/outcomes?deck_id=chulane` | 200 | 682 | 3 | 2 | 2 | 5,1 |
| `GET /api/deck-browser?commander=…` | 200 | 48.936 | 2524 | 341 | 361 | 5,4 |
| `GET /api/similar-decks?…` | 200 | 30.846 | 61 | 63 | 408 | 5,4 |
| `POST /api/check` | 200 | 23.437 | 57 | 60 | 62 | 5,4 |
| `POST /api/deck-doctor` | 200 | 1.695 | 156 | 160 | 165 | 5,4 |
| `POST /api/deck-evidence` | 200 | 78.079 | 244 | 144 | 146 | 5,4 |
| `POST /api/card-duel` | 200 | 949 | 33 | 32 | 33 | 5,4 |
| `POST /api/cut-lab` | 200 | 39.346 | 173 | 148 | 166 | 5,8 |
| `POST /api/deck-facts` | 200 | 10.268 | 204 | 198 | 223 | 5,8 |
| `POST /api/land-advisor` | 200 | 26.552 | 117 | 117 | 125 | 5,8 |
| `POST /api/castability` | 200 | 21.252 | 27 | 26 | 30 | 5,8 |
| `POST /api/packages` | 200 | 50.244 | 412 | 386 | 694 | 6,2 |

Nicht gezeigt (alle ≤ 4 ms, ≤ 34 KB): `/tierliste.js`, `/api/strength/presets`, `/api/decks`, `/api/outcomes/decks`, `/api/games`.

**Auswahl (repräsentatives Dutzend plus Pflichtliste), Begründung.** `web.py` hat 113 Routen-Dekoratoren (112 Funktionen,
`/img/by-name` und `/img-name` teilen eine). Gewählt: (1) was Startseite und Tierliste beim Laden tatsächlich abrufen
(Chromium-Mitschnitt: status, commanders, pool, layers, cohorts, allocation, strength, evidence, data-report, roles/audit,
tournament-conversion, universe/*, decks, revisions, check), (2) die im Auftrag genannten Deck-Werkzeuge (deck-doctor,
deck-evidence, card-duel, cut-lab, deck-facts, land-advisor, strength/snapshot, rating-layers, history, outcomes),
(3) zwei statische Dateien als Untergrenze. Schreibende Routen, Simulation, Partie und Bilder sind nicht gemessen.

| Sonderfall | Wert | n | Last | Befehl |
|---|---|---|---|---|
| Erster Aufruf ohne Aufwärmphase (im Prozess): pool / strength / evidence | 7,55 s / 7,99 s / 8,24 s | je 1 | 6,6–7,5 | `prof.py` |
| Während der Aufwärmphase (Browser, Startseite): layers / pool / strength | 6,1 s / 8,2 s / 16,3 s | 1 | 2,2 | `pw.js` direkt nach `srv.py run` |
| Nach `PUT …/favorite` (Schreibvorgang): strength | 5,58 / 5,57 / 5,17 s (vorher 0,07–0,09 s) | 3 | 4,5–4,7 | `after_write.py`, `manifest.py` |
| Nach Schreibvorgang: land-advisor / layers | 2,54–2,56 s / 0,74–1,23 s (vorher 0,14 s / 0,005 s) | 2–3 | 4,5 | `after_write.py` |
| Nach Schreibvorgang: pool, evidence, rating-layers | unverändert (0,28–0,34 s / 0,83–1,13 s / 0,30–0,31 s) | 2 | 4,5 | `after_write.py` |
| Hash von strength und evidence vor/nach Favoriten-Klick | identisch (pool und layers ändern sich, erwartbar) | 1 | 4,7 | `manifest.py` |
| Manifest A vs. B (Schreiben + Rücknahme, Caches neu aufgebaut) | 37 Endpunkte, 0 Abweichungen | 1 | 4,5 | `manifest.py` |

### A3 Profil der langsamsten Pfade (cProfile, im Prozess; `py-spy` ist nicht installiert)

| Messung | Wert | n | Last | Befehl |
|---|---|---|---|---|
| Aufwärmphase gesamt unter cProfile | 33,6 s; SQLite `execute` 12,2 s (491 Aufrufe) + `fetchall` 4,1 s | 1 | 6,8–9,7 | `prof_warm.py` |
| davon `universe._universe_raw_sets` (SQL) | 8,5 s in 4 Aufrufen | 1 | wie oben | `prof_warm.py` |
| davon `universe.deck_sets` (SQL) / `universe._resolve` (fetchall) | 2,4 s in 2 / 3,6 s in 18 Aufrufen | 1 | wie oben | `prof_warm.py` |
| davon reine Python-Zeit: `_card_options` / `land_advisor._source_deck_groups_uncached` / `_cohort_shapes_uncached` | 2,15 s / 1,72 s / 1,02 s (Selbstzeit) | 1 | wie oben | `prof_warm.py` |
| `/api/data-report` kalt unter cProfile | 53,3 s; `_commanders` 38,9 s = 104 Commander × `signal_coverage` (0,32 s) | 1 | 7,0–8,8 | `prof_dr.py` |
| darin wiederholt, obwohl commander-unabhängig | `builder.role_names` 104× = 6,7 s; `compute_store_signal_rate_alarms` 108× = 4,95 s; `playgroup_rows` 104× = 0,8 s | 1 | wie oben | `prof_dr.py` |
| darin `builder.cohort_sizes` / `corpus_binding` (SQL) | 5,1 s (313 Abfragen) / 1,4 s (312) | 1 | wie oben | `prof_dr.py` |
| `/api/evidence` warm | 0,79 s (im Prozess); `_role_claims` 0,47 s, `_observations` 0,32 s, `pool_cards` 0,36 s, `load_spellbook_combo_cards` 0,18 s (davon `json.loads` 0,09 s je Aufruf) | 3 | 7,5 | `prof.py evidence` |
| `/api/pool` warm | 0,25–0,27 s; `pool_cards` komplett neu: 23 Abfragen 87 ms, `cohort_sizes` 91 ms, `role_names` 54–59 ms | 3 | 7,0–7,5 | `prof.py pool` |
| `/api/status` warm | 0,10 s; `source_layers` ~70 ms (21.358 Zeilen in Python), `bridge_qualification()` 35 ms (2 Unterprozesse je Aufruf) | 3 | 6,7 | `prof.py status` |
| `/api/packages`, `/api/deck-facts` | 0,35 s / 0,21 s; beide `combos._card_catalog_for_slots` 84 ms, deck-facts zusätzlich `cohort_sizes` 90 ms | 3 | 7,5 | `prof.py` |
| `/api/strength` warm | 1,6 ms Rechenzeit, Rest ist Serialisierung von 11,8 MB | 3 | 7,3 | `prof.py strength` |

### A4 SQL (`EXPLAIN QUERY PLAN`, Zeiten = `fetchall`, jeweils 3 Läufe, Minimum)

Store-Kopie: 254 MB, 45 Tabellen, 53 Indizes, `journal_mode=delete`, kein `sqlite_stat1` (nie `ANALYZE`).
Größte Objekte (`dbstat`): `corpus_deck_card` 92,8 MB (913.063 Zeilen), `corpus_card_cover` 49,1 MB, `card_signal` 22,5 MB.

| Abfrage | Plan heute | Zeit heute | Variante | Zeit Variante | Last |
|---|---|---|---|---|---|
| `SELECT c.card_name, c.oracle_id, group_concat(c.deck_id, char(31)) FROM corpus_deck_card c JOIN temp.universe_deck u … GROUP BY c.card_name, c.oracle_id` (10.128 Decks) | `SCAN c USING INDEX corpus_card_cover` + Nachschlagen je Zeile (Index enthält `oracle_id` nicht) + `TEMP B-TREE` | 2.403–2.594 ms | `FROM u CROSS JOIN c` → `SCAN u`, `SEARCH c USING PRIMARY KEY` | 618 ms (Ergebnis kanonisch identisch) | 9,5 |
| dieselbe, 500 Decks | wie oben (liest immer alle 913.063 Indexzeilen) | 1.966 ms | `CROSS JOIN` | 32 ms | 9,2 |
| dieselbe, nach `ANALYZE` | unverändert | 2.404–2.601 ms | – | – | 9,0 |
| dieselbe, mit Index `(card_name, oracle_id, section, quantity, deck_id)` | `SCAN c USING COVERING INDEX`, kein Temp-B-Tree | – | neuer Index (Schema, +86 MB gemessen inkl. `ANALYZE`-Tabellen) | 418–435 ms | 9,0 |
| `SELECT c.deck_id, SUM(c.quantity), MAX(c.quantity > 0) … GROUP BY c.deck_id` (`_resolve`) | `SCAN c` | 282 ms (10.128 Decks) / 165 ms (500) | `CROSS JOIN` | 314 ms / 15 ms | 9,0–9,2 |
| `SELECT c.deck_id, c.card_name …` (`_card_options`) | `SCAN c USING COVERING INDEX corpus_card_cover` | 767 ms / 181 ms | `CROSS JOIN` | 608 ms / 25 ms | 9,2 |
| `SELECT COUNT(*), COUNT(oracle_id), SUM(quantity) FROM corpus_deck_card` (Datenepoche) | `SCAN corpus_deck_card` | 75–108 ms | – | – | 5,9–10 |
| `cohort_sizes`: `corpus_cohort c JOIN corpus_deck d USING (deck_id) … GROUP BY c.cohort` | `SCAN c` (33.953 Zeilen), `SEARCH d` | 28–71 ms | – | – | 5,6–10 |
| `evidence._observations`: `observation o WHERE … EXISTS (commander_binding)` | `SCAN o USING INDEX observation_card` + `TEMP B-TREE FOR ORDER BY` | 325 ms (54.278 Zeilen) | – | – | 5,6 |
| `role_names`: `SELECT oracle_id, role FROM card_role ORDER BY role` | `SCAN card_role` + `TEMP B-TREE` | 19–39 ms (27.546 Zeilen) | – | – | 5,6–10 |

Einordnung der Daten-Inventur-Funde: Die per `SCAN` gelesenen FK-Spalten (`corpus_cohort.deck_id`, `observation.card_id`,
`source_id`) kosten im Lesepfad 28–71 ms je Abfrage und sind über Pufferung billiger zu entschärfen als über Indizes.
Ihre Wirkung auf Importer und Löschpfade (FK-Prüfung beim Eltern-`DELETE`) ist hier **nicht gemessen: UNKNOWN**.

### A5 Frontend (Chromium headless, 1440×900, frischer Kontext je Lauf)

Static: 31 Dateien, 788.955 B roh (229.171 B bei gzip-6). `app.js` 3.141 Zeilen / 207.852 B, `tierliste.js` 2.433 / 183.396 B,
`partie.js` 1.617 / 87.705 B. Startseite lädt 1 CSS + 17 klassische Skripte (blockierend, in Dokumentreihenfolge; `ui.js` im Kopf),
Tierliste 2 CSS + 4 Skripte, Partie 2 CSS + 5 Skripte. Kein `defer`/`async`/Modul.

| Messung | Wert | n | Last | Befehl |
|---|---|---|---|---|
| Startseite warm: FCP / LCP | 100, 80, 120 ms / 1752, 1576, 1124 ms | 3 | 2,0–2,6 | `EFF_RUNS=3 node pw.js` |
| Startseite warm: letzte Antwort (inkl. externer Kartenbilder) | 2513 / 2547 / 2072 ms | 3 | wie oben | wie oben |
| Startseite warm: API-seitig nutzbar (`/api/check` fertig) | ≈ 1,5 s (Lauf 1: 1.503 ms) | 1 abgelesen | wie oben | Wasserfall aus `pw_warm.json` |
| Startseite warm: CLS | 1,326 (alle Läufe; Sprünge 0,29 + 0,82 + 0,18 beim Rendern von Pool und Deck) | 6 | 2,0–3,9 | wie oben |
| Startseite während der Aufwärmphase: FCP / LCP / letzte Antwort | 172 ms / 9.380 ms / 16.626 ms | 1 | 2,2 | `pw.js` direkt nach Start |
| Startseite, zweiter Besuch mit Browser-Cache | letzte Antwort 984 / 1418 ms; 18 Dateien ohne Rückfrage aus dem Cache | 2 | 2,6–3,9 | `EFF_REUSE=1 node pw.js` |
| Startseite Netzwerk | 87 Anfragen: 19 statisch (424 KB), 17–18 API, 46–51 Bilder von `cards.scryfall.io` (3,8–4,3 MB); gleiche Herkunft 13,96 MB, davon `/api/strength` 11,76 MB, `/api/pool` 1,45 MB, `/api/allocation` 0,50 MB | 3 | wie oben | `pwsum.py` |
| Startseite: doppelte Aufrufe | `/api/status` 2× (336 + 892 ms parallel), `/api/layers` 2× | 3 | wie oben | Wasserfall |
| Startseite: `/api/pool` im Parallelbetrieb | 1.090 ms (allein 295 ms) | 1 abgelesen | wie oben | Wasserfall |
| Tierliste warm: FCP = LCP | 52–100 ms | 3 | 2,0–2,6 | `pw.js` |
| Tierliste warm: letzte Antwort | 4.048 / 4.436 ms; erster Besuch 42.090 ms (`/api/data-report` 41.862 ms) | 3 | wie oben | `pw.js` |
| Tierliste: Abrufkette bis `/api/strength` startet | 2,2–2,4 s (evidence 1,26 s → roles/audit 0,53–0,62 s → decks → revision → presets → universe/counted 0,26–0,39 s → strength) | 2 | wie oben | Wasserfall |
| Tierliste: CLS | 0,025 (5 von 6 Läufen), einmal 0,547 | 6 | 2,0–3,9 | `pw.js` |
| Tierliste Netzwerk | 132 Anfragen; gleiche Herkunft 17,7 MB (strength 11,76 MB + evidence 5,53 MB); 106 Bilder 9,7 MB extern; Hauptthread-Blockaden 355–508 ms; 6.270 DOM-Knoten | 3 | wie oben | `pw.js` |
| Partie warm: FCP / LCP / CLS / letzte Antwort | 56–80 ms / 76–108 ms / 0–0,002 / 147–173 ms; 10 Anfragen, 180 KB | 3 | 2,6 | `pw.js` |
| Kopfzeilen statisch | `ETag` und `Last-Modified` ja, `Cache-Control` fehlt, kein `Content-Encoding`; bedingtes `GET` mit `If-None-Match` → 304 | 1 | 2,9 | `manifest.py` |
| Kopfzeilen API | `Cache-Control: no-store`; trotz `Accept-Encoding: gzip` kein `Content-Encoding`; CSP auf jeder Antwort | 1 | 2,9 | `manifest.py` |
| Was gzip kosten würde (Python `gzip`) | strength 11,76 MB → 1,47 MB in 59 ms (Stufe 1) / 0,81 MB in 104 ms (Stufe 6); evidence 5,53 MB → 0,61 MB in 23 ms | 1 | 4,7 | `manifest.py` |
| Aufbau von `/api/strength` | 927 Karten × ≈ 12,6 KB; Feld `components` 7,97 MB (68 %) mit je Karte wiederholten Beschriftungs- und Hinweistexten | 1 | – | Inline-Analyse |

### A6 CI (GitHub REST, kein HTTP 429)

Stichproben: (S40) die letzten 40 Läufe je Workflow `ci.yml` und `production-qualification.yml`, 2026-11-18 18:33–22:49 UTC,
mit Job- und Schrittzeiten; (S300) die letzten 300 Läufe je Workflow, 2026-11-15 18:36 bis 11-18 22:49 UTC; (S7d) Zähler
`total_count` seit 2026-11-11. Last: nicht relevant (Netzabfragen). Befehle: `gh api repos/…/actions/workflows/<wf>/runs?per_page=…`,
`…/actions/runs/{id}/jobs?per_page=100&filter=all`, `…/actions/jobs/{id}/logs`, `gh run download 44411300725 --pattern 'ci-evidence-tests-*'`.

| Messung | Wert | n | Befehl / Quelle |
|---|---|---|---|
| `quality` fertig nach Laufstart: Code-PR mit `packaging` / ohne / Doku-PR / Push auf `main` | Median 260 s (Max 310) / 160 s (166) / 125 s (139) / 240 s (316) | 15 / 5 / 8 / 10 | `an_ci.py`, S40 |
| CI-Lauf gesamt, erfolgreiche PR-Läufe / Pushes | Median 250 s, P90 301 s, Max 385 s / Median 268 s, P90 309 s | 151 / 101 | S300 |
| Production Qualification gesamt, PR / Push | Median 146 s, P90 183 s / Median 190,5 s (mit `exact-main-admission`) | 189 / 100 | S300 |
| Job `packaging` | Median 229 s, P90 276 s, Max 288 s; längster Job in 25 von 38 Läufen | 25 | S40 |
| Job `security` | Median 123 s, P90 158 s; längster Job in 9 von 38 | 38 | S40 |
| Jobs `tests 1/4 … 4/4` | Median 116 / 112 / 116 / 122 s; P90 149 / 129 / 133 / 138 s; Max 232 s (Slot 1) | je 30 | S40 |
| Job `tests 1/1 (docs)` | Median 95,5 s | 8 | S40 |
| Jobs `lint` / `changes` / `quality` (Gate) | Median 52,5 s / 11 s / 10 s | 38 | S40 |
| Job `infrastructure` / `exact-main-admission` | Median 140 s, P90 179 s / 42 s | 24 / 5 | S40 |
| `ci-definition-integrity-shadow` / `repository-tree-integrity` | Median 37 s / 41,5 s | 5 / 6 | S40-Teil |
| `windows-runtime` / `release-artifacts` (`build-release`) / `exact-main-recovery` | Median 76 s / 158 s / 65,5 s | 6 / 6 / 4 | S40-Teil |
| „Studio Human Seat Real Engine“ | ein Lauf, 174 s gesamt, nur auf einem PR-Zweig (Workflow nicht auf `main`) | 1 | Laufliste; Jobdaten nicht geholt: UNKNOWN |
| Queue-Zeit (Job erstellt → gestartet) | Median 2–3 s, Max 4 s | alle Jobs | S40 |
| Schritt „Packaging tests“ | Median 173 s (Max 228); in Lauf 44411300725: 33 Tests in 151,9 s, davon `test_every_forged_binding_is_rejected_independently` 68,1 s | 25 / 1 | S40, Job-Log |
| Schritt „Test suite“ (Slots) | Median 80,5 s, Max 184 s | 120 | S40 |
| Schritt „Broad secret scan (pinned gitleaks)“ | Median 63 s, Max 92 s (21.423 Dateien) | 38 | S40 |
| Schritt „Validate WS-17 qualification infrastructure“ | Median 105 s, Max 144 s | 24 | S40 |
| Installationsschritte (pip, hash-gesperrt) | Median 16–19 s je Job, in 7 Jobs je CI-Lauf | 38 | S40 |
| Checkout | Median 7 s (flach) / 10 s (`fetch-depth: 0`); Windows 22,5 s | 38 | S40 |
| Pip-Cache | Treffer in allen 6 Jobs mit `setup-python` (61 MB, Wiederherstellung ≈ 1–2 s) | 1 Lauf | Job-Logs 44411300725 |
| Maven-/XMage-Cache | nicht analysiert (pfadgefilterte Workflows nicht in der Stichprobe); indirekt: „Build or restore pinned XMage engine“ 3 s Median | 6 | S40-Teil; sonst UNKNOWN |
| Shard-Balance, gemessene Sekunden je Slot (JUnit, Lauf 44411300725) | 136,9 / 167,4 / 199,0 / 113,9 s; Gewichtstabelle plant je 151,8–151,9 s | 1 Lauf | `tests/pytest_shards.py` + JUnit |
| Schritt „Test suite“ je Slot in diesem Lauf / längster Innen-Shard | 61,5 / 80 / 93 / 51,4 s / 45,1 / 55,2 / 62,8 / 38,4 s → Überhang 16,5 / 25 / 30 / 13 s | 1 Lauf | Job-Logs |
| Schwerster Test je Slot (gemessen; Tabelle) | 1: `test_deck_variant_prefilter.py` 44,7 s (52,5) · 2: `test_ci_definition_integrity.py` 31,0 s (20,5) · 3: `test_pilot_real_request_corpus.py` 44,9 s (26,3), `test_studio_builder.py` 39,8 s (21,2) · 4: `test_mana_analysis.py` 15,3 s (21,3) | 1 Lauf | JUnit |
| Gewichtstabelle | 363 Einträge, 202 am Boden 0,1 s; 12 von 375 Testdateien ohne Gewicht (3,2 %; Deckel 5 %, heute 18 Dateien, `UNWEIGHTED_SHARE` in `tests/unit/test_pytest_shards.py`); letzte Auffrischung 2026-11-17 | – | Worktree `51185f2d8` |
| Qualifikations-Gewichte | 93 Dateien, Summe 313,8 s; `test_pb03_trigger_completeness.py` 87,5 s, `test_pre_freeze_contract_successor.py` 78,4 s | – | `tests/pytest_shard_weights_qualification.json` |
| Ergebnisse CI | 256 Erfolg, 31 Fehlschlag (10,3 %), 13 abgebrochen (4,3 %) | 300 | S300 |
| Fehlschläge nach Job | `tests` 24, `lint` 6 (Mypy 4 Schritte, Ruff 2, Format 2), `security` 1 (Abhängigkeits-Audit) | 31 | Jobdaten |
| Rerun-Quote | 4 von 300 Läufen mit zweitem Versuch (1,3 %), alle danach grün | 300 | S300 |
| Abbrüche über 7 Tage | CI 102 von 779 (13,1 %), Production Qualification 76 von 779 (9,8 %) | 779 | S7d |
| Abgebrochene CI-Läufe: Laufzeit bis zum Abbruch | Median 118 s, Summe 31 min | 13 | S300 |
| Pushes je PR-Zweig | Median 2 Läufe, Max 6 (198 Läufe auf 106 Zweigen) | 106 | S300 |
| Production Qualification Fehlschläge | 2 von 300, beide Push auf `main`; der geprüfte (44374592820) scheiterte in „Install validation runtime“ | 300 / 1 | S300, Jobdaten |
| Lokal: `ruff check .` / `ruff format --check .` | 1,2 s / 1,0 s | 1 | `time ruff …` (Last 10,3) |
| Lokal: Kopie des Checkouts wie ein Shard (21.424 Dateien, 531 MB, ohne `.git`) | 1,3 s, Löschen 1,3 s | 1 | `shutil.copytree` (Last 9,3) |
| Sichtbarkeit des Repos | öffentlich: Standard-Runner-Minuten kosten nichts, Kosten = Wartezeit | – | `gh api repos/…` |

---

## B) Maßnahmen

Reihenfolge nach Gewinn gegen Risiko. „Gewinn“ nennt, ob gemessen oder geschätzt. Keine Maßnahme streicht Daten oder Funktionen.

### B1 Top 8 BUILD

| # | Maßnahme | Erwarteter Gewinn | Risiko, Berührung | MATERIAL | Aufwand |
|---|---|---|---|---|---|
| 1 | **Join-Reihenfolge** in `universe._universe_raw_sets` und `universe.deck_sets` festlegen (`FROM <temp> u CROSS JOIN corpus_deck_card c`); `_card_options` und `_resolve` gleich prüfen | gemessen: Aufwärmphase 29,2 → 18,8 CPU-s; Abfrage 2,4 s → 0,62 s (10.128 Decks), 1,97 s → 0,03 s (500 Decks) | niedrig. Kein Schema, kein Importer, keine Qualifikation. `group_concat`-Reihenfolge ist egal, der Code bildet Mengen. `_resolve` bei vollem Universum 282 → 314 ms: dort nur umstellen, wenn gemessen besser | nein | S |
| 2 | **Caches überleben Nutzerzustands-Schreibvorgänge** (Favorit, Markierung, Label, Entwurf, Primer): Einträge, die nur von Importdaten abhängen, nach einem bekannten Schreibvorgang auf den neuen Dateistempel fortschreiben, nur wenn der Änderungszähler genau um die eigenen Commits gestiegen ist; sonst wie heute verwerfen | gemessen als Ist-Kosten: 5,2–5,6 s (strength), 2,5 s (land-advisor), 0,7–1,2 s (layers) nach jedem Klick; Ziel ≈ Warmwerte | mittel: ein falsch als „unabhängig“ eingestufter Eintrag liefert veraltete Zahlen. Kein Schema. Unabhängiges Review empfohlen (Zahlen der Evidenzanzeige) | empfohlen ja (Review), formal nein | M |
| 3 | **`/api/data-report`**: commander-unabhängige Teile (`role_names`, `playgroup_rows`, Signal-Alarme) je Durchlauf einmal rechnen; Bericht nach Datenepoche statt nach Dateistempel merken; in der Aufwärmphase hinten anstellen | Schätzung aus Profil: 40–42 s → 25–28 s kalt (12–13 s wiederholte Arbeit entfällt); Neuberechnung nur noch bei Datenänderung | niedrig bis mittel: Bericht enthält Deck-Zähler (Nutzerzustand), dieser Teil bleibt je Aufruf frisch | nein | M |
| 4 | **Antwort-Pufferung für teure Lese-Routen** über das vorhandene `cache.cached` (Schlüssel = Dateistempel + Parameter): `evidence`, `pool`, `rating-layers`, `roles/audit`, `tournament-conversion`, `universe/counted`, `deck-browser`, der Store-Teil von `status`; dazu `load_spellbook_combo_cards` und `_card_catalog_for_slots` einmal laden | Schätzung: evidence 0,8–1,1 s → < 0,1 s, pool/rating-layers 0,3 s → < 0,05 s; Startseite API-nutzbar 1,5 → ≈ 1,0 s, Tierliste 4,0–4,4 → ≈ 2,5–3 s | niedrig: identisch per Konstruktion, solange niemand das gemerkte Objekt verändert (Test nötig); Speicher (evidence ≈ 5,5 MB je Eintrag, Grenze 48 Einträge) | nein | S–M |
| 5 | **Abrufhygiene im Frontend**: `/api/status` und `/api/layers` je Seite einmal (geteilte Anfrage in `ui.js`); Tierliste: unabhängige Abrufe parallel statt als Kette | Schätzung: Tierliste −0,5 bis −1,0 s; Startseite −0,1 bis −0,5 s (weniger Gedränge neben `pool`) | niedrig: nur JS, CSP unberührt; Reihenfolge der Zustandsübernahme muss gleich bleiben | nein | M |
| 6 | **Schlanke Stärke-Antwort für die Builder-Liste** als zusätzlicher, ausdrücklich angeforderter Umfang (Standardantwort unverändert); Details je Karte beim Öffnen | gemessen als Ist: 11,76 MB je Seitenaufruf = 84 % der Bytes; Schätzung −0,2 bis −0,3 s (Serialisieren 70 ms + Parsen ≈ 150 ms) und weniger Speicher | mittel: neue API-Form, Frontend-Pfad für Details; kein Datenverlust, weil die volle Antwort bleibt | nein | M |
| 7 | **Cache-Regel für statische Dateien** ausdrücklich setzen: `Cache-Control: no-cache` (immer Rückfrage per ETag, 304 in ≈ 3 ms). Kein gzip | Qualität statt Tempo: heute entscheidet die Browser-Heuristik, nach einem Update kann altes JS ohne Rückfrage laufen (18 Dateien so beobachtet) | niedrig: Middleware neben den Sicherheitskopfzeilen, CSP unverändert | nein | S |
| 8 | **Layout-Sprünge der Startseite** (CLS 1,33): Platz für Pool- und Deckbereich in `app.css` reservieren | CLS-Ziel < 0,1 (Schätzung); keine Zeitersparnis | niedrig, sichtbar: Darstellung ändert sich leicht. Keine Inline-Styles (CSP `style-src 'self'`) | nein | S–M |

Bewusst **nicht** empfohlen: gzip (lokal reiner CPU-Aufwand); neuer Index mit `oracle_id` (0,42 s statt 0,62 s der Maßnahme 1, dafür
Schema 22 und +86 MB); `ANALYZE` (kein Effekt gemessen); verzögerte Importe von `openpyxl`/`numpy` (≈ 0,15–0,2 s von 1,7 s Start,
nur einmal je Serverstart); FK-Indizes für den Lesepfad.

**Äquivalenznachweis (für jede BUILD-Maßnahme gleich):**
1. Vorher auf der Basis: Server mit einer Store-Kopie starten, Aufwärmphase abwarten, `manifest.py` schreibt je Endpunkt Status, Länge und SHA-256 (37 Anfragen; Vorlage `eff/manifest_A.json`).
2. Nachher auf dem Kandidaten mit einer frischen Kopie derselben Vorlage: Manifest erneut, Vergleich muss 0 Abweichungen zeigen. Für Maßnahme 1 so durchgeführt: 37 von 37 identisch.
3. Für Cache-Maßnahmen (2, 3, 4) zusätzlich die Schreibmatrix: Favorit, Markierung, Label, Entwurf, Revision, Primer, Universumsprofil je einmal schreiben; danach muss jedes Manifest dem eines frisch gestarteten Servers auf derselben Datei gleichen. Zusätzlich ein Import in die Kopie: danach darf kein alter Eintrag ausgeliefert werden.
4. Für Frontend-Maßnahmen (5, 6, 8): Playwright-Lauf vorher/nachher, Vergleich des gerenderten Tabelleninhalts (Text der Pool- und Tierzeilen als Hash), keine Konsolenfehler, CSP-Kopfzeile unverändert.
5. Zeiten als Median aus ≥ 5 Läufen auf ruhiger Maschine, mit Last notiert.

Die Antworten sind dafür geeignet: über 6 Wiederholungen und über einen Schreibvorgang mit Rücknahme hinweg byte-identisch.

### B2 Top 8 CI

Harte Bedingung eingehalten: `quality`, `security`, `infrastructure` behalten Namen, Bedeutung und Strenge; kein Test wird geschwächt,
übersprungen oder abgewählt. „Gate“: **OWNER** = Owner-Entscheid nach `AGENTS.md` §8/§10 (Definition eines Pflicht-Checks,
`production-qualification.yml`, `WS17_SHA256SUMS`); **MATERIAL** = unabhängiges Review auf dem exakten Head, Workflow- oder Gate-nahe Datei;
**keins** = normale Änderung.

| # | Maßnahme | Erwarteter Gewinn | Risiko | Aufwand | Gate |
|---|---|---|---|---|---|
| 1 | **Shard-Gewichte auffrischen** (`python -m tests.pytest_shards weights --from-artifacts`) und als Routine nach größeren Test-PRs | Schätzung aus JUnit: langsamster Slot 199 → ≈ 154 s Testsumme, Schritt 93 → ≈ 75 s, also −15 bis −20 s auf dem Testpfad. Zusätzlich: 12 von 375 Dateien ohne Gewicht, bei etwa 20 wird `quality` rot (rund 8 neue Testdateien; zuletzt 12 in anderthalb Tagen) | keins (nur Verteilung; jede Datei läuft weiter genau einmal) | S | keins (Gewichtstabelle ist PASS-Klasse der Shadow-Prüfung) |
| 2 | **`test_every_forged_binding_is_rejected_independently`**: die 30 unabhängigen Prüfaufrufe (26 Fälschungen, 4 fehlende Schlüssel) nebenläufig starten, gleiche Kontrollen, gleiche Zusicherungen | Schätzung: 68 → ≈ 20–25 s, `packaging` 229 → ≈ 185 s; `quality` für Code-PRs −40 bis −45 s | niedrig: heute schreiben alle Aufrufe in dieselbe Nachweisdatei, sie brauchen dann je eine eigene | S | MATERIAL (Test des Pflicht-Checks; Shadow meldet „review-required“) |
| 3 | **`packaging`-Tests auf zwei Runner teilen** (feste Aufteilung der 33 Tests, Besitz-Nachweis in `test_required_test_ownership.py`: Vereinigung vollständig, Schnitt leer) | Schätzung: `packaging` ≈ 110 s; mit 1+2 `quality` für Code-PRs 260 → ≈ 150–160 s | mittel: Job-Graph unter `quality` ändert sich; `scripts/verify_required_check_definitions.py` muss das Muster weiter per Parsen anerkennen | M | **OWNER** + MATERIAL (`ci.yml`, Definition von `quality`) |
| 4 | **Secret-Scan in `security` nebenläufig**: `run_broad_secret_scan.py` zu Jobbeginn im Hintergrund starten, vor Jobende einsammeln, gleicher Scanner, gleiche Rot-Kontrollen, Fehler bleibt Fehler | Schätzung: `security` 123 → ≈ 75–80 s | mittel: Abbruch- und Fehlerpfade müssen geschlossen bleiben (kein verlorener Exit-Code) | S–M | **OWNER** + MATERIAL (Pflicht-Check `security`, Sicherheitskonfiguration) |
| 5 | **Schlanker Checkout für `changes` und das Gate `quality`** (beide brauchen je ein Skript; Checkout 7 s von 10–11 s) | Schätzung: −8 bis −10 s auf jedem `quality`-Pfad | niedrig: `changes` braucht weiter den Basis-Commit für das Diff | S | **OWNER** + MATERIAL (Gate-Job in `ci.yml`) |
| 6 | **Überhang der Shard-Ausführung messen** (nur Bericht: Sekunden für Kopie, Start, Lauf, Aufräumen je Shard in `tests/pytest_shards.py`) und danach über billigere Isolation entscheiden | 13–30 s je Slot sind heute unerklärt (UNKNOWN-Aufteilung); mögliches Ziel −10 bis −15 s je Slot und für `infrastructure` | niedrig (reine Ausgabe) | S | MATERIAL (Shard-Läufer der Pflicht-Checks) |
| 7 | **Lokale Vorab-Prüfung `scripts/check_fast.sh`** (offene Empfehlung 7 des CI-Plans): Ruff, Format, Mypy, Compile, Tests des geänderten Bereichs; in den Agenten-Richtliniendateien als Schritt vor dem Push | 6 von 31 roten CI-Läufen waren reine Lint-/Typfehler (19 %); jeder vermiedene rote Lauf spart einen Zyklus von ≈ 4–5 min. Lokal gemessen: Ruff 1,2 s, Format 1,0 s. Anteil vermeidbarer Testfehler UNKNOWN | keins | S | keins für das Skript; MATERIAL für den Satz in den Richtliniendateien |
| 8 | **`infrastructure` unter 100 s**: die zwei Dateien mit 87,5 s und 78,4 s testweise auf Innen-Shards verteilen (kein Test geändert) | Schätzung: Schritt 105 → ≈ 70 s, Job 140 → ≈ 105 s. Wird nach 1–4 der längste Pflicht-Check (heute schon für Doku-PRs: 146 s gegen 125 s) | mittel: Aufteilung unterhalb der Dateiebene ist neue Läufer-Logik | M | **OWNER** (`production-qualification.yml`, Digest-Zeile in `WS17_SHA256SUMS` nur innerhalb dieser Änderung) |

Schon gut und unverändert zu lassen: `concurrency` mit Abbruch veralteter PR-Läufe (alle Workflows), Doku-Schnellpfad (`NON_DOCS_ROOTS`
in `scripts/ci_change_scope.py`: 125 s statt 260 s), Pfadfilter der schweren Lanes, Pip-Cache, Queue. Abbrüche (13 % über 7 Tage)
sind die Folge mehrerer Pushes je PR (Median 2, Max 6), nicht einer fehlenden Regel: Abhilfe ist Maßnahme 7.

Bewusst **nicht** vorgeschlagen: Doku-Schnellpfad für `infrastructure` (würde ändern, was der Check auf Doku-PRs beweist);
`pytest-xdist` (neue Abhängigkeit in `requirements/lock.txt`, siegelgebunden); automatische Reruns (im CI-Plan ausgeschlossen);
`packaging` seltener starten (läuft heute bei jeder `src/`-Änderung, strenger als `docs/CI_WHICH_CHECK_RUNS_WHEN.md` es beschreibt).

Nebenfund Doku-Drift: `docs/CI_WHICH_CHECK_RUNS_WHEN.md` nennt für `quality` „about 2.5 min“ und für `packaging` nur ausgewählte
`src/`-Änderungen; `scripts/ci_change_scope.py` startet `packaging` bei jeder Änderung unter `src/`, und der gemessene Median ist 260 s.

---

## C) Issue-Entwürfe

`/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad/costudio/eff_build_ci_issues.json`
(15 Entwürfe: 8 BUILD, 7 CI, davon 3 mit Owner-Gate, 6 MATERIAL, 10 agentenreif; Felder `title`, `body_markdown`, `labels_proposed`, `priority`, `owner_gate`, `material`, `agent_ready`).
Nichts davon ist angelegt.

---

## D) Unsicherheiten

- **Fremdlast.** Load 2–10 während fast aller lokalen Messungen. Absolute Zeiten ab 23:08 sind zu hoch, Faktor UNKNOWN. Die Rangfolge der Engpässe und die Vorher/Nachher-Paare (SQL-Varianten, Prototyp, Schreibvorgang) sind davon unberührt, weil sie direkt nacheinander liefen.
- **Zielmaschine.** Gemessen auf Linux-VM mit Python 3.13; Owner-Rechner (Windows, anderes Dateisystem, Virenscanner) UNKNOWN. „Kalt“ heißt hier: DB-Datei aus dem Seitencache verdrängt, Codedateien blieben gepuffert. Ein echter Kaltstart nach Neustart ist nicht gemessen.
- **Zustand der Store-Kopie.** 2 Decks, 0 Universumsprofile, 0 Tier-Snapshots, 0 Simulationen, 0 Partien. `strength/snapshot` (404), `outcomes`, `games`, `history`, `universe/spread` sind damit praktisch ungemessen; mit echten Daten UNKNOWN.
- **Stichprobengröße.** n = 1–5 je Messung; Profil-Läufe n = 1.
- **Externe Bilder.** Kartenbilder kamen von `cards.scryfall.io`; „letzte Antwort“ der Seiten enthält deren Netzlaufzeit. Die API-seitige Nutzbarkeit ist aus dem Wasserfall abgelesen, nicht als eigene Marke gemessen.
- **CLS.** Reproduzierbar 1,33 auf der Startseite (6 Läufe), aber headless bei 1440×900; wie störend das wirkt, ist nicht bewertet.
- **Schätzungen.** Gewinne der BUILD-Maßnahmen 3–6 und 8 sowie der CI-Maßnahmen 1–6 und 8 sind aus Profilen und Stufenzeiten abgeleitet, nicht gemessen. Gemessen sind nur BUILD 1 (Prototyp) und die Ist-Kosten.
- **Abhängigkeiten der Caches (BUILD 2).** Dass `strength` und `evidence` nach einem Favoriten-Klick byte-identisch sind, ist für genau diesen Schreibvorgang gezeigt. Für Markierung „ausgeschlossen“, Labels, Entwürfe, Revisionen UNKNOWN; der Kommentar in `builder._corpus_hits` warnt, dass Importer Kartennamen ändern können, ohne die Datenepoche zu bewegen.
- **CI-Stichprobe.** Job- und Schrittzeiten stammen aus 4,3 Stunden eines Tages (38 erfolgreiche CI-Läufe, 24 PQ-Läufe); Shard-Balance, schwerste Tests und Cache-Treffer aus einem einzigen `main`-Lauf. JUnit-Zeiten sind unter vier parallelen Prozessen gemessen.
- **Nicht analysiert.** Maven-/XMage-Caches, PB-03, H4, Conformance, 4P-Smoke (pfadgefiltert, nicht in der Stichprobe); Jobdaten des Human-Seat-Workflows; Ursache der 24 Test-Fehlschläge; zweiter PQ-Fehlschlag; Aufteilung des Shard-Überhangs.
- **Gate-Einstufung.** Ob Änderungen an `tests/pytest_shards.py` und am Packaging-Test als „Gate-Definition“ (Owner) oder als MATERIAL mit Review gelten, entscheidet der Lead; hier vorsichtig eingestuft.
- **Importer und Löschpfade.** Wirkung der fehlenden FK-Indizes dort nicht gemessen: UNKNOWN.
