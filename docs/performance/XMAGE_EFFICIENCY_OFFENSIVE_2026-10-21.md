# XMage efficiency offensive: batching, serial GC and AppCDS for sweeps (2026-10-21)

Scope: make the simulation sweeps (36-seed smoke pods, 46-pod precon sweep) clearly faster
without changing a single game. Stage 1 changes tooling only: no bridge, no fork, no
pin, so nothing here needs requalification. Later stages are listed with their cost in
section 7; none of them is started.

Measured on a 4-core, 16 GB container, JDK 21, bridge jar built from the fork at the live
pin `769e6ebb` (XMage 1.4.62, determinism line), lab main `3171328` plus this change.
The runs are sequential and nothing else was meant to run during one; short lint and unit-test
runs overlapped the 3-worker precon baseline (1126 s), which can only have made it slower.

## 1. Result

| Sweep | Before (best configuration) | After | Games identical |
|---|---:|---:|---:|
| 36 seeds, real pod | 873 s (3 workers; 914 s with 2) | **408 s** (4 workers, 9 games per JVM) | **36/36** |
| 46 precon pods | 1126 s (3 workers; 1268 s with 2) | **592 s** (4 workers, 12 games per JVM) | **46/46** |

That is 2.1x for the 36 seeds and 1.9x for the precon sweep against the best old configuration
(2.1x against the 2-worker run the sweeps used so far).

At the same worker count the saving is smaller, because the wall time of one game does not
shrink much (section 3). The change saves CPU, and CPU is what lets more workers run: with
the old launch the 2-worker sweep already used 3.4 of the 4 cores, and a third worker made it
only 4.5 % (36 seeds) and 11 % (46 pods) faster; the new launch needs 2.3 cores for two workers.

| Same machine, 2 workers | Wall | Process-tree CPU |
|---|---:|---:|
| 36 seeds, one game per JVM, defaults (reference) | 914.5 s | 3072 s |
| 36 seeds, 9 games per JVM, serial GC, AppCDS | 576.2 s (-37 %) | 1325 s (-57 %) |
| 46 pods, one game per JVM, defaults (reference) | 1268.4 s | 4150 s |
| 46 pods, 6 games per JVM, serial GC, AppCDS | 897.0 s (-29 %) | 2246 s (-46 %) |

The evidence lanes (PB-03, gates) keep one game per JVM (Owner decision 2026-10-15). What
they could take without breaking that rule is the launch flags alone: serial GC and AppCDS,
one game per JVM: 914.5 -> 819.3 s (-10 %), CPU 3072 -> 2588 s (-16 %), 36/36 identical.
That is a change of the bridge command string and so of the batch execution identity; it is
the Owner's call and not made here.

## 2. Method

- Reference sets: **R1** = the real 4P pod (`run_real_4p_full_game_smoke` decks), seeds 1-36;
  **R2** = the precon sweep plan (plan seed 1, game seed 1, 46 pods over the 182 importing
  decks). Both through `benchmark_xmage_full_games.py` / `precon_pod_sweep.py`, with a private
  card repository per JVM.
- Identity: the semantic transcript SHA-256 of every game; `benchmark_xmage_full_games.py
  compare before.json after.json` fails on any different hash, any status change and any
  missing game. A failed game is never identical.
- Time: total wall time and CPU of the whole process tree (`getrusage` of the waited-for
  children around the entire run), not the sum of per-game rows: with several workers a
  per-game child CPU counts other games' CPU.
- The reference is deterministic: R1 was run twice (two runs, 36/36 identical hashes, 917.5 s
  and 914.5 s), so a hash difference in a later run is a real difference.

Raw reports and timings: `docs/performance/measurements-2026-10-21/`.

## 3. Where the time goes on the live pin

- **Fixed cost per JVM** about 8 s on an idle machine (JVM start, card repository, deck import,
  game start). The 20 s seen under load is mostly CPU contention.
- **Per decision** about 8 ms; a precon game has about 3,200 decisions.
- **Engine**: about 44 % of the game thread is `GameImpl.createSimulationForPlayableCalc` /
  `GameState.copy`, the simulation copy that `PlayerImpl.getPlayable` and `getManaAvailable`
  make. Removing a copy changes games (section 7), so this part is the floor.
- **Bridge**: about 25 % is JSON: the actor and public views, the state hash (deep copy,
  `toString`, SHA-256) and the main thread's request copy.
- **A cold JVM pays twice**: a game in a fresh JVM costs about 85 CPU-s, the same game in a
  warm JVM about 37 CPU-s. The difference is JIT compilation of the engine, repeated for every
  JVM. That is why batching saves far more CPU than the 8 s fixed cost alone.

## 4. Levers tried

One worker, four games per JVM, CPU per game; the hashes were identical in every row.

Real pod, seeds 1-4:

| Launch | CPU per game | Verdict |
|---|---:|---|
| G1 (default) | 51.5 s | reference |
| Serial GC | 43.1 s (-16 %) | **chosen**: small live set, about 1 GB/s allocation, one collector thread wins |
| Parallel GC | 45.4 s | rejected, serial is better |
| C1 only (`TieredStopAtLevel=1`) | 55.3 s, wall +60 % | rejected |

Four precon pods:

| Launch | CPU per game | Verdict |
|---|---:|---|
| G1 (default) | 51.0 s | reference |
| Serial GC | 45.8 s (-10 %) | **chosen** |
| Serial GC + AppCDS archive | 43.2 s (-6 % more) | **chosen**: the classes are mapped, not loaded |
| Serial GC + transparent huge pages | 43.6 s | not adopted: needs a host setting |
| Serial GC + fixed young generation | 44.0 s | not adopted: machine-specific sizing |

The last two are within 1 CPU-s of the AppCDS row on four games; a larger sample would be
needed before either is worth a flag. `build_xmage_cds_archive.py` now trains with serial GC,
so the archive is trained and used in one configuration, and it maps under serial GC (checked
with `-Xshare:on`).

## 5. Stage 1: what changed (tooling only)

- `scripts/benchmark_xmage_full_games.py`: `--games-per-jvm N` (consecutive games in one bridge
  JVM through `XmageFullGameRunner.run_batch`), `--fast` (serial GC and the jar's `.jsa` archive
  if it exists), `--jvm-option=...`; `compare` also reads sweep files.
- `scripts/precon_pod_sweep.py`: the same options plus `--reverse` (play the pods last to first
  to meet other neighbours than a forward run).
- `scripts/build_xmage_cds_archive.py`: serial GC in training and in the printed command.
- `scripts/check_batch_failure_isolation.py`: plays two batches with one broken game each on the
  real bridge and compares every good game with its single-game hash (section 6).
- Tests: batched rows keep each game's own hash and status, a failed game is a failed row, a
  raising batch fails every game of it, chunking, sweep comparison, fast options; the guard
  `test_only_known_files_can_batch_games` allows the three scripts.

Batching stays measurement-only (Owner decision 2026-10-15): the bridge needs
`-Dcommanderlab.fullGame.gamesPerJvm=N` and the runner shuts each game down before the next.

## 6. Why the games are still the same games: checks

| Check | Result |
|---|---|
| R1, 9 games per JVM, serial GC, AppCDS, 2/3/4 workers | 36/36 identical each |
| R1 and R2 with one game per JVM and 3 workers (the old launch, more load) | 36/36 and 46/46 identical to the 2-worker reference: load does not change a game |
| R1, seeds played 36 -> 1, 5 games per JVM, 2 workers | 36/36 identical |
| R2, 4 workers: 4, 6 and 12 games per JVM; 6 games per JVM with 2 workers | 46/46 identical each |
| R2, pods played last to first, 4 games per JVM | 46/46 identical |
| R1, one game per JVM with the fast flags only | 36/36 identical |
| R1 seeds 1-18 in **one** JVM (18 games) | 18/18 identical; peak RSS 1025 MB, as with 9 games (968 MB): no growth |
| Failure inside a batch: [seed 1, broken deck, seed 2] and [broken deck, seed 3] | the broken game fails (`BRIDGE_ERROR`), the neighbours before and after are identical to their single-game hashes (fresh JVM after the failure) |
| AppCDS in use during a real game (seed 1, serial GC) | 37,022 of 37,730 loaded classes come from the archive (98 %); the hash is that of the run without archive |

Different chunk sizes and orders mean different neighbours in a JVM; state that one game left
behind would show up as a different hash. None did.

### The deck-comparison path end to end

`run_full_game_deck_comparison.py` (baseline against one swap variant, one opponent, seeds 1-6,
both seats, 24 two-player games, 4 workers) with the bridge command from the environment:

| Launch | Wall | Process-tree CPU | Games per hour |
|---|---:|---:|---:|
| one game per JVM, defaults | 286.4 s | 1113 s | 302 |
| 4 games per JVM, defaults | 157.8 s | 535 s | 548 |
| 6 games per JVM, serial GC, AppCDS | **114.0 s** | **400 s** | **758** |

All 24 games have the same semantic transcript hash, decision count and winner in the three
runs (compared by case id). The comparison runner needs no code change: it reads the command
that `build_xmage_cds_archive.py` prints, which now carries serial GC.

## 7. Next stages (not started; each needs the Owner's go as stated)

| Stage | What | Expected | Cost |
|---|---|---:|---|
| 2 | Bridge: shallow copy in `stateHash`, memoise rule text in the views, avoid the request `deepCopy` | 3-5 % (estimate) | bridge change: PB-03, AF11, seal. Not worth a requalification alone; bundle with the next bridge change. |
| 3 | Fork: lazy copy of triggers, watchers and battlefield in `GameState.copy` | 8-15 % (estimate) | fork push, repin, requalification. The copy is where games diverged before (`AddManaChosenColorEffect`, the P1 fast path); only with a 36-seed and a sweep comparison, locally first. |
| 4 | Card-test time: keep the card database, run the tests of a change in one invocation (section 8) | cold 39 s -> 10 s, further tests about 0.25 s each | no code; CI cache or workflow habit of the fork's test job. Owner's call for the fork CI. |

Why stage 3 stays small: the JFR profile of one game (seed 1, 7,614 game-thread samples; 3,306
of them, 43 %, inside `createSimulationForPlayableCalc`) shows no single hot spot in the copy.
It is the object graph: `Battlefield.copy` 31 %, `TriggeredAbilities.copy` 27 %, `Modes`/
`Mode`/`Effects` copies 35 %, `Watchers` 7 %, `ContinuousEffects` 7 % (inclusive shares, they
overlap); leaf time is `HashMap.putVal` 16 %, `Effects.<init>` 12 %, `CardUtil.deepCopyObject`
7 %. Safe micro-changes (presizing the `ArrayList` copies) would save a few percent; presizing
a `HashMap` or `HashSet` changes its iteration order and is exactly what the determinism line
removed. Sharing instead of copying is where earlier attempts diverged.

Removing the second simulation copy (about 24 % faster) was rejected earlier because one game
played differently (`docs/performance/XMAGE_FULL_GAME_SPEED_2026-10-12.md`); that stands.

## 8. Card-test time

One card test through Maven (`mvn -o -pl Mage.Tests test -Dtest=...`, same container, JDK 21):

| Run | Wall |
|---|---:|
| Cold, `Mage.Tests/db` absent (card database is built) | 39.4 s |
| Warm, one test class | 9.9 s |
| Warm, four test classes in one invocation | 10.6 s |

So most of a card test's wall time is not the test: the cold start builds the card database
(about 30 s) and each Maven invocation costs about 9.5 s (Maven, test compilation check,
surefire fork, JVM); a test class itself takes well under a second. A figure around a minute
per card test therefore describes a cold database, one invocation per test, or both. Two habits
remove it, and neither touches code or a game: keep `Mage.Tests/db` between runs (the module's
`maven-clean-plugin` deletes it on `mvn clean`, so avoid `clean` there, or cache that directory
in the test job), and run all card tests of a change in one invocation (`-Dtest=A,B,C`).

## 9. Use

```bash
python scripts/build_xmage_cds_archive.py                  # once per jar build, about 30 s
python scripts/precon_pod_sweep.py --jar JAR --out sweep.json \
    --import-report imports.json --workers 4 --games-per-jvm 12 --fast
python scripts/benchmark_xmage_full_games.py run --jar JAR --out after.json \
    --seeds 1-36 --workers 4 --games-per-jvm 9 --fast
python scripts/benchmark_xmage_full_games.py compare before.json after.json
```

- Pick the chunk size by worker count. A chunk runs whole in one JVM, so the last round decides
  the wall time. 36 seeds at 4 workers: 9 games per JVM, 408 s (one round); at 3 workers the
  fourth chunk runs alone and 583 s is no better than 576 s at 2. 46 pods at 4 workers: 4 per
  JVM 700 s, 6 per JVM 680 s, 12 per JVM 592 s (four JVMs, CPU 1984 s against 2529 s with 4 per
  JVM). Each extra JVM costs a JIT warm-up: 36 seeds took 1325 CPU-s with 4 JVMs and 1636 s with 8
  (batch 5, seeds reversed), about 80 CPU-s per extra JVM. A good default is games / workers.
- Run one sweep at a time on a machine: CPU contention turns slow decisions into
  `DECISION_ADVANCE_TIMEOUT` rows, and four workers on four cores leave no room for another
  sweep.
- A new jar needs a new archive. Without it `--fast` still uses serial GC and the JVM runs at
  normal class-loading speed.
- Chunk starts can collide on the card repository (`XMAGE_CARD_REPOSITORY_INIT_FAILED`, H2 "Lock
  file recently modified", #731, #878). Over twelve 36-seed sweeps that followed one another, 9 of
  48 chunk starts failed their first game this way (also with the unmodified pin jar), which looked
  like a game failure (and in a pod sweep as a pod that is green when played alone). `run_batch` now
  starts such a first game again in a fresh process, up to four times with the back-off of the batch
  runner; any other failure, and a collision after the first game, stays a failed game.
