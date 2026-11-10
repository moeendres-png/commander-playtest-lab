# Reference run of the 36-seed acceptance after the counter-fuelled mana change (2026-11-10, second)

Refs #1070. Measurement only: no bridge, fork, pin or sealed record changes, so nothing here needs
requalification. It replaces `REFERENCE_36_SEEDS_2026-11-10.md` as the reference of the current pilot, bridge
and pin.

## 1. Why a new reference

`benchmark_xmage_full_games.py check-reference` reported the reference of `823903239` stale: two watched files
changed, `src/commander_lab/engine/rules/full_game_pilot/common.py` and `payment.py`. That is the pilot change of
#1158 (`docs/performance/PILOT_COUNTER_FUELLED_MANA_2026-11-10.md`: no tap of a mana ability that has no counters
to add). Seeds 1-36 on the new code against the old reference: hash equal in 33 of 36 seeds (different: seeds 1,
18 and 25). The branch run before the merge gave the same three. A hash comparison cannot say whether the games
got better; the win rate stays UNDECIDED.

## 2. Reference

| | |
|---|---|
| Lab commit | `2cc29df14` (`main` after #1158) |
| XMage pin | `f4d12f6e80` (`config/rules_engines.json`, v15) |
| Bridge jar | sha256 `36167ba71e480c6c85f95df3bd24feac5a75c94d0752e71f25544a861c9064a7`, built from the Lab sources of `5bd29ab6f`; `engine-bridge/` is unchanged since |
| Command | `scripts/benchmark_xmage_full_games.py run --jar JAR --out OUT --seeds 1-36 --workers 2 --games-per-jvm 9 --fast` |
| Files | `docs/performance/measurements-2026-11-10/real36_main_2cc29df14_run1.json` (reference) and `..._run2.json` (twin) |

Result, `LOCAL_OBSERVED`, no CI credit, not a pass rate:

- 36 of 36 games finished in both runs, no abort, no timeout.
- Twin runs give the same hash and the same winner in 36 of 36 seeds (`compare run1 run2`: `identical 36/36`).
- Winners by seat: seat 1 7, seat 2 0, seat 3 24, seat 4 5 (reference of `823903239`: 6, 0, 25, 5). One pod with
  its own four decks, not a fairness measure.
- Decisions per game 1853 to 4269, median 2979.0, mean 2957.2 (before: median 2979.0, mean 2969.2).
- Speed is not a claim: elapsed 418.0 s and 413.8 s with two workers, one after the other (before 422.4 s).

## 3. Use

```bash
python scripts/benchmark_xmage_full_games.py compare \
    docs/performance/measurements-2026-11-10/real36_main_2cc29df14_run1.json after.json
```

`identical 36/36` is the identity gate. The reference holds only while the watched paths and the pin are those
above (`check-reference` prints which changed).
