# Batched play (`--games-per-jvm`): qualification on the v12 pin (2026-10-22)

Stage 1 of T-2/E2 in #961: tests first. Tooling only (a script, its unit tests and an
on-demand workflow); no bridge, fork, pin or sealed record changes, so nothing here needs
requalification. Batched games stay measurements and never evidence (Owner decision
2026-10-15); PB-03, the mid-game lanes and the evidence lanes keep one game per JVM.

Measured on a 4-core, 16 GB container, JDK 21.0.12, bridge jar built from the fork at pin
`4da83f62` (XMage 1.4.62, v12; jar sha256 `bcc607a2…ee45`), lab main `0b3abed` plus this
change. Raw data: `docs/performance/measurements-2026-10-22/`.

## 1. Result

| Property | What was played | Verdict |
|---|---|---|
| Reference | 8 games, each alone in its own JVM with the evidence-lane launch, twice | **PASS**: 8/8 reproduce, 8 different hashes |
| Positions | 8 cyclic rotations of the 8-game pool: every game at every position 0-7 | **PASS**: 64/64 identical to the reference |
| Permutations | reverse, 2 shuffles, chunks of 3 and of 5, a game 3 times in a row (2 games) | **PASS**: 46/46 identical |
| Isolation | a failing game at the first, middle and last place of a 3-game batch: unknown card, SIGKILL, SIGSTOP | **PASS**: 9/9 failed as planned, the 18 other games identical |
| Memory | 56 games in one JVM (the pool 7 times, a new order each pass) | **FAIL**, with a known cause (section 4): all 56 hashes identical, but the live set grows 1.6 MiB per game |

**184 comparisons with a single-game hash, 0 differences.** Batching, the launch flags of the
sweeps (serial GC, AppCDS) and the position or neighbours of a game in a JVM do not change a
game, up to position 56 of one JVM. The one FAIL is a leak in the bridge that only costs
memory: 330 MiB of live set and 1.31 GiB RSS at game 56, against a default maximum heap of
4 GiB. It is harmless at the batch sizes in use (4 to 18 games) and unbounded in the number
of games, so the script reports it as a failure and does not widen its criterion to pass.

`python scripts/qualify_game_batching.py verdict
docs/performance/measurements-2026-10-22/batching-qualification-v12.json` prints this table from
the raw rows, without a JVM; it exits 1 while the memory property fails.

## 2. Method

`scripts/qualify_game_batching.py` (tests: `tests/unit/test_qualify_game_batching.py`).

- **Pool**: 8 games over 5 pods, `real:1`, `real:2`, `real:3` (the real 4P pod, three seeds)
  and `coverage-0..4:1` (five pods of the owner-collection coverage decks). Pods differ, so a
  deck or card state that one game leaves behind has something to disturb in the next.
  The reference hashes are pairwise different; a swap of two games' results is therefore
  visible, and the script refuses a pool where it would not be.
- **Reference**: every pool game alone in its own JVM through `XmageFullGameRunner.run`, the
  evidence-lane path, with no extra launch flags, played twice. A game whose two runs differ
  is a determinism defect, not a batching finding, and fails the reference.
- **Batched runs**: `run_batch` with `-Dcommanderlab.fullGame.gamesPerJvm=<batch size>` and the
  sweep flags (`--fast`: serial GC and the jar's AppCDS archive). So the claim covers batching
  and the flags together.
- **Compared**: the semantic transcript SHA-256 of each game, as in every speed change before.
  A game that failed is never identical. A hash that differs is a FAIL and is never played
  again; a game lost to infrastructure (a timeout under load) is INCONCLUSIVE and is played
  again with `--resume`. A property is PASS only if every planned game was played, compared and
  identical; missing, unplayed or unsampled data is never PASS.
- **Instruments** hook the requests of the runner (`_RawFullGameClient.request`) from outside;
  runner, pilots and bridge are unchanged. A fault hook signals the bridge JVM of one game of a
  batch once, at its 400th answered decision. A memory hook reads `VmRSS` and `VmHWM` from
  `/proc` and the live set from `jcmd GC.run` plus `GC.heap_info` at every game start (the
  previous game is released by then) and every game end.
- **Memory criteria**, fixed in the script before the first measurement and not changed
  since: after a warm-up pass, the least-squares slope of the live set at game start is at most
  1.0 MiB per game, the last pass's mean live set is at most 1.10 times the first judged
  pass's plus 16 MiB, and the RSS peak is at most 3 GiB; at least 50 games in one JVM.

The plan is 209 games: 16 reference, 64 positions, 46 permutations, 56 memory, 27 isolation.
Four batches ran side by side; the 56-game batch took 66 minutes under that load, the whole
run about 80 minutes.

## 3. Results

### Reference

| Game | Semantic hash | Decisions |
|---|---|---:|
| `real:1` | `45556bdb7c61…` | 4095 |
| `real:2` | `e3196abea7c5…` | 2436 |
| `real:3` | `cfae05a4388f…` | 4098 |
| `coverage-0:1` | `8be25d699329…` | 3963 |
| `coverage-1:1` | `ae27d5f9f05c…` | 5882 |
| `coverage-2:1` | `26056277f79a…` | 3250 |
| `coverage-3:1` | `6f2b0184da5e…` | 2572 |
| `coverage-4:1` | `ea27cc431ad5…` | 2613 |

### Positions and permutations

All 64 rotation rows and all 46 permutation rows equal their reference hash. The 56-game memory
batch adds 56 more rows at positions 1 to 56, among them every game seven times and games that
follow themselves directly: all identical. The chunk batches also show that the value of the
property (3, 5, 8, 56) does not matter.

### Isolation

| Failure | at the first | in the middle | at the last place |
|---|---|---|---|
| Deck with an unknown card (`BRIDGE_ERROR`) | game failed, 2 neighbours identical | same | same |
| JVM killed by SIGKILL at decision 400 (`BRIDGE_CLOSED`) | same | same | same |
| JVM stopped by SIGSTOP, the runner times out (`BRIDGE_TIMEOUT`) | same | same | same |

For the killed and stopped JVM the finished games before the failure are played again alone
(their result cannot rest on a graceful shutdown) and the games after it start in a fresh JVM;
all of them have their single-game hash. A fault that does not fire (the game ended before
decision 400) is INCONCLUSIVE, not a pass.

### Memory

Live set at game start, mean per pass of 8 games (MiB), RSS at the end in GiB:

| Pass | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bridge as pinned (56 games) | 251.6 | 266.4 | 282.7 | 300.5 | 314.4 | 324.5 | 328.9 |
| With the deck release of section 4 (32 games) | 138.3 | 148.0 | 153.9 | 146.8 | | | |

Without the release the slope after warm-up is +1.63 MiB per game (limit 1.0), the last pass
holds 329 MiB against 266 in the first judged pass (limit 309), and RSS reaches 1.31 GiB
(limit 3 GiB). Metaspace grows from 8.6 to 16.9 MiB in the first 40 games and is flat after that.

## 4. The memory finding: decks of finished games are never released

`XmageDeckImporter.decksByHandle` (and `requestsByHandle`) keep every imported `Deck` under a
random handle for the life of the JVM. `create_full_game` already releases the previous
game's static records (`releaseStaticGameRecords`) but not the decks it was built from. In a
one-game JVM that is invisible; in a batch every game leaves its four decks behind.

Evidence that this, and nothing else, is the growth:

- **Probe**: the real pod's four decks imported 40 times into one JVM without playing: the
  live set grows 2.06 MiB per set of four decks, linearly (151.8 MiB after 10 sets, 213.7 after
  40).
- **Release applied** (`measurements-2026-10-22/bridge-release-decks.patch`, a `forget`
  method on the importer, one field and one call in the bridge, and a test with a negative control: without the release the test sees 4 decks
  where it expects 2): the same 32-game batch has a live-set slope of -0.10 MiB per game, a
  flat 138-154 MiB, RSS 0.98 GiB peak, and all 32 hashes equal the hashes of the unpatched
  56-game run. That run is `batching-memory-with-deck-release.json`; it carries no reference
  games of its own, so its stored verdict reads INCONCLUSIVE, and the hash comparison above
  was done against the 56-game run.

The patch is not applied here. It changes the bridge, so it needs PB-03, the AF11 decision, a
seal and a new `current_qualification` epoch, which is not worth doing for 2 MiB per game
alone (same rule as stage 2 of the efficiency offensive); it belongs in the next bridge
change (#975). Until then the memory property fails on purpose, and the on-demand workflow below
will show it red; after the release it passes without a change to the criteria.

## 5. What this does not show

- One pin, one jar, one machine, JDK 21. The workflow below repeats it on the CI runner's JDK
  17 with the pin from `config/rules_engines.json`; run it after every repin or bridge change.
- Eight games over five pods. Other cards can leave other state behind; a difference would show
  as a changed hash in a sweep that is compared with `benchmark_xmage_full_games.py compare`.
- Semantic transcripts, not bit-exact replay (as for every comparison in this repository).
- Faults at decision 400 of a 3-game batch; a fault inside the shutdown handshake or the very
  first request of a JVM is not planned.
- Nothing about evidence lanes: they still never set the property
  (`test_only_known_files_can_batch_games` lists the callers; this script is one of them).

A first live run found a defect in the qualification itself: the fault hook counted
`get_full_game_decision`, which the runner sends once per wait for the engine, not per answered
decision, so no fault fired. The verdict said INCONCLUSIVE and not PASS, the hook now counts
`submit_full_game_decision` (a test reads the runner's source for it), and only the six fault
batches were played again.

## 6. Use

```bash
python scripts/build_xmage_cds_archive.py --jar bridge.jar     # once per jar
python scripts/qualify_game_batching.py run --jar bridge.jar --out report.json --fast --workers 4
python scripts/qualify_game_batching.py run --jar bridge.jar --out report.json --fast --resume
python scripts/qualify_game_batching.py verdict report.json
```

- `--resume` plays only batches that infrastructure got in the way of (a timeout, a fault that
  did not fire). `--only memory` (also `reference`, `positions`, `permutations`, `isolation`)
  and `--memory-passes N` run a part or a shorter memory batch.
- Run it on a machine that is otherwise idle: four JVMs on four cores leave no room for
  anything else, and a starved engine turns into timeouts.
- The workflow `Batching Qualification` (`workflow_dispatch` only, never a gate) builds the
  pinned engine, the bridge and the AppCDS archive and runs the same script, then uploads the
  report. About 90 minutes, more when the engine build is not cached.

## 7. Recommendation

Batching in the sweep, comparison and pilot-measurement lanes rests on tested ground: keep
`--games-per-jvm` as it is (games divided by workers; up to 56 games per JVM are qualified),
keep every evidence lane at one game per JVM, and bundle the deck release of section 4 with the
next bridge change, after which the memory property passes. Whether to also use batching
somewhere that is not a measurement stays the Owner's decision.
