# Determinism probe: where two games of one seed part ways (2026-10-22)

The same seed must give the same semantic hash. When it does not, the hash only says that
something differs. `scripts/determinism_probe.py` plays one pod more than once, optionally with
the JVM's identity hash function replaced, and names the first request on which the games
disagree, with the earlier decisions around it. It needs a bridge jar and nothing else; the
comparison itself is plain Python and has JVM-free tests (`tests/unit/test_determinism_probe.py`).

## What it found on the pinned engine (2026-10-22)

Pin `456b0e22` (v11), bridge jar `daa6e2bb…1ee3`, JDK 21, 4 vCPUs, one game per JVM.

| Question | Result |
|---|---|
| Real pod, seeds 1-8, `-XX:hashCode` 0-4 (semantic hash) | 40 of 40 identical to the standard game |
| Precon plan 1/1, 46 pods (12 per JVM), modes 2 and 0 | 0 of 46 deviating in either mode |
| Probe on the real pod, 4 perturbed games (seeds 1-3, modes 0 and 2), 14 724 decisions | same hash, 0 different answers; seed 1 under mode 2: 0 of 4095 requests differ once the four lists below are sorted |
| **Seed 22, pod 004** (`2018_nature_s_vengeance`, `2018_built_from_scratch`, `2020_arcane_maelstrom`, `2016_breed_lethality`), 16 plain games on v11, no perturbation | **two hashes: `1a74a441…` 7 times, `9605145d…` 9 times** (default GC 4 and 6 games, serial GC 3 and 3) |
| The same pod on the v12 candidate (token creation order, mage#68), 8 plain games | `1a74a441…` 8 of 8 (the probability of that under the v11 mix is about 0.1 %) |

So the instability of seed 22 pod 004 is not caused by a perturbation and not tied to a
machine: two consecutive plain games on one machine give different transcripts. In the pairs
examined, the two Phyrexian Wurm tokens of Wurmcoil Engine have exchanged `deathtouch` and
`lifelink` from turn 54 on, and the answers part at a block declaration at turn 61
(`CreateTokenEvent.tokens` is a `HashMap`, `TokenImpl.putOntoBattlefieldHelper` a `HashSet`,
and a token has no `hashCode`; the iteration order follows the identity hash, which HotSpot
draws from a per-thread xorshift whose start depends on thread creation order and timing).
Details: `fork-fixes-2026-10-21/DETERMINISMUS_TOKENREIHENFOLGE.md` in the project files.

`-XX:hashCode=0` is therefore a weak trigger: it draws from one generator that all threads
share, so it gave the second hash in 4 of 5 runs against 9 of 16 plain games, and not every time. Repeat plain games
(`--mode none --runs N`) when you look for run-to-run instability, and perturb when you look for
a dependency on iteration order.

### Lists that come in a random order

Between two plain games the bridge sends some lists in another order although the game is the
same: `commander_status` (sorted by the random UUID string of the commander),
`commander_damage_to_player`, `players[].command` and `players[].exile` are filled from
UUID-keyed collections. In every game above the pilot's answers did not depend on it, and the
probe sorts these lists by their naming field before it compares (`KNOWN_ORDER_NOISE`; switch
off with `--raw-order`). Every other list keeps its order: a changed battlefield order is
reported. That the pilot is order-insensitive for these four lists is observed, not enforced;
a stable order from the bridge is a candidate for the next bridge change.

## Use

```bash
# is a pod stable? play it, then again, until two games differ (stops at the first difference)
python scripts/determinism_probe.py locate --jar bridge.jar --seed 22 --mode none --runs 6 \
    --decks 2018_nature_s_vengeance 2018_built_from_scratch 2020_arcane_maelstrom 2016_breed_lethality

# does the identity-hash order change the game?  mode 2 (constant) is repeatable, 0 is not
python scripts/determinism_probe.py locate --jar bridge.jar --real-pod --seed 1 --mode 2

# separate order noise from an effect of the perturbation (plays the standard game twice)
python scripts/determinism_probe.py locate --jar bridge.jar --real-pod --seed 1 --mode 0 --baseline

# keep a game's normalised requests and compare dumps from two machines
python scripts/determinism_probe.py play --jar bridge.jar --real-pod --seed 1 --out a.jsonl.gz
python scripts/determinism_probe.py compare a.jsonl.gz b.jsonl.gz
```

`--decks` takes four names from `data/decks/precons`; the pod and the seed of a sweep row are in
its report. `--fast` adds the serial GC (and the archive when `<jar>.jsa` exists) to both games.
A game takes about as long as in a sweep; `--runs N` can play N more.

## Reading the result

Requests and answers are compared with every process-local id (UUIDs, 64-hex hashes, the
`[abc]` fragments in prompts, state references) replaced by counters in order of first
appearance, so a relabelled copy of a game is the same game.

| Verdict | Exit | Meaning |
|---|---:|---|
| `IDENTICAL` | 0 | same requests, same answers (and, in `locate`, the same hash) |
| `REQUESTS_DIFFER_ANSWERS_SAME` | 2 | the pilot saw a list in another order or form but chose the same everywhere: a latent order dependency, not a changed game. With `--baseline` the pattern list says which differences two plain games also show. |
| `ANSWERS_DIFFER` | 1 | the games part at `first answer difference`; the cause is at or before the first request difference, usually a few decisions earlier. A different semantic hash or length also exits 1. |

`kinds of request difference` counts the decisions per path pattern (list positions folded to
`[]`): a long list of one pattern is a collection that comes in another order, a short list of
`battlefield[].abilities[]` or `object_id` is an object whose identity changed.

## When a hash differs

1. Run `locate` on the pod (and seed) of the differing row, plain first (`--mode none`), then
   perturbed. Note the first answer difference and the objects named there.
2. Find the collection: iteration over a `HashSet`/`HashMap` whose keys have no `hashCode`
   (a token, permanent, ability, effect) or a collection keyed by a random UUID.
3. Repair with a `LinkedHashSet`/`LinkedHashMap` or a sorted list, and add an order test against
   many fresh events (pattern: `CreateTokenEventOrderTest`).
4. Prove it: at least 8 plain games with one hash (the pod 004 numbers above show that three
   games prove nothing), the perturbed modes, then the 36-seed acceptance of the repin process.

## Limits

- Identical under modes 0 and 2 is not proof: a card that never entered play cannot show. Run
  the probe over many pods and seeds, and treat every hash difference of a perturbed sweep
  (`precon_sweep_compare.py`) as a case for `locate`.
- `Set.of`/`Map.of` iterate in an order salted from the clock; no JVM switch controls it, only a
  source search finds them.
- `-XX:hashCode` is experimental and slows a game (+14-18 % CPU; mode 2 about +30 % wall on the
  real pod). It is a probe, never a production option.
- The probe compares what the pilot was asked and answered. A difference that never reaches the
  pilot and never changes an answer shows only in the semantic hash.
