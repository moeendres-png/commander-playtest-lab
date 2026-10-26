# Reference run of the 36-seed acceptance (2026-10-26)

Measurement only: two run files and this note. No bridge, fork, pin, pilot or sealed record
changes, so nothing here needs requalification. It replaces `REFERENCE_36_SEEDS_2026-10-24.md`
as the reference of the current pilot, which is the state after the combat, payment, timing,
tie-break and commander-damage steps of the pilot work.

## 1. Why a new reference

The 36-seed acceptance of the repin process (`docs/claude/REPIN_RUNBOOK.md`, section 2) is a run,
not a stored set of hashes: 36 seeds of the real pod are played with the new jar and compared
with a run of the previous state. The reference of 2026-10-24 (`053708e56`, after the target
ladder) no longer describes `main`: since then the block declaration (#1006), the payment solver
(#1007, #1009), the timing gates (#1010), the land, land-search and planeswalker tie-breaks
(#1015), the attack-defender tie-break (#1019) and the commander damage input (#1022) changed what
the pilot answers. Comparing a repin with the old reference would report seeds as moved for
reasons that have nothing to do with the repin.

Seeds 1-36 of this run against the reference of 2026-10-24 (`benchmark_xmage_full_games.py
compare`): hash equal in 0 of 36, same winner in 9 of 36. That is the expected size of the effect
of those steps on whole games, not a defect.

The Meta-Lane steps merged in the same span (#1016 to #1018, #1020, #1021, #1023) touch only
`whole_deck/` and the snapshot schema; they do not enter the game path, and the twin runs below
are taken on the state that contains them.

## 2. Reference

| | |
|---|---|
| Lab commit | `b528082d5` (`main` after #1023) |
| XMage pin | `90f5c4d3f8` (`config/rules_engines.json`, v13) |
| Bridge jar | sha256 `541365e5b2f0133af6603c67923f53ec79a68aac9cd4a1967c9987c44d5380fa` (pin jar plus the bridge classes; the bridge sources have not changed since the v13 repin) |
| Command | `scripts/build_xmage_cds_archive.py --jar JAR`, then `scripts/benchmark_xmage_full_games.py run --jar JAR --out OUT --seeds 1-36 --workers 4 --games-per-jvm 9 --fast` |
| Machine | 4 cores, one run at a time |
| Files | `docs/performance/measurements-2026-10-26/real36_main_b528082d5_run1.json` (reference) and `..._run2.json` (twin) |

Result, `LOCAL_OBSERVED`, two runs, no CI credit, not a pass rate:

- 36 of 36 games finished in both runs, no abort, no timeout.
- The twin run gives the same hash and the same winner in 36 of 36 seeds
  (`benchmark_xmage_full_games.py compare run1 run2`: `identical 36/36`).
- Winners by seat: seat 1 3, seat 2 2, seat 3 21, seat 4 10 (reference of 2026-10-24: 15, 3, 8,
  10). That is one pod with its own four decks, not a fairness measure; the move away from seat 1
  matches what the attack-defender tie-break did on its own pull request (#1019).
- Decisions per game 1656 to 4955, median 2767 (reference of 2026-10-24: 2098 to 5361, median
  3342).
- Speed is not a claim of this note: the second run was 0.7 % faster in game wall time and 1.2 %
  in child CPU than the first, one after the other and not interleaved, and the run against the
  reference of 2026-10-24 was taken in another session. Neither is an interleaved comparison.

## 3. Use

At a repin or an engine change that is meant to keep the games, run the same command with the
new jar and compare:

```bash
python scripts/benchmark_xmage_full_games.py compare \
    docs/performance/measurements-2026-10-26/real36_main_b528082d5_run1.json after.json
```

`identical 36/36` is the identity gate. The reference holds only while the pilot code, the
bridge sources and the pin are those above: a change to any of them moves hashes on purpose, and
then the gate is the comparison of the run before and after that change, as in section 1. The
batch of fork cards (#979) and later pilot steps each get their own recalibration; this file is
the one for the state after the pilot steps listed in section 1.
