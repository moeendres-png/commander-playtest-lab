# WS-49 CHECKPOINT 14 — G49-09 BEHAVIOR INVENTORY + RUNNER v1 (IN PROGRESS)

Status: **IN PROGRESS / NO BEHAVIOR CREDIT**

G49-01..G49-08 retained PASS untouched. G49-09 behavior credit remains 0/107.
No AF07, Architecture Freeze, provider winner, or Decision-Contract
executability is claimed.

## 1. Source-lock reconciliation (start of task)

- Commander-Lab branch `ws49/xmage-v1.0.5-successor-qualification`:
  HEAD `4488ec95a1f38697af65480f59438b153cd7b0af` /
  tree `b424c389c773dbe55599268cb621174d01290a91`.
  Remote branch HEAD matched exactly; worktree clean. No source movement:
  retained G49-01..G49-08 evidence stands, no requalification triggered.
- XMage baseline `/home/moeen/code/xmage-ws49-baseline` (read-only inspection):
  HEAD `0c1f455ea8c8fa48ab9d638ad5068ec242800428` /
  tree `fdb8bf56a8bd8199a4ef372e468d93d6550b0649` — pin MATCHES the WS49
  engine authority exactly.
  Working tree DIRTY (7 modified files, all local-only, NOT committed):
  `Mage.Sets/.../ExposeTheCulprit.java`, `GhastlyConscription.java`,
  `JalumGrifter.java`, `JeskaiInfiltrator.java`, `VialSmasherTheFierce.java`,
  `Mage/.../PlayerImpl.java`, `mage/util/RandomUtil.java`.
  Per contract: that checkout was NOT modified/cleaned, and NONE of its
  build/runtime output may serve as terminal qualification evidence.
  Terminal G49-09 evidence executes ONLY in CI, which checks out the exact
  immutable pin independently (`ws49-xmage-v105-behavior.yml` pins
  commit/tree identically to the construction workflow).
- WS47 materialization bytes re-extracted from freeze commit `192e2b77`
  locally: SHA-256 `0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3`
  — exact match. All inventory work below is bound to those bytes.
- `vendor/engine-source/` in this worktree contains only `README.md`
  (no symlink, nothing committed). No action needed.

## 2. Work completed

1. `build_behavior_inventory_v105.py` (new, WS49-owned): strict fail-closed
   transcription of the 107-record provider denominator into per-record
   behavior obligations. Verified locally against exact WS47 bytes:
   - denominator 107, unique ids 107;
   - families `{player_count:4, pilot_boundary:17,
     pilot_boundary_negative:7, hidden_information:20, replay_rng:5,
     micro_rules:17, actual_card:1, multiplayer_commander:36}`;
   - entry modes `{NATIVE_STATE_LOAD:100, NATURAL_GAME_START:7}` with exact
     natural-start fixture identity (7 ids match construction probe);
   - every decision entry carries all 7 forbidden fallbacks, FAIL_CLOSED on
     zero/multiple match, matches-only-offered-options policy;
   - every record carries non-empty native procedure, expected events, and
     terminal postconditions;
   - decision-family totals: priority 23, mulligan 21, target 11,
     choose_mode 9, replacement_effect 5, choice 5, declare_attacker 4,
     mana_payment 3, choose_use 2, declare_blocker 2, pile/choice variants 1
     each, trigger_order 1, announce_x 1, choose_object 1, choose_ability 1,
     target_amount 1, multi_amount 1;
   - selector kinds: semantic_action 44, boolean 10, semantic_mode_key 7,
     fail_closed_probe 6, semantic_player 4, semantic_object 3,
     mana_payment 3, semantic_stack_object 2, amount_assignment 2,
     attacker_assignment 3, blocker_assignment 2, + singletons
     (integer, partition, order, semantic_ability_key, semantic_choice_key,
     semantic_objects).
   Output grants zero credit (`behavior_credit_granted: false`,
   `behavior_status: UNKNOWN_NOT_RUN` per row).
2. `run_full107_behavior_probe_v105.py` (new, WS49-owned): G49-09 behavior
   runner v1. Restores each record natively (state-load) or via natural
   game start, then CONTINUES into Rules execution:
   - generic scripted decision loop: native offers published, scripted
     selector matched with unique-match discipline (zero/multiple fail
     closed with truncated native-offer diagnostics), rebound to the exact
     native option, submitted via the external controller;
   - priority passes submitted ONLY while the record procedure declares
     explicit scripted passes; obligations ending at the scripted action
     stop driving instead of answering foreign frames;
   - multi-step entries (mana_payment symbol queue + scripted sources,
     amount_assignment target map) consumed across successive native
     decisions; completion events (`mana_paid:*`, `amount_assignment:*`)
     derived from natively committed values, never scripted text;
   - negative records: drive to the declared frame, withhold every response
     (handler intentionally unavailable), terminate with typed
     UNSUPPORTED_DISCRETIONARY_DECISION; any fallback/continuation fails;
   - hidden records: per-viewer observation battery + honey-sentinel
     (`WS30_HONEY_P2_PRIVATE_7F3A`) scan across observations, state, and
     result payloads;
   - natural records: held-open session reusing the construction probe's
     player-bound mulligan helpers; lifecycle events gated on native
     preconditions; terminal state observed from the live game;
   - per-record anti-echo probe (mutated expectation must fail against the
     unchanged native log);
   - terminal checkers: `PLAYER_COUNT_*` opening battery implemented;
     every other fixture returns explicit
     `UNKNOWN_TERMINAL_CHECKER_NOT_IMPLEMENTED` (no credit by construction).
   Pure-function self-tests pass locally (event evaluation incl. ordering
   and forbidden detection, anti-echo sensitivity, unique-match and
   zero-match fail-closed, boolean matcher). Engine paths compile
   (`py_compile`) but are UNRUN locally: no clean XMage build exists here
   and the dirty baseline must not supply terminal evidence.
3. `.github/workflows/ws49-xmage-v105-behavior.yml` (new, WS49-owned):
   behavior CI mirroring the construction workflow's locks, overlays, and
   builds (exact WS47 + XMage pins, same 13 overlay steps), then inventory
   verification + full-107 behavior probe from record 1 with sealed
   artifact upload. No fixture filter exists anywhere: partial denominators
   are unrepresentable.
4. Edge cases preserved from inventory for runner correctness:
   - `NEGATIVE_PARENT_CLASS_FALLBACK` has an EMPTY decision script but
     requires `decision_frame:choose_object` + fail-closed (handled as
     `negative_empty_script`);
   - `semantic_stack_object` (`stack:1`) resolved against the live native
     stack view, never requested state;
   - `semantic_objects` list requires exact-set match;
   - `PILOT_CHOOSE_USE` boolean False selects the native No option; the
     `scry_choice:keep_top` vocabulary must come from native outcome
     observation (checker pending, currently UNKNOWN).

## 3. Failure classification (this cycle)

- No ENGINE_RULES_DEFECT established (no behavior has executed yet).
- No PROVIDER_ADAPTER_DEFECT established.
- QUALIFICATION_HARNESS_DEFECT risk (v1 blind spots, documented):
  H1 unimplemented terminal checkers (103/107 fixtures) — EVIDENCE_GAP by
  design, each explicitly UNKNOWN, zero credit;
  H2 native option-shape assumptions (cast/ability/mode/amount/declaration
  matchers) unconfirmed against live offers — first CI run is the discovery
  run; mismatches fail closed with offer diagnostics, never fall back.
- ENVIRONMENT: local XMage baseline dirty (recorded above); CI checkout is
  the sole terminal-evidence venue.

## 4. Gate status

- G49-01..G49-08: PASS (retained, re-verified source pins, no invalidation).
- G49-09: IN PROGRESS / UNKNOWN (inventory verified 107/107 obligations;
  runner v1 + workflow committed; zero behavior verdicts executed).
- G49-10..G49-14: NOT_RUN (blocked on G49-09).

CONSTRUCTION_CREDIT = 107/107 (retained, unchanged)
BEHAVIOR_CREDIT = 0/107
HISTORICAL_SUCCESSOR_RUNTIME_IMPORTED = 0
FALLBACK_COUNT = 0
XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = false
AF07 = NOT_CLAIMED
ARCHITECTURE_FREEZE = NOT_CLAIMED

## 5. Exact next action

Push this checkpoint (inventory script, behavior runner v1, behavior
workflow, this file) to `ws49/xmage-v1.0.5-successor-qualification`, let CI
execute `WS49 XMage v1.0.5 Full107 Behavior` (run 1 = discovery), then:
(a) triage per-record fail-closed diagnostics into FIRST-causal-defect
buckets (selector-shape mismatch vs terminal-checker gap vs genuine
provider/engine defect); (b) extend matchers/checkers with impact notes;
(c) re-run full 107 from record 1 until legitimate 107/107 PASS or a proven
terminal blocker. Do NOT rerun construction/normalization for reassurance.

COVERAGE_PROMOTION=FALSE. TURN_STATUS=INTERRUPTED (workstream continues).
TASK_COMPLETE=NO. WS49=INCOMPLETE (G49-09→G49-14 remain).
