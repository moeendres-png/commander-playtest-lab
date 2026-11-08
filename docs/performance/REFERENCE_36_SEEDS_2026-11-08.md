# Reference run of the 36-seed acceptance after repin v15 (2026-11-08)

Refs #1070. Measurement only: this note points at the three run files of the measurement folder. No
bridge, fork, pin, pilot or sealed record changes, so nothing here needs requalification. It replaces
`REFERENCE_36_SEEDS_2026-10-31b.md` as the reference of the current pilot, bridge and pin.

## 1. Why a new reference

`benchmark_xmage_full_games.py check-reference` reported the reference of `889335c38` stale: 20 watched
files changed and the XMage pin moved. Two things moved the games, and they are not the same thing:

- **The pin** (repin v15, `f4d12f6e80`, #1143). Its own effect was measured on the same Lab code with
  the jars side by side (`UPSTREAM_PICKS_V15_2026-11-08.md`): 36 of 36 seeds equal to the old reference
  and 44 of 44 precon pods equal to the v14 jar. The pin alone did not move a hash in those 80 games.
- **Lab code between the old reference and the repin**: the pilot changes of 2026-11-02 to 2026-11-06
  (paid-cast ranking, payment plans, optional mana costs, counter growth, exiled-card cycles,
  combat finishing windows, native board colours in payment choices), the bridge sources they use and
  the card-fact cache, and the dependency updates of `engine-bridge/pom.xml`. These move hashes on
  purpose. A watched opponent deck file also changed in the privacy commit of 2026-10-31, but only
  its two source-id fields (`redacted`); no card of the deck moved.

Seeds 1-36 on the current code against the old reference
(`compare real36_pilot_tiebreak_3578aaa38_run1.json real36_main_5bd29ab6f_run1.json`): hash equal in 0
of 36 seeds, the same winner in 20 of 36. A hash comparison cannot say whether the games got better;
the win rate stays UNDECIDED.

## 2. Reference

| | |
|---|---|
| Lab commit | `82d781ef3` (`main` after the second seal of repin v15, #1146) |
| XMage pin | `f4d12f6e80` (`config/rules_engines.json`, v15) |
| Bridge jar | sha256 `36167ba71e480c6c85f95df3bd24feac5a75c94d0752e71f25544a861c9064a7`, built from the Lab sources of `5bd29ab6f` against XMage jars installed from exactly `f4d12f6e80` (`mvn package -DskipTests`, not byte-reproducible) |
| Command | `scripts/benchmark_xmage_full_games.py run --jar JAR --out OUT --seeds 1-36 --workers 2 --games-per-jvm 9 --fast` |
| Machine | 4 cores, one run at a time, no other local load |
| Files | `docs/performance/measurements-2026-11-08/real36_main_5bd29ab6f_run1.json` (reference) and `..._run2.json` (twin) |

The two runs were taken on `5bd29ab6f` (`main` after the first seal). `82d781ef3` is the second seal.
`git diff 5bd29ab6f 82d781ef3` over all watched paths of `check-reference` lists one file,
`config/rules_engines.json`, six lines changed on each side: the `current_qualification` block (epoch,
engine commit, artifact digest, Lab commit, note) and the pin prose that names the sealed epochs. No
game path reads those fields, and the four-worker run in section 3 was taken on the tree of
`82d781ef3` itself and gives the same hashes.

Result, `LOCAL_OBSERVED`, no CI credit, not a pass rate:

- 36 of 36 games finished in both runs, no abort, no timeout.
- Twin runs give the same hash and the same winner in 36 of 36 seeds (`compare run1 run2`:
  `identical 36/36`).
- Winners by seat: seat 1 9, seat 2 0, seat 3 22, seat 4 5 (reference of `889335c38`: 4, 4, 20, 8).
  That is one pod with its own four decks, not a fairness measure.
- Decisions per game 1844 to 5680, median 2775.0, mean 2988.6 (before: 1847 to 4054, median 2639.0).
- Speed is not a claim of this note: the runs were taken one after the other, not interleaved.

## 3. Worker count

The two reference runs used `--workers 2`, because the rule for this work allows at most two bridge
JVMs at once; the documented command uses four. A third run with `--workers 4` on the branch head
`9712f39d3` (the tree that became `82d781ef3`) gives the same hash in 36 of 36 seeds
(`compare real36_main_5bd29ab6f_run1.json real36_workers4_9712f39d3_run1.json`: `identical 36/36`), file
`docs/performance/measurements-2026-11-08/real36_workers4_9712f39d3_run1.json`, 36 of 36 games
finished. Together with the earlier note this is evidence that the hash does not depend on the
worker count for the current pilot on these 36 seeds; it is not a proof for other seeds. The elapsed
times (415.0 s and 458.8 s with two workers, 263.1 s with four) are not a speed claim: `compare`
prints its note for different worker counts.

## 4. Use

At an engine change that is meant to keep the games, run the same command with the new jar and
compare:

```bash
python scripts/benchmark_xmage_full_games.py compare \
    docs/performance/measurements-2026-11-08/real36_main_5bd29ab6f_run1.json after.json
```

`identical 36/36` is the identity gate. The reference holds only while the watched paths and the
pin are those above (`check-reference` prints which of them changed): a change to any of them moves
hashes on purpose, and then the gate is the comparison of the run before and after that change.
