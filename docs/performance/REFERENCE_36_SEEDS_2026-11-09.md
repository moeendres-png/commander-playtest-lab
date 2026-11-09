# Reference run of the 36-seed acceptance after the ramp-rounds pilot change (2026-11-09)

Refs #1070. Measurement only: this note points at the two run files of the measurement folder. No
bridge, fork, pin or sealed record changes, so nothing here needs requalification. It replaces
`REFERENCE_36_SEEDS_2026-11-08.md` as the reference of the current pilot, bridge and pin.

## 1. Why a new reference

`benchmark_xmage_full_games.py check-reference` reported the reference of `82d781ef3` stale: one watched
file changed, `src/commander_lab/agents/pilots.py`. That is the pilot change of #1149 (the two ramp
terms decay with the game round instead of the engine's per-player turn counter,
`docs/performance/PILOT_RAMP_ROUNDS_2026-11-09.md`). It moves hashes on purpose in every game in which a
ramp option is on offer.

Seeds 1-36 on the current code against the old reference
(`compare real36_main_5bd29ab6f_run1.json real36_main_49bdc94b7_run1.json`): hash equal in 1 of 36
seeds, the same winner in 22 of 36. A hash comparison cannot say whether the games got better; the
win rate stays UNDECIDED.

## 2. Reference

| | |
|---|---|
| Lab commit | `49bdc94b7` (`main` after #1149) |
| XMage pin | `f4d12f6e80` (`config/rules_engines.json`, v15) |
| Bridge jar | sha256 `36167ba71e480c6c85f95df3bd24feac5a75c94d0752e71f25544a861c9064a7`, built from the Lab sources of `5bd29ab6f`. `engine-bridge/` is identical on `49bdc94b7` (`git diff 5bd29ab6f 49bdc94b7 -- engine-bridge` is empty), so the jar is the jar of this commit's bridge classes |
| Command | `scripts/benchmark_xmage_full_games.py run --jar JAR --out OUT --seeds 1-36 --workers 2 --games-per-jvm 9 --fast` |
| Machine | 4 cores, two runs one after the other, only light Python analysis alongside |
| Files | `docs/performance/measurements-2026-11-09/real36_main_49bdc94b7_run1.json` (reference) and `..._run2.json` (twin) |

Result, `LOCAL_OBSERVED`, no CI credit, not a pass rate:

- 36 of 36 games finished in both runs, no abort, no timeout.
- Twin runs give the same hash and the same winner in 36 of 36 seeds (`compare run1 run2`:
  `identical 36/36`).
- Winners by seat: seat 1 6, seat 2 0, seat 3 25, seat 4 5 (reference of `5bd29ab6f`: 9, 0, 22, 5).
  That is one pod with its own four decks, not a fairness measure.
- Decisions per game 1853 to 4269, median 2979.0, mean 2969.7 (before: 1844 to 5680, median 2775.0,
  mean 2988.6).
- Speed is not a claim of this note: elapsed 433.8 s and 435.0 s with two workers, taken one after the
  other, not interleaved (the reference of `5bd29ab6f` took 415.0 s).

## 3. Use

At an engine or pilot change that is meant to keep the games, run the same command with the new jar and
compare:

```bash
python scripts/benchmark_xmage_full_games.py compare \
    docs/performance/measurements-2026-11-09/real36_main_49bdc94b7_run1.json after.json
```

`identical 36/36` is the identity gate. The reference holds only while the watched paths and the
pin are those above (`check-reference` prints which of them changed): a change to any of them moves
hashes on purpose, and then the gate is the comparison of the run before and after that change.
