# Reference run of the 36-seed acceptance after the payment fixes (2026-10-30, second note)

Refs #1067. Measurement only: two run files and this note. No bridge, fork, pin, pilot or sealed
record changes, so nothing here needs requalification. It replaces
`REFERENCE_36_SEEDS_2026-10-30.md` as the reference of the current pilot and pin.

## 1. Why a new reference

The pilot moved after the reference of the morning (`6db6934f5`): #1068 withholds a cast whose
mandatory extra mana cannot be paid and no longer counts loyalty abilities as payment sources.
Seeds 1-36 on `main` after #1068 against the morning reference: hash equal in 26 of 36 seeds
(`real36_fix1067_run1.json`, taken on the same code before the merge, is `identical 36/36`
against the run below).

## 2. Reference

| | |
|---|---|
| Lab commit | `2c3f8f82a` (`main` after #1068) |
| XMage pin | `2ec507b721` (`config/rules_engines.json`, v14) |
| Bridge jar | sha256 `035a5b4e6ff6ff2911d0b49ff070e4c9e9b0df501539bcc32462b832f3fef3a0` (pin jar plus the bridge classes; the bridge sources have not changed since the v13 repin, the jar carries the v14 pin literal) |
| Command | `scripts/build_xmage_cds_archive.py --jar JAR`, then `scripts/benchmark_xmage_full_games.py run --jar JAR --out OUT --seeds 1-36 --workers 4 --games-per-jvm 9 --fast` |
| Machine | 4 cores, one run at a time |
| Files | `docs/performance/measurements-2026-10-30/real36_main_2c3f8f82a_run1.json` (reference) and `..._run2.json` (twin) |

Result, `LOCAL_OBSERVED`, no CI credit, not a pass rate:

- 36 of 36 games finished in both runs, no abort, no timeout.
- Twin runs give the same hash and the same winner in 36 of 36 seeds
  (`compare run1 run2`: `identical 36/36`).
- Winners by seat: seat 1 3, seat 2 3, seat 3 21, seat 4 9. That is one pod with its own four
  decks, not a fairness measure.
- Decisions per game 1656 to 3902, median 2740.
- Speed is not a claim of this note: the runs were taken one after the other, not interleaved
  (game wall time of the whole run 1249.6 s against 1200.7 s for the twin).

## 3. Use

At an engine change that is meant to keep the games, run the same command with the new jar and
compare:

```bash
python scripts/benchmark_xmage_full_games.py compare \
    docs/performance/measurements-2026-10-30/real36_main_2c3f8f82a_run1.json after.json
```

`identical 36/36` is the identity gate. The reference holds only while the watched paths and the
pin are those above (`check-reference` prints which of them changed): a change to any of them
moves hashes on purpose, and then the gate is the comparison of the run before and after that
change.
