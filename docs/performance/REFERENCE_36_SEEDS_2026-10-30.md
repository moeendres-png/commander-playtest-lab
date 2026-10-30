# Reference run of the 36-seed acceptance (2026-10-30)

> Superseded by `REFERENCE_36_SEEDS_2026-10-30b.md` (after #1068, 2026-10-30).

Refs #1040. Measurement only: two run files and this note. No bridge, fork, pin, pilot or sealed
record changes, so nothing here needs requalification. It replaces
`REFERENCE_36_SEEDS_2026-10-29.md` as the reference of the current pilot and pin.

## 1. Why a new reference

The reference of 2026-10-29 (`5d85d2dc4`, pin `90f5c4d3f8`) no longer describes `main`: the
v14 repin (#1059) moved the pin and the commander-tax view (#1062) moved the pilot. The
staleness check of the old note said so. Seeds 1-36 on `main` after #1062 against the old
reference runs: hash equal in 5 of 36 seeds; against the v14 run taken before the tax change
(`real36_v14_pin2ec507b721_run1.json`) 31 of 36 differ, the same 31 that
`PILOT_COMMANDER_TAX_2026-10-30.md` reports.

## 2. Reference

| | |
|---|---|
| Lab commit | `6db6934f5` (`main` after #1062) |
| XMage pin | `2ec507b721` (`config/rules_engines.json`, v14) |
| Bridge jar | sha256 `035a5b4e6ff6ff2911d0b49ff070e4c9e9b0df501539bcc32462b832f3fef3a0` (pin jar plus the bridge classes; the bridge sources have not changed since the v13 repin, the jar carries the v14 pin literal) |
| Command | `scripts/build_xmage_cds_archive.py --jar JAR`, then `scripts/benchmark_xmage_full_games.py run --jar JAR --out OUT --seeds 1-36 --workers 4 --games-per-jvm 9 --fast` |
| Machine | 4 cores, one run at a time |
| Files | `docs/performance/measurements-2026-10-30/real36_main_6db6934f5_run1.json` (reference) and `..._run2.json` (twin) |

Result, `LOCAL_OBSERVED`, no CI credit, not a pass rate:

- 36 of 36 games finished in both runs, no abort, no timeout.
- Twin runs give the same hash and the same winner in 36 of 36 seeds
  (`compare run1 run2`: `identical 36/36`). The run `real36_tax_visible_1040_run1.json`, taken
  one commit earlier with the same pilot code, is also `identical 36/36` against `run1`.
- Winners by seat: seat 1 4, seat 2 3, seat 3 19, seat 4 10. That is one pod with its own four
  decks, not a fairness measure.
- Decisions per game 1656 to 3902, median 2690.
- Speed is not a claim of this note: the runs were taken one after the other, not interleaved
  (game wall time of the whole run 1099 s against 1122 s for the twin).

## 3. Use

At an engine change that is meant to keep the games, run the same command with the new jar and
compare:

```bash
python scripts/benchmark_xmage_full_games.py compare \
    docs/performance/measurements-2026-10-30/real36_main_6db6934f5_run1.json after.json
```

`identical 36/36` is the identity gate. The reference holds only while the watched paths and the
pin are those above (`check-reference` prints which of them changed): a change to any of them
moves hashes on purpose, and then the gate is the comparison of the run before and after that
change.
