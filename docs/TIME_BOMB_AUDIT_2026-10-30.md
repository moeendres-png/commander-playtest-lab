# Time-bomb audit: code and tests whose result depends on the wall clock (2026-10-30)

Refs #1028. Source lock: Lab `main` at `692847dab`. Evidence class `LOCAL_OBSERVED` for the runs,
`CODE_DERIVED` for the static list. Two independent passes agree: Muse's report
(`handover/2026-10-26/time-bombs/REPORT.md` on `muse/claude-handover`, commit `c246cc58a`, run on
`6fb26071b`) and the re-run below on today's `main`.

## 1. Static list (AST, `src/commander_lab`, `scripts`, `tests`)

Calls of `datetime.now/utcnow/today`, `date.today` and `time.time/monotonic/perf_counter/
process_time` (module or `from` import, any alias), found by walking the syntax tree, so comments
and strings never count.

| Tree | Call sites | `datetime.now` | `time.time` | `time.monotonic` | `perf_counter` / `process_time` | `date.today` |
|---|---|---|---|---|---|---|
| `src/commander_lab` | 56 | 26 | 6 | 18 | 6 | 0 |
| `scripts` | 63 | 9 | 14 | 29 | 8 + 2 | 1 |
| `tests` | 27 | 1 | 5 | 18 | 2 | 1 |

Muse counts 103 in `src` + `scripts` (it leaves out `perf_counter` and `process_time`):
119 − 16 = 103, and 27 − 2 = 25 in `tests`. Both scans agree after that difference.

Classes (Muse's classification, re-checked for every site that can decide something):

- **A, stamps** (32 sites): `created_at`, `retrieved_at`, `observed_at` and the like. Nothing reads
  them back to decide. Checked: `storage/result_cache.py` (`get` compares key and hash only),
  `evidence_epoch.py`, `process_manager.py`, `meta/store.py`, `models/provenance.py`.
- **M, T: durations** (`time.monotonic`, `time.time` differences): independent of the calendar.
- **B, decides on a date** (3): `whole_deck/meta.py:is_source_stale` (12-month window, `now`
  injectable, the #1025 site), `scripts/refresh_meta.py` (`--as-of`, report only),
  `scripts/upstream_delta.py` (`today` injectable, pin age in weeks).
- **C, cache or lock on time** (3): `engine/rules/full_game.py` orphan cleanup (24 h by mtime),
  `whole_deck/optimizer_v2.py` `OptimizerLock` (stale after 12 h),
  `scripts/run_current_boundary_qualification.py` (`not_before`, relative to the run start).

## 2. Shifted-clock run

`time-machine` 3.6.0 moves the clock of the whole test process (`datetime`, `date`, `time.time`,
`time.gmtime`; `tick=True`), `time.monotonic` is left alone. Plugin: a `pytest_configure` hook that
starts the traveller when `SHIFT_TO` is set. Probe inside a test: year 2035 for `datetime.now`,
`date.today` and `time.gmtime` with the shift, 2026 without.

Command: `SHIFT_TO=<date> PYTHONPATH=<plugin dir>:src python -m pytest tests/unit -p shift_clock
-q` (same `--ignore` set as CI locally: the two collection errors for the missing asyncio plugin
and the packaging smoke that needs build isolation).

| Clock | Result |
|---|---|
| real (plugin loaded, control) | 3239 passed, 2 skipped (both Windows junction tests) |
| 2028-01-01 | 1 failed, 3238 passed, 2 skipped |
| 2035-01-01 | 1 failed, 3238 passed, 2 skipped |

The control is green, so the difference counts. The one failure in both shifted runs is
`test_full_game_private_card_repository.py::test_orphans_older_than_a_day_are_removed_and_slots_and_young_ones_kept`:
it made the "young" directory with the file system's mtime and the cleanup compared it with
`time.time()`, so with a shifted `time.time` the young directory looked 3+ years old. Production
code is right (it removes directories older than 24 h); the test mixed two clocks. Fixed in this
change by anchoring both to `time.time()`. Before the fix the test fails under 2035 and passes after
(same command, one test file), and it passes under the real clock.

This matches Muse's run on `6fb26071b` (2028: 1 failed, the same test; 2035: the same test plus a
disk-dependent flake in `test_run_manifest_integrity.py` that did not show up here and does not
depend on the clock).

## 3. Result

No real time bomb in `tests/unit`, no production code that breaks with the date. The #1025 site
stays the only one of its shape and its fix is merged.

## 4. Dates on which behavior changes by design (not failures)

The 12-month rule of the meta lane (PR6) takes sources with weight 0 from their `retrieved_at` plus
12 months. `scripts/refresh_meta.py --as-of DATE` prints it:

| From | What goes stale |
|---|---|
| 2027-08-05 | `meta-2026-08-05-phase12-1` (9 sources) and `local-project-meta-2026-08-05` inside the 08-13 snapshot |
| 2027-08-13 | the remaining sources of `meta-2026-08-13-whole-deck-phase2-1` |
| 2027-10-25 | `meta-2026-10-25-chulane-refresh-1` and `-rogshai-refresh-1` and the two package files |

`whole_deck/search_construct.py` loads `WHOLE_DECK_META_SNAPSHOT_ID = meta-2026-08-13-whole-deck-phase2-1`,
so from 2027-08-13 the deck search finds no fresh meta reference (`build_meta_functional_profile`
raises, the search skips the band) and runs without meta references; the packages follow on
2027-10-25. Measured for the commander the search uses (Ishai / Rograkh, 4 matching meta references):
4 of 4 fresh on 2027-08-04, 3 of 4 on 2027-08-06 (the `local_meta` band is gone), 0 of 4 on
2027-08-14. Nothing fails; the search result changes. A refresh and a repoint of that constant before
then keeps it. This is a planning date, not a defect.
