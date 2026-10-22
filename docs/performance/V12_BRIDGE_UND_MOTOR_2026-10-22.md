# Repin v12: order of collections, stable bridge lists, and one lever dropped (2026-10-22)

Scope: make equal seeds replay equal games in more pods without changing a game that was
already stable, take the bridge's random list order out of the pilot's requests, and measure
the one speed lever of the package (T-1) before it ships. Everything here that touches the
engine or the bridge goes through the repin process (requalification, AF11, two seals).

Measured on a 4-core, 16 GB container, JDK 21. Baseline `bridge_v11.jar` = fork pin
`456b0e22` plus the Lab bridge of main `cd95f2ad2`; candidate = fork head `4da83f62679` plus
the same bridge with D-3. Lab pilot of main `cd95f2ad2` for every run, so no pilot change
enters the comparison (the pilot fixes of #967 are outside this table).

## 1. What is in the package

| Part | Where | What changes | Why |
|---|---|---|---|
| Token creation order (mage#68) | fork | `CreateTokenEvent` keeps `LinkedHashMap`, `TokenImpl` a `LinkedHashSet` | tokens carry no `hashCode`; the two Wurms of Wurmcoil Engine were made in identity-hash order |
| Insertion-order collections (mage#70) | fork | `CreatedTokensEvent`, `ContinuousEffects` (requirement and restriction effects, as-though approvers), `ManaType` sets as `EnumSet`, four cards that move a set of cards together | same family: objects without `hashCode` decided an order a player sees |
| Player order in 18 cards (mage#69) | fork | `LinkedHashMap`/`LinkedHashSet` in Wave of Vitriol, From the Ashes and sixteen more | `HashMap<Player,…>` hashes by the per-game random player id |
| D-3, stable lists | bridge | `players[].command`, `players[].exile`, `commander_status` and `commander_damage_to_player` are sorted by content, not by random UUID | the pilot saw these lists in a new order in every game |
| E1, serial collector | PB-03 launch | `-XX:+UseSerialGC` in the launch plan | -12 % wall, -20 % CPU, 12 of 12 hashes identical on the real pod |
| T-1, direct mana payment | bridge | **dropped**, see section 3 | gain below the 3 % bar |

## 2. Result

Final jar = fork head `4da83f62679` plus the bridge with D-3, built once and used for every
row below (sha256 `a9f4b086d9f9...`). All rows are LOCAL_OBSERVED: no CI-level credit.

| Check | `bridge_v11.jar` | Final jar |
|---|---|---|
| 46 precon pods, plan seed 1, game seed 1 | 46 of 46 ok | 46 of 46 ok, **46 of 46 hashes equal to v11** |
| 36 real-pod seeds (1-36) | 36 of 36 ok | 36 of 36 ok, **36 of 36 hashes equal to v11** |
| Seed 22 pod 004 (Wurmcoil Engine), plain games | two hashes in 16 games (7 and 9) | **one hash in 27 of 27 games** (`1a74a441`, 4671 decisions) |
| Plan seed 24 pod 030, 4 games | two hashes (`fb442187`, `4eb6ff64`) | one hash (`e0e1eeb7`, 4815 decisions) |
| Plan seed 27 pod 028, 4 games | two hashes (`b1de6b39`, `c6be761f`) | one hash (`dc98496a`, 6683 decisions) |
| Plan seed 30 pod 005, 4 games | two hashes (`17beb629`, `580e89b1`) | one hash (`2aba23dd`, 4311 decisions) |
| Plan seed 30 pod 036, 4 games | two hashes (`f97c048f`, `427cd41e`) | one hash (`502cc6be`, 2056 decisions) |

The v11 column of the four plan-seed pods comes from `determinism_probe.py locate`, which stops
at the first run that differs: two hashes are what one pair of runs gave, not a count. The four
pods now give one hash each. Their hash changes once with the repin; the hash of a stable pod
stays. Seed 27 pod 028 and seed 30 pod 036 give the hashes Muse measured on the collective
patch jar; seed 24 pod 030 and seed 30 pod 005 give other ones. Muse ran an older Lab pilot
(hypothesis: the pilot fixes of #967 change decisions in those two games); within the final
jar every run of every pod agrees.

Speed is not a claim of this table: the sweeps ran one after the other and not interleaved
(46 pods: 219 CPU-s against 232 on v11; 36 seeds: 239 CPU-s against 281), so they carry the
state of the container at that hour. The only interleaved measurement is T-1 in section 3.

## 3. T-1: direct mana payment path, measured and dropped

`playManaFrame` runs the whole playable calculation (every spell and ability of every zone,
each checked in an engine copy) for every mana payment to read two things from it: the mana
abilities the player may activate and the mana available. T-1 collected the mana abilities of
the active permanents directly (`getUseableManaAbilities`) and read the available mana without
the list, keeping the full calculation whenever any card had a mana ability outside the
battlefield (including one an effect grants to a card in hand or graveyard), and in
simulation copies. A verification mode ran both paths on every payment and failed the game on
a difference.

Correctness held: the verification run (both paths on every payment) gave no mismatch in 46
of 46 precon pods, and 46 pods and 36 seeds gave the hashes of v11. The speed did not:

| Same engine, 6 seeds, one worker, serial GC, order ABBA | Wall total | CPU per game |
|---|---:|---:|
| without T-1, cold start (not counted) | 216.1 s | 44.7 s |
| with T-1 | 175.1 s | 35.7 s |
| with T-1 | 168.7 s | 34.4 s |
| without T-1 | 175.6 s | 35.3 s |

With T-1 the two runs average 171.9 s against 175.6 s without (-2 %), CPU 35.1 s against
35.3 s (-0.6 %). Within noise, under the 3 % bar the roadmap set. Payment frames are a small
part of the playable calculations: the priority decisions compute the list anyway. The change
was committed, measured and reverted (`1db6ed3e7`, `01a990709`); the code and its verification
mode are in that history if a future profile finds payments to be dearer.

## 4. D-3 and the probe

Before D-3 the probe had to sort four lists before comparing requests (`KNOWN_ORDER_NOISE`),
because `commander_status`, `commander_damage_to_player`, `players[].command` and
`players[].exile` came in a random order. With D-3 the bridge sorts them
(`XmageFullGameStateRedactor`; `XmageFullGameViewOrderTest` plays eight partner-commander
games and compares the lists) and the probe's `--raw-order` run finds nothing to normalise:

| Seed (real pod) | Decisions | v11 jar: requests that differ between two runs | Final jar |
|---|---:|---:|---:|
| 1 | 4095 | 1060 (`commander_damage_to_player` order, 833 of them also the totals) | **0** |
| 2 | 2436 | 312 (`players[].command` order 250, `players[].exile` 35, `commander_damage_to_player` 62) | **0** |

On both jars the answers of the pilot differ in no decision and the semantic hash is equal
(`45556bdb7c61` and `e3196abea7c5`): the pilot sorts these lists itself, so the old random
order did not change a game. D-3 makes sure that stays true for every future pilot code that
reads the list in order. Run with `scripts/determinism_probe.py locate --real-pod --seed N
--mode none --runs 1 --raw-order`.

## 5. Not claimed

- Three or eight runs of a pod prove stability for that pod, not for every game.
- The 18 cards of mage#69 have no card test; the evidence is the hash stability of the four
  formerly unstable pods and the identity of every stable pod and seed.
- The unclear collections Muse listed (Reins of Power, Retether, Soulflayer, Trazyn, Mantle of
  the Ancients, Dance of the Manse, Lavabrink Floodgates, six enum sets) are untouched: their
  influence on an order cannot be decided from the source.
- Speed: the package changes no speed except E1, whose gain on PB-03 is measured by the
  PB-03 run of the repin and reported with the seal.
