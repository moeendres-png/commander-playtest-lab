# R-09 — #992 OOM-Fix im Deck-Vergleichs-Runner: Verifikation

Stand: 2026-10-25. Basis: Lab-main `217c34d95` (#1007). Fix-Commit (lokal, KEIN
Push/PR/Merge): `5fc7347be` in `~/workspace/github/wt-992` („#992: sequential
runner slims batch records at ingest"). Verifikation durch mich, nicht vom
Vorgänger übernommen. Alle Befehle liefen in `wt-992` mit
`source ~/workspace/venvs/commander-lab/bin/activate` und
`PYTHONPATH=~/workspace/github/wt-992/src`.

## 1. Symptom (Issue #992, offen, Label `agent:muse`)

Sequenzieller Runner: ~5,25 GB RSS bei 495 Records. Evidenzklasse:
**Issue-behauptet, hier NICHT neu gemessen** — eine RSS-Messung an 200/800
echten Spielen braucht JVM-Ketten und läuft nicht in dieser Lane (Haupt-Thread).
Was hier stattdessen gemessen wurde: der Mechanismus (Retention) und die
Heap-Kurve im Python-only-Test (s. Abschnitt 4).

## 2. Ursache (gemessen, DIRECTLY_VERIFIED)

`run_sequential_blocks` (`scripts/run_full_game_deck_comparison.py`, vor dem
Fix) machte `records.extend(report.records)` — jede volle
`FullGameBatchRecord` inkl. des Multi-MB-Transkripts in
`result.result_payload` blieb im Speicher. Beleg an einer echten M4-Datei:

- Datei `~/workspace/tmp/m4/speedtest_rogshai/games/11122690…json`:
  **2,30 MB gesamt, davon `result.result_payload` 1,58 MB** — exakt die
  Commit-Behauptung („1.58 MB of a 2.30 MB M4 record file").
- Die Datei ist eine `FullGameBatchRecord` (`case_id`, `status`, `result`,
  `resumed_from_completed_record`, `run_key`).

Rechnung: 495 Records × ~1,6 MB Payload ≈ 800 MB reines Payload, plus
Pydantic-Overhead, Duplikate in `combined`-Reports je Look und JVM-Seite —
die Größenordnung GB ist damit plausibel, auch wenn die 5,25 GB selbst hier
nicht reproduziert wurden.

## 3. Fix (gelesen, CODE_DERIVED + laufzeit-verifiziert)

Neu: `_slim_record_for_aggregate(record)` — ersetzt `result_payload` durch
nur `{"outcomes", "turn_number"}` (wenn vorhanden); alles Record-Level
(`case_id`, `status`, `failure_class`, `resumed_from_completed_record`)
und alle anderen `result`-Felder (`winner_seats`,
`semantic_transcript_sha256`, `decision_count`) bleiben durch
`model_copy` erhalten. `run_sequential_blocks` slimmt bei Ingest
(`records.extend(_slim_record_for_aggregate(record) for ...)`).

### Whitelist-Prüfung (von mir per Code-Lektüre, kein Vertrauen in den Docstring)

`aggregate_comparison` (`src/commander_lab/engine/rules/full_game_comparison.py:657`)
liest je Record genau:

| Gelesen | Wo | Vom Slimmen betroffen? |
|---|---|---|
| `record.case_id`, `record.status`, `record.failure_class` | Z. 671, 691, 696 | Nein (Record-Level, bleibt) |
| `record.resumed_from_completed_record` | Zähler in `run_sequential_blocks` (Z. ~380) | Nein (Record-Level, bleibt) |
| `result.winner_seats` | `_tested_outcome` (Z. 565) | Nein (`result`-Feld, bleibt) |
| `result.semantic_transcript_sha256` | Z. 708 | Nein (bleibt) |
| `result.decision_count` | Z. 712 | Nein (bleibt) |
| `result_payload["outcomes"]` | `_tested_placement` (Z. 643) | Nein (in Slim-Whitelist) |
| `result_payload["turn_number"]` | Z. 709 | Nein (in Slim-Whitelist) |

`COMPARISON_REPORT.json` (`main`, Z. ~596) = `comparison.model_dump` +
`sequential` + `swaps` + `pilot_readiness` + `engine` + `batch`-Zähler —
**keine Records** (gelesen). Einziger Produktions-Aufrufer von
`run_sequential_blocks` ist `main` (Z. 558); alle anderen Aufrufer sind
Tests. Ergebnis: **Die Whitelist-Behauptung stimmt.**

Grenze (ehrlich): Der zurückgegebene `combined`-Report enthält jetzt
geslimmte Records. Ein künftiger Konsument, der `combined.records`
Payloads außerhalb des Aggregats liest, sähe nur noch `outcomes` /
`turn_number`. Das ist kein heutiger Pfad (s. o.), aber ein Fallstrick
für später — der Byte-Identitäts-Test (s. Abschnitt 4) fängt nur
Aggregat-Änderungen, keine neuen Konsumenten.

## 4. Messung (von mir selbst gesehen, DIRECTLY_VERIFIED)

Test: `tests/unit/test_sequential_runner_memory.py` — 800 synthetische
Seeds, 50 KB Padding je Record (= Transkript-Ersatz), 160 Looks,
`tracemalloc`-Snapshots je Block.

| | Commit-Behauptung | Von mir gemessen |
|---|---|---|
| Post-Fix, Test | PASS | **1 passed in 8.29 s** |
| Post-Fix, Heap-Wachstum | +7,0 MB | **7.008.535 Bytes = 7,0 MB** (eigenes Skript `/tmp/r09_growth.py`, 160 Looks, 1.600 Records) |
| Pre-Fix, Test (Negativkontrolle) | FAIL | **FAILED, Wachstum 86.276.510 Bytes = 86,3 MB** (Skript temporär auf `217c34d95`-Stand gesetzt, danach Baum per `git status` + `git diff 5fc7347be` leer verifiziert) |
| Schwellwert | 10 MB | Liegt mit Abstand zwischen 7,0 und 86,3 MB |
| Kosten je Slim-Record | ~4,4 KB | 7.008.535 / 1.600 = 4.380 Bytes ≈ 4,4 KB (stimmt) |
| Byte-Identität | Aggregat byte-identisch | Test-Assertion `comparison.model_dump(mode="json") == reference.model_dump(mode="json")` **besteht** (im selben Lauf) |

Test-Suite (von mir gelaufen):

- `test_sequential_runner_memory.py`: **1 passed**
- `test_sequential_deck_comparison.py`: **8 passed**
- `test_full_game_batch_games_per_jvm.py`: **26 passed**
- Summe **35 = die Commit-Behauptung** (1 + 8 + 26; „batched" =
  `games_per_jvm`-Datei). Weiterer Umkreis ebenfalls grün:
  `test_full_game_parallel_comparison.py` 15, `test_qualify_game_batching.py`
  55, `test_full_game_run_batch.py` 8 (gesamt 112 in diesem Lauf).
- `ruff check` + `ruff format --check` auf beiden geänderten Dateien:
  **sauber**.
- `mypy scripts/run_full_game_deck_comparison.py`: **exakt 8 Fehler, alle
  `[import-untyped]` auf Import-Zeilen (47, 48, 49, 58, 74, 75, 76, 79),
  keiner im neuen Code**. „Unverändert gegen HEAD" gilt per Diff-Argument:
  Der Diff ändert keine Import-Zeile, also kann sich die
  Import-Fehler-Menge nicht geändert haben (CODE_DERIVED, nicht per
  Zweitlauf auf HEAD belegt — ein HEAD-Zweitlauf bräuchte einen zweiten
  Worktree und ist hier nicht nötig, weil die Fehlerklasse rein
  importseitig ist).

## 5. Was NICHT verifiziert ist (UNKNOWN, niemals PASS)

- RSS bei 200 und 800 echten Spielen (Akzeptanz aus #992): braucht
  JVM-Ketten → Haupt-Thread. Der Tracemalloc-Test ist ein Proxy, kein
  RSS-Beweis.
- Die 5,25 GB @ 495 Records: Issue-Zahl, Mechanismus plausibel (s. 2),
  aber nicht reproduziert.
- Ob der Fix auf einem 800-Spiele-Echtlauf das Aggregat byte-identisch
  hält: Der synthetische Test beweist es für synthetische Records; der
  Echtlauf-Beweis steht aus (gleiche Lane wie RSS).

## 6. Urteil

**Verifiziert, kein Repair nötig.** Alle vom Commit genannten Zahlen
(1,58/2,30 MB, 86,3 MB pre, 7,0 MB post, 35 Tests, ruff sauber, mypy 8)
wurden von mir unabhängig reproduziert oder per Code-Lektüre bestätigt.
Der einzige offene Punkt ist der Echtlauf (RSS + Byte-Identität an echten
Spielen) — das ist die #992-Akzeptanz und gehört in den PR als
„vor Merge zu messen", nicht als erledigt. Kein neuer Commit nötig;
`wt-992` steht unverändert auf `5fc7347be`, Baum sauber verifiziert.

## 7. Testkommando (selbst gelaufen)

```bash
cd ~/workspace/github/wt-992
source ~/workspace/venvs/commander-lab/bin/activate
PYTHONPATH=~/workspace/github/wt-992/src python3 -m pytest \
  tests/unit/test_sequential_runner_memory.py \
  tests/unit/test_sequential_deck_comparison.py \
  tests/unit/test_full_game_batch_games_per_jvm.py -q
ruff check scripts/run_full_game_deck_comparison.py tests/unit/test_sequential_runner_memory.py
ruff format --check scripts/run_full_game_deck_comparison.py tests/unit/test_sequential_runner_memory.py
PYTHONPATH=~/workspace/github/wt-992/src python3 -m mypy scripts/run_full_game_deck_comparison.py
```

## 8. PR-Body-Entwurf

Siehe `PR_BODY_R09.md` (copy-paste-fertig, ohne Merge-Claim: die
Echtlauf-Akzeptanz ist dort als offen markiert).
