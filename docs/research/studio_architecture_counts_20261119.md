# Studio-Zählwerte und Messnetz D-0 (Stand 2026-11-19)

Refs #1612 (Architektur-Option D, Paket D-0). Grundlage ist die Brownfield-Bewertung, auf die
#1612 verweist (Abschnitt 1 „Ist-Bewertung“). Diese Datei hält die dort genannten Zählwerte so
fest, dass sie sich wiederholen lassen: jede Zahl nennt die Definition im Messskript, den Befehl
und den Stand. Wo eine Zahl von der Bewertung abweicht, steht beides mit Grund daneben.

**Stand:** `main` @ `14a802bcd393921622d5f431f629c2e7cd8e4570`. `src/` ist dort identisch mit dem
Stand der Bewertung (`git diff --stat 60be9fa8 14a802bc -- src/` ist leer).

**Befehl** (alle Werte unten, nur Lesen, keine Abhängigkeit außer der Standardbibliothek):

```
python scripts/studio_architecture_counts.py --out <datei außerhalb des Repos>.json
```

Die Definitionen stehen im Docstring der jeweiligen Funktion in
`scripts/studio_architecture_counts.py`. „besser“ heißt: Zahl in der Spalte „Richtung“ bewegt sich
in die angegebene Richtung, bei gleichem Antwort-Manifest (unten).

## 1. Zählwerte

| Wert | Stand | Richtung | Funktion / Definition | Bewertung (Abschnitt 1) |
|---|---|---|---|---|
| `src/commander_lab` Python | 218 Dateien, 113.695 Zeilen | – | `line_count` (= `wc -l`) | gleich |
| `studio/` Python | 74 Dateien, 47.916 Zeilen | – | `line_count` | gleich (das alte Analyse-Skript zählte `count("\n")+1` = 47.990) |
| `studio/static` JS | 24 Dateien, 11.638 Zeilen | – | `line_count` | gleich |
| `engine/` Python | 48 Dateien, 21.656 Zeilen | – | `line_count` | gleich |
| `qualification/` Python (src) | 27 Dateien, 28.425 Zeilen | – | `line_count` | gleich |
| `tests/unit` Python | 354 Dateien, 104.581 Zeilen | – | `line_count` | gleich |
| `tests/unit/test_studio*.py` | 99 Dateien, 42.788 Zeilen | – | `line_count` | gleich |
| `Any` in `studio/` | 0 | bleibt 0 | `any_uses` (wie `test_any_usage_ratchet.py`) | gleich |
| Funktionen mit Rückgabetyp | 1.316 von 1.317 | ↑ | `function_return_annotations` | gleich |
| `type: ignore` in `studio/` | 57 (davon `play.py` 18, `combos.py` 9, `deck_evidence.py` 9) | ↓ | `type_ignores` (Kommentar-Token) | gleich |
| SQL-Aufrufe in `studio/` | 488 in 47 von 74 Modulen | ↓ außerhalb einer Datenschicht | `sql_calls` (`execute`/`executemany`/`executescript`) | gleich |
| SQL-Aufrufe Spitzen | `builder` 75, `importers` 51, `store` 51, `universe` 31, `catalog` 30 | ↓ | `sql_calls` je Modul | gleich |
| `response_model` in `web.py` | 0 | ↑ | `keyword_uses` | gleich |
| Private Zugriffe `studio/` → `engine` | 11 Stellen (`play.py` 9, `engine_check.py` 1, `play_batch.py` 1) | ↓ (D-3: 0) | `private_engine_accesses` | Bewertung: 5 Beispielstellen in `play.py`; s. Anm. 1 |
| Private Überschreibungen `studio/` → `engine` | 2 (`play.py` `_validated_policy`, `_drive`) | ↓ | `private_engine_overrides` (auch über Studio-Unterklassen, transitiv) | gleich (`play.py:128-161`) |
| Importgraph `studio/` | 74 Module, 312 Kanten, davon 42 nur über Importe in Funktionsrümpfen | – | `studio_import_graph` | gleich |
| Importzyklen | 1 Zyklus, 12 Module | ↓ (Ratsche, Abschnitt 2) | `cyclic_components` | gleich |
| Importe aus `commander_lab.qualification` | 6 Anweisungen in 5 Modulen | ↓ (Ratsche) | `qualification_imports` | gleich |
| Duplikation `studio/` Python | 2,0 % (dateiübergreifend 0,3 %) | ↓ | `duplication`, Fenster 6 | gleich |
| Duplikation JS | 0,8 % (0,5 %) | ↓ | `duplication` | gleich |
| Duplikation `engine/` | 1,6 % (0,7 %) | ↓ | `duplication` | gleich |
| Duplikation Studio-Tests | 4,6 % (1,8 %) | – | `duplication` | gleich |
| Testfunktionen, die JS mit `node` ausführen | 41 (23 in `test_studio*.py`, 18 in `test_human_seat_play_1169.py`) | ↑ | `js_executing_tests` | Bewertung: 8; s. Anm. 2 |

Anm. 1: Die Bewertung nennt fünf Stellen als Beispiele (`play.py:701/715/722/811/871`). Das Skript
zählt nach fester Regel: Import eines privaten Engine-Namens, Attributzugriff `obj._name` oder
`getattr(obj, "_name")` auf einen Namen, den `engine/` definiert und `studio/` nicht. Dazu kommen
`engine_check.py:68`, `play_batch.py:21`, der Import `_RawFullGameClient` und drei
`getattr(client, "_transport_failure")`/zwei `getattr(…, "_process")`. `play.py:701`
(`runner._validated_policy`) ruft die Studio-eigene Überschreibung auf und steht deshalb in der
Zeile „Überschreibungen“.

Anm. 2: Die Methode hinter der Zahl 8 ist in der Bewertung nicht festgehalten und mit den
Messskripten nicht nachzubilden. Hier zählt eine Testfunktion, wenn sie selbst
`shutil.which("node")` aufruft oder (transitiv) eine Hilfsfunktion derselben Datei, die das tut.

**Nachtrag `main` @ `0792a59b`** (nach Einmergen in den D-0-Branch): Zyklus 13 Module (neu
`gc_band`, über #1622: `universe` importiert `gc_band` auf Modulebene, `gc_band` importiert
`universe` in einem Funktionsrumpf); private Überschreibungen 3 (neu `play_batch.py:94 _drive` aus
#1629, Unterklasse von `play._RecordingRunner`); übrige Werte der Tabelle unverändert geprüft:
`qualification`-Importe 6, private Zugriffe 11.

## 2. Architekturtest (Ratsche)

`tests/architecture/test_layer_boundaries.py` prüft mit denselben Funktionen gegen
`tests/fixtures/studio_architecture_baseline.json`:

- Zyklen im Importgraph von `studio/` (alle Importe, auch in Funktionsrümpfen und unter
  `TYPE_CHECKING`): höchstens 1 Zyklus, höchstens 12 Module, und kein Modul außerhalb der heutigen
  12 (`builder`, `corpus_signals`, `decks`, `research_import`, `roles`, `sources`,
  `strength_view`, `tier_snapshot`, `tiers`, `universe`, `universe_choice`, `universe_view`). Ein
  zweiter, getrennter Zyklus ist damit ebenso rot wie ein größerer.
- Importe aus `commander_lab.qualification` (exaktes Präfix; `commander_lab.bridge_qualification`
  ist ein anderes Modul): nur aus einem Modul in `qualification_facades` (heute keins) oder bis zur
  festgeschriebenen Zahl je Modul (heute `doctor` 1, `launch` 2, `paired_comparison` 1, `play` 1,
  `simulations` 1, alle `current_boundary.bridge_launcher.canonical_xmage_engine_pin`).
- Sinkt ein Wert, wird der Test ebenfalls rot und nennt den neuen Wert für die Fixture (Gewinn
  festschreiben, wie `test_any_usage_ratchet.py`).
- Keine stille Erhöhung: Jede Änderung eines Ratschenwerts ist ein neuer Eintrag in `history` der
  Fixture (Datum, `#Issue`, Begründung); die obersten Werte müssen dem letzten Eintrag gleichen,
  sonst ist der Test rot. Heute zwei Einträge: Erstaufnahme (12 Module, #1612) und `gc_band`
  (13 Module, #1622, vor der Ratsche gemergt, festgehalten, nicht neu erlaubt).
- Erkannt werden auch `from commander_lab import qualification`, `from .. import qualification`
  und `importlib.import_module("commander_lab.qualification…")`/`__import__` mit konstantem Text.
  Statische Grenze: ein zur Laufzeit gebauter Modulname (Variable, f-String) bleibt unsichtbar.
- Mutationsprüfung im Test selbst: synthetischer Graph, und eine Kopie von `studio/` mit einem
  zusätzlichen Funktions-Import `store` → `builder` bzw. `web` → `..qualification` muss rot werden.
  Von Hand auf dem echten Baum geprüft (danach zurückgesetzt): ein Funktions-Import
  `strength` → `builder` macht den Zyklus 15 Module groß (neu: `layers`, `layers_view`,
  `strength`), ein zweiter `bridge_launcher`-Import in `doctor.py` meldet „2, recorded 1“.

## 3. Antwort-Manifest (Äquivalenznachweis)

`scripts/studio_response_manifest.py` (nur Standardbibliothek, Windows-tauglich):

```
python scripts/studio_response_manifest.py run --store <Vorlage> --out <außerhalb>/A.json [--src <checkout>/src]
python scripts/studio_response_manifest.py run --store <Vorlage> --out <außerhalb>/B.json --src <kandidat>/src
python scripts/studio_response_manifest.py compare A.json B.json     # Exit 0 gleich, 1 verschieden
python scripts/studio_response_manifest.py writes --store <Vorlage> --out <außerhalb>/W.json
```

- Die Vorlage wird nur gelesen: alle Dateien werden vor und nach dem Lauf gehasht (Abbruch mit
  Exit 3 bei Änderung), der Server läuft gegen eine frische Kopie in einem Arbeitsordner, die danach
  gelöscht wird. Vor der ersten Anfrage prüft das Werkzeug, dass der Server den Ordner dieser Kopie
  meldet (sonst Exit 3); der Port ist frei gewählt, der Prozess wird nur über den eigenen Handle
  beendet. Gelöscht wird nur, was dieser Lauf angelegt hat: ein schon vorhandener Ordner
  `<work-dir>/store` oder eine Überschneidung von Vorlage und `--work-dir` bricht mit Exit 2 ab,
  ohne etwas anzufassen. Die Vorlagenprüfung läuft auch nach einem Fehler (geänderte Vorlage →
  Exit 3). Eine Einzeldatei-Vorlage wird samt `-wal`/`-shm`/`-journal` kopiert und gehasht.
  `COMMANDER_LAB_*`-Variablen (z. B. `COMMANDER_LAB_TOPDECK_DIR`) stehen unter
  `inputs.environment`; `compare` meldet abweichende Werte.
- 30 Routen, je zweimal abgefragt (`stable` = beide Antworten byte-gleich): `/`, `/tierliste.html`,
  `status`, `commanders`, `pool`, `layers`, `cohorts`, `allocation`, `evidence`, `data-report`,
  `strength` (POST), `rating-layers`, `universe/options`, `universe/counted`, `roles/audit`,
  `tournament-conversion`, `decks`, `revisions/<id>`, `outcomes`, `deck-browser`, `similar-decks`,
  `check`, `deck-doctor`, `deck-evidence`, `card-duel`, `cut-lab`, `deck-facts`, `land-advisor`,
  `castability`, `packages`. Deck und Karten kommen aus der Kopie selbst (`/api/decks` → Zweig
  `main` → `/api/revisions/<id>`) und stehen als `inputs` im Manifest; `compare` meldet
  abweichende Eingaben.
- Normalisierung: nur `image_cache.folder` in `GET /api/status`, und nur wenn der Wert genau
  `<Kopie>/images` ist (der Server meldet den absoluten Ordner der Kopie, der sich je Lauf
  unterscheidet). Rohlänge und Roh-Hash bleiben im Manifest.
- `writes`: je Schreibvorgang (Favorit, Markierung, Label, Entwurf, Revision, Primer,
  Universumsprofil) müssen alle 30 Antworten des laufenden Servers denen eines frisch gestarteten
  Servers auf derselben Kopie gleichen.

Abnahmelauf auf `main`-Quellstand (`src/` = `14a802bc`), Vorlage: ein Studio-Store mit 10.551
Korpus-Decks (254 MB, SHA-256 `2029752a…7e08`), Deck `chulane` (83 Karten), 4 Kerne, fremde Last
auf der Maschine (load 6,3 bis 6,6):

| Lauf | Start | Gesamt | load vorher/nachher | Ergebnis |
|---|---|---|---|---|
| 1 | 6,5 s | 48,0 s | 6,52 / 6,29 | 30 Routen, alle 200, alle `stable` |
| 2 | 2,6 s | 48,5 s | 6,29 / 6,56 | 30 Routen, alle 200, alle `stable` |
| `compare` 1 gegen 2 | | | | Exit 0, „30 routes, 0 difference(s)“; Roh-Hash `status` verschieden, normalisiert gleich |
| `writes` (alle 7, 30 Routen) | | 531 s | – / 4,46 | Exit 0; je Schreibvorgang Status 200 und 30 von 30 Antworten warm = nach Neustart |
| `writes` label, primer, universe_profile (33 Routen) | | 308 s | – / 8,03 | Exit 0; 33 von 33 warm = nach Neustart |

Empfindlichkeit der Schreibmatrix (Routen, deren Hash sich durch den Schreibvorgang gegenüber dem
Stand davor ändert; nur so belegt ein „gleich“ etwas): Favorit 3 (`pool`, `layers`,
`data-report`), Markierung 3 (dieselben), Label 1 (`pool`), Entwurf 1 (`decks`), Revision 3
(`allocation`, `decks`, `deck-browser`), Universumsprofil 3 (`status`, `data-report`, `strength`;
mit Zusatzroute 4), Primer 0 unter den 30 Leserouten. Deshalb fragt `writes` zusätzlich
`GET /api/decks/<id>/primer`, `GET /api/universe/profiles` und `GET /api/labels` ab
(`observer_requests`); damit ändert der Primer 1 Antwort und ist belegt.

Langsamste Antwort je Lauf: `data-report` 21,0 s / 23,6 s (kalt, Aufwärmphase läuft parallel).
Zeiten sind wegen der Fremdlast nur Orientierung, kein Messwert für Effizienzvergleiche.
