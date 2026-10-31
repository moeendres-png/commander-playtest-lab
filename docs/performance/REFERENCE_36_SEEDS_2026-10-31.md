# Reference run of the 36-seed acceptance after the discard and colour fixes (2026-10-31)

Refs #1071. Measurement only: two run files and this note. No bridge, fork, pin, pilot or sealed
record changes, so nothing here needs requalification. It replaces
`REFERENCE_36_SEEDS_2026-10-30b.md` as the reference of the current pilot and pin.

## 1. Why a new reference

Two pilot changes moved after the reference of 2026-10-30 (`2c3f8f82a`): #1078 chooses the card to
discard from the own hand by value instead of by the alphabetically last name, and #1079 lets the
colour choice inside a nested payment serve the spell around it.
`benchmark_xmage_full_games.py check-reference` reported the old reference stale on five watched
pilot files.

Seeds 1-36 on the new code against the old reference run
(`compare real36_main_2c3f8f82a_run1.json real36_main_b19a2562f_run1.json`): hash equal in 0 of
36 seeds. That is expected and not a regression signal: a discard happens in nearly every game, and
in all 24 games of the real-request sample the first answer that differs is a discard from the
hand (#1078). Seeds 4, 13 and 30 also differ because of #1079 (all three on the colour choice for
Hall of Oracles, measured in #1079 against the old reference: 33 of 36 equal). A hash comparison
cannot say whether the games got better; the win rate stays UNDECIDED.

## 2. Reference

| | |
|---|---|
| Lab commit | `b19a2562f` (`main` after #1078) |
| XMage pin | `2ec507b721` (`config/rules_engines.json`, v14) |
| Bridge jar | sha256 `035a5b4e6ff6ff2911d0b49ff070e4c9e9b0df501539bcc32462b832f3fef3a0` (same jar as the reference of 2026-10-30) |
| Command | `scripts/build_xmage_cds_archive.py --jar JAR`, then `scripts/benchmark_xmage_full_games.py run --jar JAR --out OUT --seeds 1-36 --workers 2 --games-per-jvm 9 --fast` |
| Machine | 4 cores, one run at a time |
| Files | `docs/performance/measurements-2026-10-31/real36_main_b19a2562f_run1.json` (reference) and `..._run2.json` (twin) |

The runs were taken on the head of #1078 (`80cbbda54`). `b19a2562f` is the squash of that head;
`git diff 80cbbda54 b19a2562f` over all watched paths of `check-reference` is empty, so the two
describe the same inputs.

Result, `LOCAL_OBSERVED`, no CI credit, not a pass rate:

- 36 of 36 games finished in both runs, no abort, no timeout.
- Twin runs give the same hash and the same winner in 36 of 36 seeds
  (`compare run1 run2`: `identical 36/36`).
- Winners by seat: seat 1 6, seat 2 3, seat 3 21, seat 4 6 (reference of 2026-10-30: 3, 3, 21, 9).
  That is one pod with its own four decks, not a fairness measure; a shift of three games on 36
  seeds says nothing about playing strength.
- Decisions per game 1618 to 4176, median 2579.5 (before: 1656 to 3902, median 2740.5).
- Speed is not a claim of this note: the runs were taken one after the other, not interleaved.

## 3. Deviation from the documented command

The reference of 2026-10-30 was taken with `--workers 4`; this one with `--workers 2`, because the
rule for this work allows at most two bridge JVMs at once. The hash does not depend on the worker
count as far as it was checked: the 36-seed control of #1079 ran with two workers and matched the
four-worker reference in 33 of 36 seeds, the three others being the colour fix. That is evidence,
not a proof. `compare` prints a note for the time lines of two files with different worker counts
and gives no CPU line; the elapsed time (343.0 s with four workers, 425.6 s with two) is not a speed
difference. A future run with `--workers 4` should give the same hashes; if it does not, that is a
finding about worker independence and not about the pilot.

## 4. Use

At an engine change that is meant to keep the games, run the same command with the new jar and
compare:

```bash
python scripts/benchmark_xmage_full_games.py compare \
    docs/performance/measurements-2026-10-31/real36_main_b19a2562f_run1.json after.json
```

`identical 36/36` is the identity gate. The reference holds only while the watched paths and the
pin are those above (`check-reference` prints which of them changed): a change to any of them
moves hashes on purpose, and then the gate is the comparison of the run before and after that
change.
