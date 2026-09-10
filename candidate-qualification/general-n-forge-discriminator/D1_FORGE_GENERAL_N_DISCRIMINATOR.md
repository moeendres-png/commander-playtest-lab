# D1 — Forge General-N Commander Discriminator

- Status: TERMINAL / SEALED (bounded discriminator; not qualification)
- Date: 2026-09-10 (UTC)
- Research branch: `research/general-n-forge-discriminator-20260910`
- Research base (freshly verified): `origin/ws48/forge-v1.0.5-successor-qualification`
  `c8d6f97b93cf383ec2b481d96f6fb33103db4ddd` / tree `3094ed3a7ae6e9cb65ac27fd2b0048bcac5a1c0e`
- Active WS48 ownership (discovered, NOT written to):
  worktree `/home/moeen/code/commander-ws48` on `ws48/forge-v1.0.5-successor-qualification`
  @ `c8d6f97b` (matches origin; muse variant `muse/ws48-forge-v1.0.5-heavy-support` @ `895eca21` untouched)
- Isolated worktree: `/home/moeen/code/commander-general-n-d1` (this branch only)
- Forge pin (re-verified at runtime by driver): repo `moeendres-png/forge`,
  branch `foundry/ws45-v104-observation-remediation`,
  commit `66caae16015bd403bc0a52fa6689afb5508f74d0`,
  tree `40fc8f29ce4de31a964972461db2b48b4221e07f`, version `2.0.15-SNAPSHOT`
- Probe: `candidate-qualification/general-n-forge-discriminator/`
  (`general_n_discriminator_template.java`, `run_general_n_discriminator.py`)
- Raw evidence: `candidate-qualification/general-n-forge-discriminator/GN_RESULT.json`
  (55 rows: 11 checks × N=2..6), seed base 424242 (+N), 108 mechanical controller stubs
- Build: compiled against pinned Forge classes into `/tmp/ws48/general-n/work` scratch only;
  no provider artifact, no restore mechanism, no harness legality, no AI outcome use.

## Method (bounded architecture discriminator, NOT full qualification)

Hand-built native Commander games for each N=2..6 using only pinned Forge
engine classes: `GameRules(GameType.Commander)+addAppliedVariant(Commander)`,
`RegisteredPlayer.forCommander(deck)` (40 life, commander binding),
`Match.createGame()`, native `player.initVariantsZones(psc)` (exact call
`Match.startGame` makes at `Match.java:323`; pure zone setup, no controller
calls), native `Combat` + `fireTriggersForUnblockedAttackers` +
`assignCombatDamage`, native `concede()` → `checkGameOverCondition()` →
`onPlayerLost()` → `ingamePlayers.remove` (`Game.java:999`), native
`PhaseHandler.addExtraTurn/getNextTurn`, native `game.getNextPlayerAfter`
(the same primitive `PhaseHandler` uses for turn AND priority advancement).
Commander: real legendary `Isamaru, Hound of Konda` in `DeckSection.Commander`,
99× Mountain main. Full `game.start()` deliberately NOT executed (would
require controller decisions); all claims are construction/ring/zone scope.

## Per-N gate classification

| N | CONSTRUCTS | TURN_RING | PRIORITY_RING | COMMANDER_INIT | COMBAT_MULTI_DEFENDER | ELIMINATION | HIDDEN_INFO | DETERMINISM |
|---|----|----|----|----|----|----|----|----|
| 2 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 3 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 4 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 5 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 6 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

Evidence class per gate: CONSTRUCTS / TURN_RING / COMMANDER_INIT /
COMBAT_MULTI_DEFENDER / ELIMINATION / DETERMINISM = DIRECTLY_VERIFIED
(hand-built native repro rows). PRIORITY_RING = DIRECTLY_VERIFIED (runtime
ring walk `gn-seat-1>…>gn-seat-0` closure for every N) + CODE_DERIVED
(`PhaseHandler.java:1062,1119` advance priority via the same
`game.getNextPlayerAfter` primitive). HIDDEN_INFO = CODE_DERIVED/structural
(N distinct principal-bound controllers, each `getPlayer()` is its own seat;
NOT full hidden-information qualification — no card-visibility adversary run).
OPPONENTS (folded into PRIORITY_RING): every seat `getOpponents().size()==N-1`,
never self-containing (e.g. N=6 all seats =5). EXTRA_TURN (folded into
TURN_RING): `addExtraTurn(non-next)` → `getNextTurn` redirects observably
(e.g. N=5 base `gn-seat-1` → extra `gn-seat-2`) with base ring intact.

## Required adversarial scenarios (all PASS, DIRECTLY_VERIFIED)

- Eliminate middle seat N=5: `gn-seat-2` conceded → natively removed from
  `ingamePlayers` → alive ring exactly `[gn-seat-1, gn-seat-3, gn-seat-4, gn-seat-0]`.
- Extra turn N=5: redirects to non-next seat, base ring order intact after push.
- Attack non-next opponent N>=4: N=5 bands=4 defenders include seats 3,4;
  N=6 bands=5 all other seats; `assignCombatDamage` RETURNED natively
  (no `AttackingBand.isBlocked()` 873-NPE).
- Concession/leave N=6: middle + last conceded → alive ring of 4 intact.
- Priority ring after elimination: post-elimination walk visits exactly the
  surviving seats for every N (incl. N=2 game-over completion path).

## Hard gate — numPlayers==4 assumptions (exact findings)

1. Pinned Forge Rules Core (`66caae16`): NO `numPlayers==4` / `getNumPlayers==4` /
   player-count-4 assumption found. `Match`/`Game`/`GameRules`/`Player`
   (`getOpponents`, `getNextPlayerAfter` incl. just-lost branch, `forCommander`,
   `forVariants`, `checkLoseCondition` w/ 21-commander-damage, `onPlayerLost`
   CR 800.4 handling) are all general-N. Only unrelated `==4` hits
   (`Player.java:1907` speed, `:3344` level). No engine-fork authority required;
   no defect to classify; discriminator did not stop any path.
2. WS48 Forge provider overlay (`candidate-qualification/ws48-forge-v1.0.5/*.py`):
   zero `==4`/`!=4`/`Literal[4]` player-count assumptions.
3. Lab/orchestration layers (same repo, NOT Rules Core, NOT Forge provider path)
   DO hard-require 4P — reported exactly, production-driving scope:
   - `src/commander_lab/candidates/models.py:224-225`
     `player_count: Literal[4] = 4`, `seat: int = Field(ge=1, le=4)`
   - `src/commander_lab/engine/rules/tactical.py:182-183`
     defaults `player_count` to 4, raises unless `== 4`
   - `src/commander_lab/engine/rules/full_game_batch.py:49-52`
     requires `player_count == 4` and pilot seats exactly `{1,2,3,4}`
   - `src/commander_lab/engine/rules/full_game.py:53,309-313,1186,1190`
     seat `le=4`, exactly 4 pilot bindings covering 1..4, `seed % 4`, `player_count != 4` reject
   - `src/commander_lab/models/tooling.py:767` `seat_position … le=4`
   - `src/commander_lab/pod_scheduling.py:143-145` seat arithmetic `% 4`
   - `src/commander_lab/project_context.py:403` requires `pod_size == 4`
   - `src/commander_lab/mulligan/canonical.py:107`, `models/meta.py:117`,
     `whole_deck/*`, `first_run_preparation.py:114` similar 4P gates
   - `engine-bridge/.../Phase6DifferentialAdapter.java:346,357,379`
     XMage-side scenario loop `seat < 4`, `setNumPlayers(4)`, `size() != 4` reject
   Reachability: these gate lab scenario construction/policy driving ABOVE the
   engines. The lab therefore cannot currently DRIVE general-N games even though
   the pinned Forge engine natively supports them. No 4P assumption was found IN
   the Forge production-reachable Rules path, so the hard gate does not fail the
   hypothesis; it scopes follow-up work to the driving layers.

## Conclusion (exactly one)

GENERAL_N_HYPOTHESIS_SUPPORTED

Rationale: for every N=2..6 all eight discriminator gates PASS against the
pinned Forge stack with native engine mechanics, deterministic seeded repeat is
identical at construction scope, and no `numPlayers==4` assumption exists in
Forge Rules Core or the WS48 Forge provider. A smoke PASS is not Full Rules
qualification: full `game.start()` execution, mulligan/priority-action play,
trigger-rich combat, commander-damage wins, hidden-visibility adversaries, and
RNG/replay remain unqualified and are explicitly out of scope.

## 4P-specialization deletion statement

No planned 4P-specialization work can be deleted. There is no 4P specialization
in the Forge engine to remove (nothing to delete there). The lab/XMage driving
layers listed above REQUIRE 4P and must be RETAINED as-is until a dedicated
generalization workstream re-validates them for N!=4; deleting them now would
remove currently-enforced (if narrow) scope guards with no replacement.

## Remaining blockers / next action

- None for D1 itself (deliverable sealed on this branch).
- If general-N driving is later wanted: open a bounded generalization workstream
  for the driving layers in §3 (NOT the engine), each with fresh affected-gate
  reruns. Do NOT import this smoke PASS as qualification credit anywhere
  (grants_behavior_credit=false, grants_qualification_credit=false).
- TURN_STATUS = INTERRUPTED; TASK_COMPLETE = NO (WS33 contract turn boundary;
  D1 deliverable itself is terminal).
