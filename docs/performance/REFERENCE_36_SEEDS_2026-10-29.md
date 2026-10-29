# Reference run of the 36-seed acceptance (2026-10-29)

Measurement only: three run files and this note. No bridge, fork, pin, pilot or sealed record
changes, so nothing here needs requalification. It replaces `REFERENCE_36_SEEDS_2026-10-26.md`
as the reference of the current pilot (#1035).

## 1. Why a new reference

The reference of 2026-10-26 (`b528082d5`) no longer describes `main`. Seeds 1-36 of a run on
`main` at `5d85d2dc4` against its run files (`benchmark_xmage_full_games.py compare`): hash equal
in 14 of 36 seeds. The pilot changes merged in between (mana budget #1041, archetype deltas
#1044, deck-construction gate #1039 and their follow-ups) moved the other 22 on purpose.

The staleness check of the old note (`check-reference`) did not say so: it watched the directory
`src/commander_lab/engine/rules/full_game_pilot/` but not the sibling modules
`full_game_pilot_*.py` that hold the mana-hold and discount code of the pilot steps 4a-2 and 5c.
`REFERENCE_WATCHED_PATHS` now lists them (#1057), and the test
`test_reference_staleness_at_head_is_reported_not_enforced` reports a stale reference as a
warning in every full test run.

## 2. Reference

| | |
|---|---|
| Lab commit | `5d85d2dc4` (`main` after #1057) |
| XMage pin | `90f5c4d3f8` (`config/rules_engines.json`, v13) |
| Bridge jar | sha256 `541365e5b2f0133af6603c67923f53ec79a68aac9cd4a1967c9987c44d5380fa` (pin jar plus the bridge classes; the bridge sources have not changed since the v13 repin) |
| Command | `scripts/build_xmage_cds_archive.py --jar JAR`, then `scripts/benchmark_xmage_full_games.py run --jar JAR --out OUT --seeds 1-36 --workers 4 --games-per-jvm 9 --fast` |
| Machine | 4 cores, one run at a time |
| Files | `docs/performance/measurements-2026-10-29/real36_main_5d85d2dc4_run1.json` (reference), `..._39940cd64_run1.json` and `..._39940cd64_run2.json` (twin runs one commit earlier) |

Result, `LOCAL_OBSERVED`, three runs, no CI credit, not a pass rate:

- 36 of 36 games finished in all three runs, no abort, no timeout.
- The three runs give the same hash and the same winner in 36 of 36 seeds
  (`compare run1 run2`: `identical 36/36`, `compare run1 reference`: `identical 36/36`). The two
  earlier runs were taken on `39940cd64`; the diff `39940cd64..5d85d2dc4` in the watched paths
  is only the card catalog threshold and the deck gate of #1057, which do not enter play for the
  shipped pool, and the identical hashes confirm that.
- Winners by seat: seat 1 4, seat 2 1, seat 3 22, seat 4 9. That is one pod with its own four
  decks, not a fairness measure.
- Decisions per game 1656 to 4713, median 2789.
- Speed is not a claim of this note: the runs were taken one after the other, not interleaved
  (game wall time of the whole run 402.6 s against 408.5 s for the twin of the earlier commit).

## 3. Use

At a repin or an engine change that is meant to keep the games, run the same command with the
new jar and compare:

```bash
python scripts/benchmark_xmage_full_games.py compare \
    docs/performance/measurements-2026-10-29/real36_main_5d85d2dc4_run1.json after.json
```

`identical 36/36` is the identity gate. The reference holds only while the watched paths and the
pin are those above (`check-reference` prints which of them changed): a change to any of them
moves hashes on purpose, and then the gate is the comparison of the run before and after that
change. The batch of fork cards (#979) and later pilot steps each get their own recalibration;
this file is the one for the state after #1057.
