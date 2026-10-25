# PR-Body-Entwurf: #992 — Sequential runner slims batch records at ingest

> Entwurf (Muse-Lane, NICHT gepusht, NICHT als PR angelegt). Basis:
> lokaler Commit `5fc7347be` auf Lab-main `217c34d95` in `wt-992`.
> Verifikation: `~/workspace/tmp/max-review/pass2-r/R09_OOM_FIX.md`.

Refs #992

**Problem:** `run_sequential_blocks` behielt jede volle
`FullGameBatchRecord` inkl. des Multi-MB-Transkripts in
`result.result_payload` — RSS wuchs mit der Spielzahl (Issue: ~5,25 GB
bei 495 Records).

**Fix:** `_slim_record_for_aggregate` ersetzt das Payload bei Ingest
durch nur `outcomes` + `turn_number` — genau die Felder, die
`aggregate_comparison` liest (per Code-Lektüre verifiziert:
`case_id`/`status`/`failure_class`/`resumed`-Flag auf Record-Ebene sowie
`winner_seats`/`semantic_transcript_sha256`/`decision_count` bleiben
durch `model_copy` erhalten). Volle Records bleiben auf Platte (eine
Datei je Spiel, Batch-Layer); `COMPARISON_REPORT.json` enthält nur
Zähler, keine Records — seine Bytes sind unverändert.

**Messung (Python-only-Test, kein JVM-Lauf):**
`tests/unit/test_sequential_runner_memory.py` — 800 synthetische Seeds,
50 KB Padding je Record, 160 Looks, `tracemalloc`:

- Vor Fix: Test FAILT, Heap-Wachstum 86,3 MB (Negativkontrolle, selbst
  gegen den Pre-Fix-Stand gelaufen).
- Nach Fix: Test PASST, Wachstum 7,0 MB (Schwellwert 10 MB, je
  Slim-Record ~4,4 KB).
- Aggregat byte-identisch gegen den direkten Voll-Record-Vergleich
  (Assertion im selben Test).

**Tests (selbst gelaufen):** 35 passed
(`test_sequential_runner_memory` 1, `test_sequential_deck_comparison` 8,
`test_full_game_batch_games_per_jvm` 26); `ruff check` + `ruff format`
sauber; `mypy`: 8 vorbekannte `[import-untyped]`-Fehler auf
Import-Zeilen, keiner im neuen Code.

**Offen vor Merge (ehrlich, kein Claim):** Die #992-Akzeptanz — Peak-RSS
bei 200 und 800 echten Spielen + Aggregat byte-identisch am Echtlauf —
ist mit diesem Python-only-Test NICHT gemessen. Sie braucht eine
JVM-Kette und muss vor dem Merge nachgeholt werden. Der Fix ändert kein
Spiel-Verhalten (Runner-only, kein Fork/Repin).

**Risiko:** Sehr niedrig. Einzige Falle: Der zurückgegebene
`combined`-Report enthält geslimmte Records — ein künftiger Konsument,
der `combined.records`-Payloads außerhalb des Aggregats liest, sähe nur
noch `outcomes`/`turn_number`. Heute gibt es keinen solchen Pfad
(einziger Produktions-Aufrufer ist `main`).
