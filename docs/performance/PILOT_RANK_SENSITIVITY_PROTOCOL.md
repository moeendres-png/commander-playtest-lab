# Does the pilot reorder the decks? Protocol and tool (S-1 of #961)

The question behind F3 (a one-step search that improves a deck): if the ranking of decks by win
share depends on which pilot plays them, a search over card swaps optimises the pilot as much
as the deck, and its result is only as good as the pilot. S-1 turns that from `UNKNOWN` into a
number. This note fixes the design and the verdicts before any game is played, and calibrates the
test on simulated games. Section 6 holds the first measurement.

Tool: `scripts/rank_sensitivity.py` (`play` and `analyze`), tests in
`tests/unit/test_rank_sensitivity.py` (20 tests; the reversal condition, the Holm adjustment, the
pairing of blocks, the resolution check and the draw credit each make a test fail when mutated).

## 1. Design

- **Pods.** A pod is four decks. Every deck sits in every seat once (four cyclic rotations), so a
  deck's win share does not carry the seat advantage.
- **Blocks.** A block is one pod at one seed (its four rotations). Blocks are the unit that is
  paired between variants and the unit that is resampled: the rotations of one seed share a
  shuffle and are not independent.
- **Seeds.** At least 40 per pod from a master seed (`hash:MASTER:N`, as in the comparison
  protocol, so the seeds are not 1..N). Every variant plays the same seeds.
- **Variants.** A variant is a checkout of the lab. `play` uses the pilot of the checkout it runs
  from; run it once per variant from a git worktree of that commit, with the same bridge jar,
  pods and seeds. A game without a winner counts as played with no credit; a failed game stays in
  the table and makes `play` exit non-zero. `analyze` keeps only blocks whose four rotations
  finished in every variant (a block with a failed seat would average fewer than four seats and
  let the seat advantage into the deck shares of the variant that fails more often) and prints
  how many blocks were played, kept and dropped. A variant that fails in many blocks is reported
  as such; its comparison then rests on the blocks that survive.
- **Win share.** Credit per game is 1 for a sole winner, shared if several won, 0 for no winner.
  A deck's share is its mean credit over the blocks.

## 2. Statistic and verdicts

For every pair of decks (i, j) of a pod the paired change of "share i minus share j" between two
variants is tested with a sign-flip test over the blocks (2000 flips), Holm-adjusted over the six
pairs of the pod. A **reversal** is a pair that stands in the opposite order in the two variants
and passes that test at 5 %. Kendall's tau-b between the two rankings (averaged over the pods) is
reported as the summary figure, not as the test: with four decks tau takes a handful of values and
cannot tell a swap of two neighbours from chance (a first design on tau alone found a middle swap
in 6 of 40 simulated cases at 40 seeds; the pair test finds 51 of 60).

| Verdict | Rule |
|---|---|
| `RANK_SENSITIVE` | at least one reversal |
| `NOT_DETECTED` | no reversal, and both variants reproduce their own ranking (mean tau between two random halves of the same variant's blocks at least 0.5) |
| `UNRESOLVED` | no reversal, and a variant's own halves disagree: the decks are too close for this many seeds, the sensitivity stays unknown |
| `TOO_FEW_BLOCKS` | fewer than 20 paired blocks in a pod |

`NOT_DETECTED` is absence of evidence at this n, never "the ranking is stable". A shift in
strength that keeps the order is not a reversal; the per-deck table says which decks moved.

## 3. Calibration on simulated games

Four decks, one winner per game drawn in proportion to a fixed strength per deck, 4 rotations,
40 seeds unless noted, 60 to 150 replications per row (`rank_sensitivity` verdicts counted).
These show how the test behaves, not how the pilots behave.

| Case | Replications | RANK_SENSITIVE | NOT_DETECTED | UNRESOLVED |
|---|---:|---:|---:|---:|
| Same variant twice, strengths .45/.30/.15/.10 | 150 | 1 | 148 | 1 |
| Same variant twice, close strengths .32/.28/.22/.18 | 150 | 2 | 37 | 111 |
| Middle pair swaps (.30 and .15), 40 seeds | 60 | 51 | 9 | 0 |
| Middle pair swaps, 80 seeds | 60 | 60 | 0 | 0 |
| Ends swap in a close pod (.32 and .18), 40 seeds | 60 | 41 | 1 | 18 |
| Ends swap in a close pod, 80 seeds | 60 | 59 | 0 | 1 |

- False positives on identical variants: 3 of 300 (1 %), below the 5 % level, because a reversal
  needs both the opposite order and the Holm-adjusted test.
- **A pod of close decks cannot be ranked with 40 seeds**: 111 of 150 identical-variant pairs are
  `UNRESOLVED`. Real precon pods are close; expect `UNRESOLVED` at 40 seeds and plan 80 or more
  per pod if the first run says so. A swap of two decks 14 points apart is found in two thirds
  of cases at 40 seeds and in all but one at 80.

## 4. Running it

```
git worktree add ../lab-variant-a <commit-a>   # likewise for every variant
cd ../lab-variant-a
python3 scripts/rank_sensitivity.py play --jar <bridge.jar> --variant a --out games-a.json \
    --pod deck1.json,deck2.json,deck3.json,deck4.json --seeds hash:s1-pods:80 \
    --workers 4 --games-per-jvm 6 --jvm-option=-XX:+UseSerialGC
python3 scripts/rank_sensitivity.py analyze games-a.json games-b.json --json result.json
```

Batched play (`--games-per-jvm`) is a measurement lane and fine here: the verdict uses winners,
not evidence. Cost: about 1 CPU-minute per game; 40 seeds x 4 rotations x 2 variants x 1 pod is
320 games, roughly 1.3 h on 4 cores. One run at a time (CPU starvation turns slow decisions into
timeouts).

## 6. First measurement (2026-10-23, `LOCAL_OBSERVED`)

Bridge jar `c5c019a2` (pin `4da83f62`, built from the first revision of #977), SerialGC, 6 games
per JVM, 4 workers, one run at a time. Two pods of real precons, 40 seeds each from the master
seeds `s1-pod1` and `s1-pod2` (`hash:`-style, SHA-256), four rotations: 160 games per pod and
variant. Raw tables and the analysis are in `measurements-2026-10-23/s1/`
(`pod1-*` is pod 1; `pod2-*` is pod 2, which the merged `result.json` calls `pod1`).

- Pod 1: 2016 Breed Lethality, 2019 Primal Genesis, 2022 Necron Dynasties, 2022 Buckle Up.
- Pod 2: 2022 Draconic Destruction, 2022 Grave Danger, 2022 Token Triumph, 2022 Urza's Iron Alliance.
- Variant `a`: the pilot of main (`681f019a`). Variant `d`: the pilot of `d012424b` (2026-10-21,
  before the card-level pilot fixes of #944 to #970). Both ran from a git worktree with the same
  jar. `d`'s `config/rules_engines.json` pin line was set to `4da83f62` in the worktree so that
  the handshake accepts the jar; nothing else of `d` was changed.
- A third variant (the pilot of 2026-10-17, after the mulligan and bottoming changes, before the
  card-level fixes) was planned. It could not be played with batching (its report tool has no
  batch entry point) and failed one game in four unbatched, so it is not part of this result.

| | Pod 1 | Pod 2 |
|---|---:|---:|
| Games not played to the end, `a` / `d` | 0 / 8 | 0 / 0 |
| Games with the same semantic hash in `a` and `d` (both finished) | 19 of 152 | 159 of 160 |
| Complete blocks compared (of 40) | 33 | 40 |
| Kendall tau-b, `a` against `d` | 1.0 | 1.0 |
| Reversed pairs (Holm-adjusted sign-flip test, 5 %) | 0 | 0 |
| Split-half tau, `a` / `d` | (merged: 0.90 / 0.91) | |
| Verdict | `NOT_DETECTED` | `NOT_DETECTED` |

The eight failed games of `d` are all `ENGINE_FAILURE (XMAGE_ACTION_EXECUTION_FAILED)`: the older
pilot offers an action the engine rejects; main's pilot had none in 320 games. They cost seven
blocks, which `analyze` dropped from both variants.

What the numbers allow:

- **Pod 1** is a real test: the two pilots played 133 of 152 finished games differently, and the
  win shares moved by at most 2.3 points (Breed Lethality 0.462 to 0.485, Primal Genesis 0.349 to
  0.341, Necron Dynasties 0.152 to 0.152, Buckle Up 0.030 to 0.023). The order stayed. The decks
  are far apart (0.46, 0.35, 0.15, 0.03), so the order is easy to keep: the top two decks are 11 points apart, and only a shift of
  that size between them would reverse them.
- **Pod 2 says nothing about the pilots**: they played the same game in 159 of 160 cases, because
  the card-level fixes between `d` and `a` touch cards this pod does not play. `NOT_DETECTED`
  there only repeats that the games were identical.
- **Not tested**: a larger change of the pilot (mulligan, bottoming and stack policy together),
  pods of close decks, other seeds. The question behind F3 stays open for those; this result
  gives no reason to expect a reversal from card-level pilot fixes on decks that are far apart,
  and no evidence either way for larger pilot changes.
- A bug found by the first real table: the engine numbers seats from 1 and the first version of
  `play` stored those numbers as indexes (`IndexError` in `analyze`). `play` now stores indexes,
  `analyze` refuses an index outside the seats, and the tables in `measurements-2026-10-23/s1/`
  hold indexes (the pod 1 tables and the `d` table of pod 2 were converted after the run, by
  subtracting 1; the `a` table of pod 2 was written by the fixed tool).

## 5. Not claimed

- Nothing beyond section 6 about the pilots. A result is `LOCAL_OBSERVED` for the
  pods, seeds and variants it names.
- Pods of other decks, other seed sets or other variants may behave differently.
- Win share is the only outcome. Turn of win, life or card metrics are not ranked.
