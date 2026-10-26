# Reference run of the 36-seed acceptance (2026-10-24)

Superseded on 2026-10-26 by `REFERENCE_36_SEEDS_2026-10-26.md`: the pilot answers changed in
the combat, payment, timing and tie-break steps after `053708e56`. Kept as history.

Result of #996. Tooling and a measurement only: two run files and this note. No bridge, fork,
pin or sealed record changes, so nothing here needs requalification.

## 1. Why a new reference

The 36-seed acceptance of the repin process (`docs/claude/REPIN_RUNBOOK.md`, section 2) is a
run, not a stored set of hashes: 36 seeds of the real pod are played with the new jar and
compared with a run of the previous state. Between the v13 repin and today the pilot changed
in three steps (the mulligan ruler, the amount and cost rules, the target ladder; the earlier
self-target, equip, convoke and card-catalog changes came before). The 36-seed runs stored in
the repo (`measurements-2026-10-21`) are from earlier pins and pilots, so a comparison of the
next repin with them would report seeds as moved for reasons that have nothing to do with the
repin.

Seeds 1-24 of this run against 24-seed runs of earlier states of `main` (same pod, same pin,
`benchmark_xmage_full_games.py compare`):

| Earlier state | Hashes equal | Same winner |
|---|---:|---:|
| `main` before the mulligan ruler | 0 of 24 | 9 of 24 |
| `main` with the mulligan ruler, before the amount and cost rules | 1 of 24 | 13 of 24 |
| `main` with the target ladder (the run measured on its pull request) | 24 of 24 | 24 of 24 |

The last row is also a cross-check of the jar: the three earlier runs used a jar built from the
bridge sources of `73b5df506`, and no commit has touched `engine-bridge/` since, so it is the same
pin and the same bridge sources built again; the hashes agree seed by seed.

## 2. Reference

| | |
|---|---|
| Lab commit | `053708e56` (`main` after #1004) |
| XMage pin | `90f5c4d3f8` (`config/rules_engines.json`, v13) |
| Bridge jar | sha256 `541365e5b2f0133af6603c67923f53ec79a68aac9cd4a1967c9987c44d5380fa` (pin jar plus the bridge classes of that commit; the bridge sources have not changed since the v13 repin) |
| Command | `scripts/build_xmage_cds_archive.py --jar JAR`, then `scripts/benchmark_xmage_full_games.py run --jar JAR --out OUT --seeds 1-36 --workers 4 --games-per-jvm 9 --fast` |
| Machine | 4 cores, one run at a time |
| Files | `docs/performance/measurements-2026-10-24/real36_main_053708e56_run1.json` (reference) and `..._run2.json` (twin) |

Result, `LOCAL_OBSERVED`, two runs, no CI credit, not a pass rate:

- 36 of 36 games finished in both runs, no abort, no timeout.
- The twin run gives the same hash and the same winner in 36 of 36 seeds
  (`benchmark_xmage_full_games.py compare run1 run2`: `identical 36/36`).
- Winners by seat: seat 1 15, seat 2 3, seat 3 8, seat 4 10. That is one pod with its own four
  decks, not a fairness measure.
- Decisions per game 2098 to 5361, median 3342.
- Speed is not a claim of this note: the second run was 5.5 % slower in game wall time and
  5.1 % in child CPU than the first, one after the other and not interleaved.

## 3. Use

At a repin or an engine change that is meant to keep the games, run the same command with the
new jar and compare:

```bash
python scripts/benchmark_xmage_full_games.py compare \
    docs/performance/measurements-2026-10-24/real36_main_053708e56_run1.json after.json
```

`identical 36/36` is the identity gate. The reference holds only while the pilot code, the
bridge sources and the pin are those above: a change to any of them moves hashes on purpose, and
then the gate is the comparison of the run before and after that change, as in section 1. The
Owner decided that the later pilot phases (combat, payment solver, timing gates) and the batch
of fork cards each get their own recalibration; this file is the one for the state after the
mulligan, amount/cost and target changes.
