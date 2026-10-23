# Upstream delta check (U-1): what magefree/mage gained since the last merge (2026-10-23)

U-1 of #961. Tooling and a measurement only: a script, its unit tests and one dated result.
No bridge, fork, pin or sealed record changes, so nothing here needs requalification. The check
measures; a repin or an upstream merge needs the Owner's go and the requalification chain of
`docs/claude/REPIN_RUNBOOK.md`.

## 1. What it does

```
git -C ~/mage fetch upstream
python3 scripts/upstream_delta.py --fork-checkout ~/mage \
    --out docs/performance/measurements-2026-10-23/upstream-delta.json
```

It works on the object database of the fork checkout (no build, no working tree, about 6 s):

| Question | How |
|---|---|
| What does the pin lack, by area | `git log --name-only` from the merge base, each commit classed engine / card / set / test / verify / data / ci |
| Which card classes changed, which names, which precon decks | `git diff --name-status` on `Mage.Sets/src/mage/cards`, names from the `SetCardInfo` registrations, decks from `data/decks/precons`; owner collection as a count only |
| Does a merge conflict | `git merge-tree --write-tree`, nothing is written |
| Determinism hazards | added lines in `Mage/src/main` and the card classes that match `RandomUtil`, `new Random`, `Math.random`, `Collections.shuffle` (RNG) or `new HashSet`, `new HashMap`, `toSet()` (unordered), with the precon decks of the card |
| Core signatures changed or removed | removed member declarations in `Mage/src/main` whose name and parameter types are not among the added ones, then the files the fork changed (and `engine-bridge/src`) that still mention the name |
| Cards the pin lacks | every precon card without a `SetCardInfo` registration at the pin (accents folded, split and double-faced cards by front face); or the list of a `measure_precon_imports.py` report with `--import-report`; upstream's registrations tell which are gained |
| Upstream PR status of missing cards | optional `--pull-requests-json` (`{"<card>": {"number": N, "state": "open"}}`); not queried by the script |
| The repin triggers T1-T6 of the roadmap | `MET` / `NOT_MET` where measurable, `REVIEW` where the listed items need a human read, `OWNER` for T4 |

## 2. Result on 2026-10-23

Upstream `c74ac92c` (2026-10-22) against the v12 pin `4da83f62`; last merge base `fab0f23b`
(2026-10-19). Raw data: `docs/performance/measurements-2026-10-23/upstream-delta.json`.

Upstream `upstream/master` at `c74ac92c`, pin `4da83f62`, merge base `fab0f23b`: 40 commits the pin lacks.

| Touches | Commits |
|---|---:|
| engine | 10 |
| card | 25 |
| set | 26 |
| test | 13 |
| data | 7 |

Card classes: 29 added, 40 modified, 0 deleted (0 without a registered name). In precon decks: 19; in the owner collection: 1 (count only).
Merge into the pin: **CONFLICTS** (8 files)

| Repin trigger | Status | Detail |
|---|---|---|
| T1 rule fix touching the lab | REVIEW | 10 engine commits, 19 changed card classes are in precon decks; read the commits against the deck lists |
| T2 release 1.4.63 or POM above 1.4.62 | NOT_MET | upstream POM 1.4.62 |
| T3 at least 2 blocked decks become importable | NOT_MET | 13 decks lack a card at the pin, 0 would be complete with upstream's registrations |
| T4 the fork's own need | OWNER | fork patch backlog or an engine bug only the fork can fix; not in the repo |
| T5 conflict pressure on core | REVIEW | 0 core conflict files; hot files changed upstream: GameImpl.java, GameState.java, PlayerImpl.java |
| T6 more than 6 weeks since the last merge | NOT_MET | merge base 2026-10-19, 0 weeks before 2026-10-23 |

Determinism hazards in new upstream lines: 0 RNG, 6 unordered collection; cards among them in precon decks: 1.
- unordered `Avenge.java` [precon: 2026_avengers_assemble, 2026_avengers_assemble_collector_s_edition]
- unordered `Avenge.java` [precon: 2026_avengers_assemble, 2026_avengers_assemble_collector_s_edition]
- unordered `BeastEruditeAerialist.java`
- unordered `BeastEruditeAerialist.java`
- unordered `CombatDamageDealtToYouTriggeredAbility.java`
- unordered `TeamworkCost.java`

Core signatures changed or removed upstream: 3; still called from files the fork changed or the lab bridge: 1.
- changed `CombatDamageDealtToYouTriggeredAbility(Zone,Effect,boolean,boolean)` to `(Effect,SetTargetPointer) / (Zone,Effect,SetTargetPointer,boolean)` in `CombatDamageDealtToYouTriggeredAbility.java`
- changed `restore(GameState)` to `(GameState,boolean)` in `GameState.java`; name also used in CommanderPlaysCountStateRestoreTest.java, RG02CommanderDamageRestoreTest.java, GameImpl.java, PlayerImpl.java
- removed `setSourceCostsTag(Game,Ability,String,Object)` in `CardUtil.java`

Precon cards the engine lacks: 31; upstream now implements 1; 0 have an upstream PR on record.
- Tamiyo, Upriser Crowned (2026_multiverse_reforged)

Engine-core commits:
- `e18157de17` 2026-10-22 Use LKI of phased-out permanents in the remaining battlefield lookups (#16576)
- `39d426476a` 2026-10-21 [TRC] Implement Koloth, Tribble Hunter (#16569)
- `859591d006` 2026-10-21 Use getSpellOrLKIStack in CantBeCopiedSourceEffect like Twinning Staff (#16575)
- `12be750f98` 2026-10-21 Fix "this spell can't be copied" never applying (#16521)
- `5f04616c6c` 2026-10-21 Melded permanents can't be turned face down (712.16) (#16562)
- `4dc8f311d4` 2026-10-21 Use last known information of phased-out permanents for damage sources (#16561)
- `22fca32e3a` 2026-10-21 Payment cancel - fixed that some spells can lost activation status on impossible payment or cancel (example: Convoke, Delve, Improvise,  #16509)
- `e6edddc37b` 2026-10-21 Update Thriving lands to the new enters tapped and choose a color template (#16560)
- `463dba35a5` 2026-10-21 Add BlocksAllTriggeredAbility and use it for whenever a creature blocks cards (#16559)
- `3f4223aade` 2026-10-20 [FRC] Implement Tamiyo, Upriser Crowned (#16408)

Changed card classes that are in precon decks:
- Avenge (added): 2026_avengers_assemble, 2026_avengers_assemble_collector_s_edition
- Flayer of the Hatebound (modified): 2019_merciless_rage, 2025_revival_trance__final_fantasy_vi_, 2025_revival_trance_collector_s_edition__final_fantasy_vi_
- Flickerform (modified): 2013_evasive_maneuvers, 2017_evasive_maneuvers
- Heroic Return (added): 2026_avengers_assemble, 2026_avengers_assemble_collector_s_edition
- Norn's Decree (modified): 2023_corrupting_influence
- Panther Habit (added): 2026_wakanda_forever, 2026_wakanda_forever_collector_s_edition
- Silver Surfer, Galactus's Herald (added): 2026_the_fantastic_four, 2026_the_fantastic_four_collector_s_edition
- Spitting Image (modified): 2016_breed_lethality, 2018_breed_lethality, 2020_reap_the_tides, 2021_quantum_quandrix
- Sword of the Paruns (modified): 2013_evasive_maneuvers, 2017_evasive_maneuvers
- Tamiyo, Upriser Crowned (added): 2026_multiverse_reforged
- Thought Reflection (modified): 2015_seize_control
- Thriving Bluff (modified): 2022_cabaretti_cacophony, 2022_maestros_massacre, 2022_riveteers_rampage, 2023_ahoy_mateys, 2023_timey_wimey, 2023_veloci_ramp_tor, 2024_family_matters, 2026_dance_of_the_elements
- Thriving Grove (modified): 2021_aura_of_courage, 2022_cabaretti_cacophony, 2022_riveteers_rampage, 2023_blast_from_the_past, 2023_veloci_ramp_tor, 2024_peace_offering, 2026_dance_of_the_elements, 2026_turtle_power_
- Thriving Heath (modified): 2021_aura_of_courage, 2021_dungeons_of_death, 2022_cabaretti_cacophony, 2022_obscura_operation, 2023_blast_from_the_past, 2023_cavalry_charge, 2023_veloci_ramp_tor, 2024_family_matters, 2024_miracle_worker, 2024_peace_offering, 2026_dance_of_the_elements
- Thriving Isle (modified): 2021_aura_of_courage, 2021_dungeons_of_death, 2022_maestros_massacre, 2022_obscura_operation, 2023_ahoy_mateys, 2023_blast_from_the_past, 2023_cavalry_charge, 2024_family_matters, 2024_miracle_worker, 2024_peace_offering, 2026_dance_of_the_elements, 2026_turtle_power_
- Thriving Moor (modified): 2021_dungeons_of_death, 2022_maestros_massacre, 2022_obscura_operation, 2022_riveteers_rampage, 2023_ahoy_mateys, 2023_cavalry_charge, 2023_masters_of_evil, 2024_miracle_worker, 2026_dance_of_the_elements, 2026_turtle_power_
- Trostani, Selesnya's Voice (modified): 2019_primal_genesis, 2026_hatsune_miku
- Verdant Sun's Avatar (modified): 2020_reap_the_tides, 2021_witherbloom_witchcraft, 2023_veloci_ramp_tor, 2026_tramplesaurus_rex
- Xathrid Demon (modified): 2014_sworn_to_darkness

## 3. Reading

- **No trigger is met; nothing argues for a repin to upstream today.** T2, T3 and T6 are
  measured `NOT_MET`. T4 is the fork's own need and not in the repository. T1 and T5 are
  `REVIEW`: ten engine-core commits exist (phasing and last-known-information, "can't be
  copied", melded permanents, payment cancel, the Thriving Lands template, a block trigger
  base class, two card implementations), and three hot files (`GameImpl`, `GameState`,
  `PlayerImpl`) are touched, but the core merges without a conflict. None of the commits
  touches the engine's copy or playable-calculation paths by name (read from the commit
  list; the script only sees files).
- **The merge conflicts are cards converging, not core drift.** All eight conflicting files
  are add/add: upstream implemented Avenge, Heroic Return, Panther Habit and Silver Surfer
  (with their tests) that the fork carries already. A merge keeps the fork's version, or takes
  upstream's and drops the fork copy; either way the cards need a look before a hash comparison.
- **The one silent break is a fork test.** `GameState.restore(GameState)` became
  `restore(GameState, boolean)`. Upstream updates its own caller in `GameImpl`, but the fork's
  `CommanderPlaysCountStateRestoreTest` calls `game.getState().restore(saved)` and upstream does
  not touch that file: no textual conflict, and the test stops compiling after a merge. The
  name match also lists `RG02CommanderDamageRestoreTest` (its own private `restore` helper) and
  `PlayerImpl` (`restore(Player)`); those are name collisions, which is the price of matching
  by name.
- **Hazards: no RNG, six unordered-collection lines in four files.** Avenge is the only changed
  card of them in a precon deck, and its `Map<UUID, Set<UUID>>` is read back through `anyMatch`,
  so the hash order never reaches a result. The one to read at merge time is
  `CombatDamageDealtToYouTriggeredAbility`: its new `PERMANENT` mode collects the attackers
  with `Collectors.toSet()` into `FixedTargets`, so an effect may later walk them in hash order.
  Only Tamiyo, Upriser Crowned uses that mode (Norn's Decree, which the fork's decks hold, keeps
  the old player or no pointer). `BeastEruditeAerialist` and `TeamworkCost` are in no precon
  deck.
- **Thriving Lands** (five cards, in 8 to 12 precon decks each) change to a new template.
  Any hash that involves one of them will move after a merge and has to be explained, not
  accepted.
- **Cards gained for the precon decks: one.** Tamiyo, Upriser Crowned, whose deck
  (`2026_multiverse_reforged`) still lacks Jace and Dack. 13 decks lack 31 card names at the pin,
  and a merge would complete none of them, so T3 is not met. The list comes from the importer
  (`measure_precon_imports.py --enumerate-missing` on the v12 bridge, 182 of 195 decks import;
  compact copy in `measurements-2026-10-23/precon-imports-v12.json`). Without `--import-report`
  the script derives the same 31 names and 13 decks from the registrations at the pin alone, in
  about 6 s and without a JVM.

## 4. Limits

- A set file keeps the registration of a card it does not implement yet as a commented-out
  `SetCardInfo` line. The registry reading skips those; counting them as registered gave 16
  missing names instead of the importer's 31.
- The signature scan reads single lines: a parameter list over several lines, a changed
  return type or a changed visibility is not seen, and an overload added next to an unchanged
  original is correctly not a change. Callers are matched by method name in the files the fork
  changed, so a common name lists files that call something else.
- The hazard scan is a text match on added lines. It finds where to look, not whether the
  collection is iterated into an observable order.
- T1 and T5 stay `REVIEW` by design: deciding them takes reading the commits against the deck
  lists and the hot methods.
- Upstream PR status is not read by the script (the agent sessions cannot search GitHub); pass
  it in with `--pull-requests-json` when it matters.
