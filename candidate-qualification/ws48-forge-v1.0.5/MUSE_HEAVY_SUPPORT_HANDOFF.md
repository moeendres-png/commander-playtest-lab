# MUSE HEAVY SUPPORT HANDOFF — WS-48 FORGE v1.0.5

**Lane:** parallel Muse support (NOT final qualification authority)
**Support branch:** `muse/ws48-forge-v1.0.5-heavy-support`
**Base:** `origin/ws48/forge-v1.0.5-successor-qualification` @ `8dd961409917680a1a4e14999e30e266545097a8`
**Updated:** 2026-09-08 (UTC) — Phase A complete, Phase B in progress

## 1. SOURCE LOCK (freshly verified locally)

| Identity | Value | Verified |
|---|---|---|
| WS-48 HEAD | `8dd961409917680a1a4e14999e30e266545097a8` | `git rev-parse origin/ws48/...` PASS |
| WS-47 freeze commit | `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8` | `git rev-parse` PASS |
| WS-47 freeze tree | `f596c54d2cb229b9827c6c94a278175e8312c65c` | PASS |
| WS-47 namespace tree | `12af73695c801a42a0193ee895d5fc0843d16b0c` | PASS |
| WS-47 schema | `commander-lab.semantic-fixture-materialization/1.0.5` | PASS |
| Materialization SHA-256 | `0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3` | `sha256sum` PASS |
| Canonical bundle digest | `631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01` | doc field PASS |
| Provider denominator | 107 unique fixture_ids | PASS |
| Forge repo/branch | `moeendres-png/forge` / `foundry/ws45-v104-observation-remediation` | clone in progress |
| Forge commit/tree | `66caae16015bd403bc0a52fa6689afb5508f74d0` / `40fc8f29ce4de31a964972461db2b48b4221e07f` | pending clone verify |
| Historical runtime credit | 0 | per WS48 checkpoints |

## 2. CURRENT WS-48 GATE MATRIX

| Obligation | Status | Evidence |
|---|---|---|
| source lock (G48-01/02) | PASS | §1 + WS48_CHECKPOINT_01 |
| denominator/digest reconciliation (G48-04/05) | PASS | WS48_CHECKPOINT_01_PREFLIGHT_PASS.json (CI run 34242094044) |
| strict no-request-echo (G48-06) | PASS | WS48_CHECKPOINT_03 (CI run 34260903310) |
| Construction 107 (G48-07) | PASS | WS48_CHECKPOINT_03: 107/107 RUNTIME_VERIFIED |
| independent native-readback normalization (G48-08) | PASS | WS48_CHECKPOINT_04: 107/107 (CI run 34263710979) |
| Behavior 107 (G48-09) | NOT_RUN | inventory+shape probe only (see §3) |
| AF04/AF05/AF06/AF08/AF09 | UNKNOWN | no fresh behavior-dependent evidence yet |
| CARD_02 | NOT_RUN | construction row PASS only; behavior not executed |
| hidden-information adversarial | PARTIAL | noecho knowledge probes PASS; full HI evidence UNKNOWN |
| RNG/replay | NOT_RUN | contract has 5 replay_rng rows + RNG probes in noecho gate |
| unsupported/fallback-zero | PARTIAL | 6 fail_closed_probe rows in denominator; runtime NOT_RUN |
| terminal evidence closure | NOT_RUN | — |

Earliest failing production-relevant gate: **G48-09 behavior** (NOT_RUN).

## 3. BEHAVIOR CONTRACT SHAPE (locally reproduced)

`artifacts/ws48-behavior-shape/INVENTORY.json` built locally from immutable
materialization: denominator=107, decision_count=92, modes={NATIVE_STATE_LOAD:100,
NATURAL_GAME_START:7}. Decision families: priority 23, mulligan 21, target 11,
choose_mode 9, choice 5, replacement_effect 5, declare_attacker 4, mana_payment 3, ...
Selector kinds include semantic_action 44, boolean 10, semantic_mode_key 7,
fail_closed_probe 6, semantic_player 4, ... Native procedure ops include
NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE ×76, NATIVE_CAST_SPELL ×15,
NATIVE_RESOLVE_TOP_OF_STACK ×16, EXTERNAL_SUBMIT_SELECTED_SEMANTIC_RESPONSE ×24,
NATIVE_CONTINUE_WITH_EXPLICIT_SCRIPTED_PRIORITY_PASSES ×19, plus combat / trigger /
commander-zone / replay-checkpoint / negative-probe ops.

## 4. KEY ARCHITECTURAL FINDING

The generated provider (`scripts/ws23_generate_forge_vertical_provider.py` →
`ws25` → `finalist` → `ws40` overlays) already implements an interactive
Rules-Core-owned decision surface: `Broker.choosePriority` enumerates native legal
actions via `Card.getAllPossibleAbilities(actor, true)` and emits DECISION_FRAME
kind `priority`; `chooseSpellAbilityToPlay`/`playChosenSpellAbility` use native
`PlaySpellAbility`; mode/target/mana/combat-damage choices are externally selected
**only from core-authorized options** (opaque option ids). Fail-closed on
zero/multiple-match is a harness-side obligation.

Gap for behavior: DECISION_FRAME options carry opaque labels
(`PASS`/`FORGE_LEGAL_ACTION`/`NATIVE_OPTION`); the harness cannot map a
`semantic_action` (e.g. cast obj:micro-growth) to the offered option without a
provider-emitted semantic descriptor per option. Fix must be provider-side
observation enrichment (labels only, enumeration stays in Rules Core), never
pilot-side legality reconstruction. Event stream (`expected_events`) likewise needs
a provider-emitted native event feed; currently only snapshots exist.

## 5. NEXT

Phase B: verify Forge clone → build forge-game → compile provider → reproduce one
construction case locally, then construction subset, then design behavior runner.

## 6. PROGRESS LOG (support branch commits)

- `eaa93b8f` Phase A: source lock, gate matrix, behavior shape.
- `197dcd80` Behavior G48-09 implementation design (`WS48_BEHAVIOR_DESIGN.md`).
- `fbdc4f69` Behavior event verifier (`behavior_events.py`) + 5 unit tests.
- `5eb6cdcb` Behavior driver core (`behavior_driver.py`: session state machine,
  fail-closed selector matchers, scripted passes, event/postcondition terminal
  verification) + fake-provider tests; postcondition registry
  (`behavior_postconditions.py`: G-B decision-log, G-C negative, stack-empty;
  unknown templates FAIL). 11 tests pass; ruff clean.
- Op matrix: 64 distinct native-procedure ops over 107
  (`artifacts/ws48-behavior-shape/OP_MATRIX.json`).
- Q1 (stack:N indexing) + Q4 (tape schema) resolved; Q2 (mode-key binding) + Q3
  (per-viewer capture) remain for Terra/Sol at closeout.

Remote Forge pin verified as branch tip (`ls-remote`); local clone in progress
(`/tmp/opencode/forge`, depth-1 single-branch).

## 7. BEHAVIOR G48-09 PROGRESS (2026-09-09)

Local: Forge `66caae1` built (JDK 17) + WS-48 provider compiled WITH behavior
surface (`COMMANDER_LAB_WS48_BEHAVIOR=1` gates emissions; construction path
byte-identical to CI) + **local construction 107/107 PASS** with that build.

First native behavior passes (local, early-terminal):
MICRO_STACK, MICRO_PRIORITY, PILOT_TARGET, PILOT_MANA_PAYMENT, MICRO_MANA_PAYMENT,
PILOT_CHOOSE_MODE, CARD_02.

Provider surface added (all Rules-Core-owned, external-choice-only):
semantic action/target/mana/combat-assignment descriptors, native GameEvent feed
(cast/stack/resolve/commander/attacker/blocker/mana_paid/mode/ability events),
behavior checkpoints with semantic refs + commander cast counts, native
declareAttackers/declareBlockers from CombatUtil enumeration, neutral
CostDecisionMaker (mana/tap structural; rest fail-closed), externalized
payManaCost from canPlay mana abilities, singleton costs/mode/variant handling,
mutable mode list (Forge sorts in place), typed unexpected stops with traces.

Driver: fail-closed selector matchers, active-cast cost context (cost-state
sources with or without mana entries), journal-anchored evaluation at first
satisfying checkpoint, early termination, zone-diff engine with incarnation
pairing, contract-exact frame/decision/lifecycle/RNG/viewer synthesis.

Key findings: object incarnation changes across zones (resolves/casts create
new unbound objects — checkers match by identity+controller+uniqueness);
`priority:Pn`-style recurring events must not drag anchors (completion-based);
setup snapshot arrives post-pregame (derivations wait for it).

## 8. BEHAVIOR MATRIX RUN 2 (2026-09-09, in progress)

First full-matrix run (batch-1 provider): 8/107 → second run 34/107.
Current run: batch-2 provider (announce/boolean/amount/order/pile/color/scry/
trigger-permutations/combat+amount refs/turn-began/typed stops/natural
lifecycle hook) + batch-2 driver (natural derivations, unscripted discretion,
off-actor passes, negative cause-casts + post-emit gate, boolean/integer/
amount/order/color/scry matchers, HI/lifecycle checkers). HIDDEN 01-05 PASS.

## 9. RECOVERY CHECKPOINT 2026-09-09 (post host shutdown)

Support branch pushed: `muse/ws48-forge-v1.0.5-heavy-support`
Remote HEAD == local HEAD: `243a098549723b4f43a4ac9db382169bcee9d0cc`
Tree: `67d0caabb69b8e400a23d4149dc813b10145ab91`
Canonical `ws48/forge-v1.0.5-successor-qualification` untouched (still `8dd96140`).

Impact adjudication: all support changes are Category A (behavior-only /
observation-only / driver). No CI construction/readback/noecho path, immutable
contract, or native legality enumeration is touched. G48-07/G48-08 CI credit
retained; no construction rerun. Local /tmp eval state was rebuilt from source
locks (Forge pin re-verified `66caae1`/tree `40fc8f29`).

Gates: G48-07 PASS, G48-08 PASS, G48-09 behavior credit 0/107 (in progress).

Exact G48-09 blocker: state-load libraries are EMPTY (GameState clears all
zones); turn-2+ draws kill the very players whose scripted actions come later
(proven: MICRO_COSTS P2/P3 vanish at their draws with 39 life, 0 poison).
Multi-turn flow is contract-intended (turn-advance ops in procedures), so the
blocker is missing canonical library background in behavior sessions, not a
contract defect. Fix in progress: behavior-mode-only padding of unspecified
libraries with face-down Mountains to canonical 99 (hidden_information family
excluded; construction path untouched). Library-intent question recorded for
Terra adjudication of credit; implementation unblocks execution either way.

Unit tests: 14/14 pass (ruff clean). Behavior smokes green (micro/pilot/
commander/declare/combat/tax/announce/naturals).

Next: rebuild provider with padding → MICRO_COSTS live proof → full-matrix
rerun → remaining families (triggers/APNAP, WS05 elim/turn/dmg, replay tapes,
zone-choice, copy, RNG/replay) → G48-10..13 as evidence permits.

## 10. LIBRARY PADDING PROOF 2026-09-09

Proven: GameState.setupPlayerState clears ALL zones; unspecified libraries are
empty; turn-2+ draws eliminate players whose scripted actions come later
(MICRO_COSTS P2/P3 vanished at their draws, 39 life, 0 poison, no pending
elimination). Multi-turn flow is contract-intended (turn-advance ops).

Implemented (behavior mode only, NATIVE_STATE_LOAD only, HIDDEN_* excluded):
pad each library with opaque face-down Forests to canonical 99 at the bottom,
preserving specified order/positions; Mountain... Forest registered via
existing registerCardRules path; distinct id range 910000+ (no collision with
1000+i native binding or 900000+ knowledge minimums). Construction path
byte-identical (gated). Extends the established WS-45 opaque-capacity pattern.

Validated: local construction BLOCK-4 + MICRO_COSTS still CONSTRUCT_OK;
HIDDEN_01 behavior PASS (exclusion holds); MICRO_COSTS behavior PASS (P2 casts
Hex turn 2 for {7}{B}{B} with Esior +3, cost_determined fires, 6 targets
matched incl. multi-ref disambiguation); MICRO_TRIGGERS behavior PASS
(singleton trigger auto-play, Surge target P2, damage:P2:2).

New native surfaces this round: direct loaded-combat-step invocation (devModeSet
skips onPhaseBegin turn-based actions — proven via phase trace), commander tax
at payment time via native getCastFrom + prior count, upkeep Phase-trigger
runner, trigger order-and-play (singleton auto), zone-order passthrough,
combat/card/player damage events, pending eliminations + poison/lost in
checkpoints, stable seat pids, ref-linked arrival labels, cost_determined
synthesis (printed vs expected_total_cost), mana window for X, scry/color/
announce/amount/order/boolean matchers, negative cause-casts + post-emit gate.

Open authority items for Terra/Sol: library-intent credit for padded runs;
unscripted-discretion policy (lowest-id deterministic picks where the contract
leaves choices open); mode-key native bindings (create_devils, loyalty_0);
empty-declaration conservatism.
