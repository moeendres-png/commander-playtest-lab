# Reference run of the 36-seed acceptance after the tie-break by rng (2026-10-31, second note)

Refs #1090. Measurement only: this note points at the two run files that #1091 brought. No bridge,
fork, pin, pilot or sealed record changes, so nothing here needs requalification. It replaces
`REFERENCE_36_SEEDS_2026-10-31.md` as the reference of the current pilot and pin.

## 1. Why a new reference

#1091 lets the pilot break a tie between different cards, modes, trigger orders and colours with
the decision's own rng instead of the alphabet (`PILOT_TIEBREAK_CLASSES_2026-10-31.md`).
`benchmark_xmage_full_games.py check-reference` reported the reference of `b19a2562f` stale on the
pilot file `full_game_pilot/choices.py`.

Seeds 1-36 on the new code against the old reference
(`compare real36_main_b19a2562f_run1.json real36_pilot_tiebreak_3578aaa38_run1.json`): hash equal in 0
of 36 seeds, the same winner in 24 of 36. That is expected: a tie shows up in nearly every game. A hash
comparison cannot say whether the games got better; the win rate stays UNDECIDED.

## 2. Reference

| | |
|---|---|
| Lab commit | `889335c38` (`main` after #1091) |
| XMage pin | `2ec507b721` (`config/rules_engines.json`, v14) |
| Bridge jar | sha256 `035a5b4e6ff6ff2911d0b49ff070e4c9e9b0df501539bcc32462b832f3fef3a0` (same jar as the reference of 2026-10-31) |
| Command | `scripts/benchmark_xmage_full_games.py run --jar JAR --out OUT --seeds 1-36 --workers 2 --games-per-jvm 9 --fast` |
| Machine | 4 cores, one run at a time |
| Files | `docs/performance/measurements-2026-10-31/real36_pilot_tiebreak_3578aaa38_run1.json` (reference) and `..._run2.json` (twin) |

The runs were taken on the branch head `3578aaa38` of #1091. `889335c38` is the squash of that
branch; `git diff 3578aaa38 889335c38` over all watched paths of `check-reference` is empty (the
commits after `3578aaa38` change tests only), so the two describe the same inputs.

Result, `LOCAL_OBSERVED`, no CI credit, not a pass rate:

- 36 of 36 games finished in both runs, no abort, no timeout.
- Twin runs give the same hash and the same winner in 36 of 36 seeds (`compare run1 run2`:
  `identical 36/36`).
- Winners by seat: seat 1 4, seat 2 4, seat 3 20, seat 4 8 (reference of `b19a2562f`: 6, 3, 21, 6).
  That is one pod with its own four decks, not a fairness measure.
- Decisions per game 1847 to 4054, median 2639.0, mean 2688.6 (before: 1618 to 4176, median 2579.5).
- Speed is not a claim of this note: the runs were taken one after the other, not interleaved.

## 3. Worker count

As in the reference of 2026-10-31 the runs used `--workers 2`, because the rule for this work allows
at most two bridge JVMs at once; the documented command uses four. The hash does not depend on the
worker count as far as it was checked (33 of 36 equal between two and four workers in #1079, the
others being the colour fix). That is evidence, not a proof. The elapsed times (449.5 s and 474.5 s)
are not comparable with a four-worker run.

## 4. Use

At an engine change that is meant to keep the games, run the same command with the new jar and
compare:

```bash
python scripts/benchmark_xmage_full_games.py compare \
    docs/performance/measurements-2026-10-31/real36_pilot_tiebreak_3578aaa38_run1.json after.json
```

`identical 36/36` is the identity gate. The reference holds only while the watched paths and the
pin are those above (`check-reference` prints which of them changed): a change to any of them moves
hashes on purpose, and then the gate is the comparison of the run before and after that change.
