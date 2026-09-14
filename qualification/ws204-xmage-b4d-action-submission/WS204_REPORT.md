# WS204 XMage B4-D Action Submission — Report

## Authority flow (implemented)

native XMage decision callback
-> XMage-generated authoritative alternatives (controller legal_options)
-> principal-scoped generic LegalAction projection
   (`XmageFullGameActionProjection.project`)
-> external pilot chooses only an offered action
-> actor plus decision/revision plus option identity validation
   (`XmageFullGameActionProjection.toDecisionResponse`)
-> generic ActionProposal submission
   (`XmageFullGameSession.submitAction` via `XmageFullGameJsonlBridge`
   `get_legal_actions` / `submit_action`)
-> native XMage decision response (`controller.submit`)
-> native XMage engine execution.

No new legality engine. The bridge represents, validates identity and option
membership, and routes the selected option back to the exact pending callback.

## Architecture adjudication (XHIGH, verified in live source)

- `XmageFullGameDecisionController` remains the native decision
  authority/parking mechanism (decision_id, offset, actor, seat, class,
  prompt, context, min/max, legal_options, actor-scoped pilot_state, timeout,
  source_object, stable identity, wrong-actor/stale/duplicate/unknown/
  ordering/range validation; no default/random/AI answer).
- Projection maps its exact pending `legal_options` into generic
  `LegalAction` objects; a generic `ActionProposal` maps back to the exact
  current decision and option, then feeds `controller.submit()`. Legality is
  never re-enumerated elsewhere.
- Schema decision A: `choices_schema` / `metadata` / `STRUCTURAL_DECISION`
  represent every native class without loss. No model extension was required:
  `action_id` is opaque and decision-bound (`decision_id:option_id`,
  `decision_id:numeric`); `metadata` carries the exact immutable decision
  identity; `choices` carries only `decision_id`, `decision_offset`,
  `selected_option_ids`, `ordering`, `numeric_choice`. `proposal_id` is never
  treated as revision. `action_type` is representational only; inexact cases
  use `structural_decision` plus explicit metadata rather than a lie. No new
  `ActionType` was needed.
- Lane relationship: both lanes survive with one shared representation
  boundary. The compat lane (`JsonlBridge`/`XmageGameManager`/
  `ExternalDecisionController`/`XmageActionExecutor`) owns variable 2–5P pods,
  multi-game processes, B3 upkeep handoff, audit event log. The full-game lane
  (`XmageFullGameJsonlBridge`/`XmageFullGameSession`/`XmageFullGamePlayer`/
  `XmageFullGameDecisionController`) owns decision-complete 17-class external
  pilots, seeded `RandomUtil`, one-game-per-process 4P conformance. Collapsing
  either direction would weaken correctness. No contradictory legality source
  exists: the sole legality source in each lane is live XMage
  (`getPlayable`/`possibleTargets`/engine-supplied option sets);
  `LegalAction` is a read-only projection in both, and pilots/adapters may
  rank but never invent `action_id`s.

## Generic Protocol-2 boundary

`get_legal_actions` returns only the exact currently pending full-game
decision (exact actor, exact decision identity/revision, every offered native
option, principal scoping, no fabrication, no other actor's hidden
information). `submit_action` requires the exact current decision/revision,
exact actor, and a `legal_action_id` corresponding to an offered option, and
rejects stale, wrong-actor, unknown-action, prior-decision options,
duplicates, replays (via advancement-staleness), malformed proposals,
action-type mismatches, forbidden target/mode smuggling, out-of-range
numerics, and orderings containing unknown options. Only the selected
authoritative option is translated into the existing `DecisionResponse`;
XMage executes natively. The caller cannot specify a requested result and ask
the bridge to search/filter for it: any `requested_result`-style choice key is
rejected as a forbidden choice field.

## Player callback inventory gate

See `PLAYER_CALLBACK_INVENTORY.json`. All 17 decision families plus mulligan,
cast-choice, land-or-spell, targets, mana, X/numeric, modes, piles,
replacement/trigger ordering, attackers/defenders, blockers are
`EXTERNALIZED`. `chooseRingBearer` and `getMultiAmount` are
`EXTERNALIZED_VIA_DELEGATION` with pinned-`cfc36f` bytecode proof (they call
only already-externalized `chooseUse`/`Target.choose` and
`getMultiAmountWithIndividualConstraints`). `shuffleLibrary`/coins/dice are
`RULES_RANDOMNESS` (XMage-owned). `abort`/`skip`/`copy` are
`NON_DISCRETIONARY`. `sideboard`/`construct`/`pickCard` were already
`FAIL_CLOSED_UNSUPPORTED`. WS204 adds explicit fail-closed `concede(Game)`
(previously the single inherited discretionary default that would silently
mark loss). `INHERITED_DEFAULT_REACHABLE` is empty. `UNKNOWN` is empty.

## Decision families (20-kind census, NON-SCORING reachability)

Fresh WS204 head census (`DECISION_KIND_CENSUS.json`, RogShai, seed 7017,
generic transport, 120 decisions, budget stop): OBSERVED (reachability only)
= `pass`/`priority`, `hidden-zone selection`/`choose_object` (including the
sealed turn-1 cleanup discard now ANSWERED through the generic boundary),
`mana payment`/`mana_payment` (2 offers answered), `choice` (1 offer
answered), `choose_use` (1 offer answered), `mulligan`. Each observed family
has native callback plus decision class plus option counts plus projection
plus submission plus native advancement evidence in `transport_evidence` and
in `XmageFullGameGenericActionSubmissionTest` (mulligan keep, priority pass,
cleanup discard with stale/wrong/unknown negative controls that leave the
native decision unadvanced, plus replay-stale).
NOT_OBSERVED in this run (transport implemented and unit-proven for all 17
classes in `XmageFullGameActionProjectionTest`, but no engine offer in this
120-decision RogShai line): `cast` beyond the observed `choice` frame,
`targets`, `activate`/`mana source` beyond priority offers (pass/activation
policy reaches offers only when the engine deals them), `X`/`amount`,
`replacement ordering`, `trigger ordering`, `modes`, `copy choices` beyond
the observed `choice` frame, `search` beyond `choose_object` frames (D2 grant
lifecycle proven separately by `Ws92D1D2D3ProjectionTest`), `attackers`/
`defender per attacker`/`blockers` beyond declaration frames (attack policy
opens them when the engine deals combat), `combat damage assignment`
(core boundary, no Player hook), `alternate cost` beyond key-mode `choice`
handling, `Commander movement` beyond `choose_use`, `concession`
(explicitly fail-closed, core boundary). The sealed WS92/WS203 baseline
census shape is reproduced exactly by rerun (`WS203_BASELINE_CENSUS_RERUN.json`:
37 answered, stop on cleanup discard, 3 classes) — base preserved, zero
behavior credit, `GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0`.

Per-family transport disposition:

- CAST: transport PASS (choice/cast_ability projects to structural_decision
  with card metadata; submission validated); runtime OBSERVED once as
  `choice` (1 offer) in this run.
- TARGETS: transport PASS (choose_targets projection; UUID domain preserved);
  NOT_OBSERVED as a dedicated `target` offer in this run.
- MANA_PAYMENT: transport PASS plus runtime OBSERVED (2 offers answered,
  pool-before-tap policy preserved representationally, affordability never
  recomputed).
- ACTIVATE: transport PASS (priority abilities classify to
  play_land/activate_ability from XMage ability metadata); offers arise inside
  `priority` frames.
- MANA_SOURCE: transport PASS (same priority frame; mana vs non-mana
  preserved in metadata).
- X_CHOICE: transport PASS (numeric-only structural action with
  numeric_min/max; range enforced); NOT_OBSERVED as `announce_x` in this run.
- REPLACEMENT_ORDERING: transport PASS (index-mapped options; ordering
  membership enforced); NOT_OBSERVED in this run.
- TRIGGER_ORDERING: transport PASS; NOT_OBSERVED in this run.
- MODES: transport PASS (choose_mode with mode UUID domain); NOT_OBSERVED
  in this run.
- COPY_CHOICES: transport PASS via key-mode/plain `choice` projection
  (D4 preserved); OBSERVED once inside the `choice` frame in this run.
- SEARCH: transport PASS with D1/D2 redaction and look-window semantics
  preserved (projection copies only the already-redacted pending offer, never
  `pilot_state`); library-scoped offers not dealt in this run beyond
  `choose_object` frames.
- ATTACKERS: transport PASS (per-attacker hold/declare with defender domain
  from `canAttack`); no combat declaration dealt in this 120-decision line.
- DEFENDER_PER_ATTACKER: transport PASS (defender leg inside the attacker
  frame); same run cause as attackers.
- BLOCKERS: transport PASS (0..max multi-select via `choices`
  membership; empty selection supported for min 0); no declaration dealt in
  this run.
- COMBAT_DAMAGE_ASSIGNMENT: core boundary, engine-default, no Player hook;
  see `XMAGE_ENGINE_CORE_REMEDIATION_REQUIRED.md`.
- ALTERNATE_COST: transport PASS via key-mode `choice_key` metadata; observed
  only insofar as the single `choice` frame covers the mechanism.
- COMMANDER_MOVEMENT: transport PASS via `choose_use`; OBSERVED once as a
  `choose_use` frame in this run (movement semantics themselves not claimed).
- CONCESSION: explicitly fail-closed; core boundary; see remediation file.
- PRINCIPAL_SCOPING: PASS (actor-bound projection, redacted labels/metadata,
  no `pilot_state` in actions, wrong-actor/another-principal rejected).
- STALE_DECISION_REJECTION: PASS. WRONG_ACTOR_REJECTION: PASS.
  UNKNOWN_OPTION_REJECTION: PASS. REPLAYED_SUBMISSION_REJECTION: PASS (via
  advancement-staleness; revision precedes actor so replays are unambiguously
  stale).

Negative-path matrix (all fail closed, covered by
`XmageFullGameActionProjectionTest` plus
`XmageFullGameGenericActionSubmissionTest` plus
`XmageFullGameGenericBridgeTest`): no pending decision; stale identity;
stale offset; wrong actor; unknown option; prior-decision option; duplicate
option; replay; malformed (blank/missing/malformed action id, non-object
choices, non-string selections); action-type mismatch; forbidden target;
forbidden mode; forbidden choice key (`requested_result`); out-of-range
numeric; missing required numeric; unauthorized numeric; ordering with
unknown option; hidden `pilot_state` leakage (asserted absent); another
principal; advancement-during-stale; unsupported callback (`concede`,
unknown message); terminal/no-pending; second game in the same full-game JVM
(bridge rejects `full_game_process_already_used`; second concurrent pending
rejected by the controller guard).

## Authority invariants

REQUESTED_OPTION_FILTERING = ABSENT. INTERNAL_XMAGE_AI_AUTHORITY = ABSENT
(human-mode player, automation settings disabled, no AI answer in the
controller). GUI_DEFAULT_AUTHORITY = ABSENT (no default yes/no, no silent
skip, no parent fallback left reachable). SECOND_RULES_ENGINE = ABSENT
(projection is representational; costs/targets/modes/combat domains come only
from XMage offers; affordability, legality, and execution stay native).

## Regression gates

D1_GRANTED_LIBRARY = PASS. D2_LOOK_GRANT_LIFECYCLE = PASS.
D3_STATE_PROJECTION = PASS. D4_CHOICE_REDACTION = PASS.
D5_STABLE_ORDERING = PASS. D5_TWIN_EQUALITY = UNKNOWN (no fresh same-seed
twin comparison claimed). FULL107 = NOT_RUN. Maven verify 88/88 green (63
baseline preserved plus 25 new). Python subset 75 passed plus decision-matrix
19 passed. Ruff PASS. Compat `XmageProvider` capability flags unchanged
(false/false). Full-game generic flags remain false/false: decision-scoped
transport exists and is proven, but global free-standing promotion is
withheld because the lane advertises a pending-decision scope, not a
GameState-complete API matching the Python adapter contract.

## Terminal evidence fields

WS204_XMAGE_B4D_ACTION_SUBMISSION = IMPLEMENTED (decision-scoped generic
transport over the native full-game authority; 17-class unit proof plus
5-class actual-card transport proof; 2 core boundaries documented).
SOURCE_LOCK = pinned above. WS203_BASE_PRESERVED = PASS (baseline census
rerun identical). XMAGE_ENGINE_PIN_PRESERVED = PASS.
D1_GRANTED_LIBRARY = PASS. D2_LOOK_GRANT_LIFECYCLE = PASS.
D3_STATE_PROJECTION = PASS. D4_CHOICE_REDACTION = PASS.
D5_STABLE_ORDERING = PASS. D5_TWIN_EQUALITY = UNKNOWN.
FULL_GAME_GENERIC_LEGAL_ACTIONS = PASS (decision-scoped).
FULL_GAME_GENERIC_ACTION_SUBMISSION = PASS (decision-scoped).
COMPAT_BRIDGE_CAPABILITY_FLAGS = false/false (unchanged).
FULL_GAME_CAPABILITY_FLAGS = false/false (promotion withheld per gate).
PLAYER_CALLBACK_INVENTORY = complete (see JSON; zero inherited-default,
zero unknown). CAST = TRANSPORT_PASS/RUNTIME_OBSERVED_AS_CHOICE.
TARGETS = TRANSPORT_PASS/NOT_OBSERVED_THIS_RUN. MANA_PAYMENT =
TRANSPORT_PASS/RUNTIME_OBSERVED. ACTIVATE = TRANSPORT_PASS (inside
priority). MANA_SOURCE = TRANSPORT_PASS (inside priority). X_CHOICE =
TRANSPORT_PASS/NOT_OBSERVED_THIS_RUN. REPLACEMENT_ORDERING =
TRANSPORT_PASS/NOT_OBSERVED_THIS_RUN. TRIGGER_ORDERING =
TRANSPORT_PASS/NOT_OBSERVED_THIS_RUN. MODES = TRANSPORT_PASS/NOT_OBSERVED.
COPY_CHOICES = TRANSPORT_PASS/OBSERVED_AS_CHOICE. SEARCH =
TRANSPORT_PASS/D1_D2_PRESERVED/NOT_DEALT_THIS_RUN. ATTACKERS =
TRANSPORT_PASS/NOT_DEALT_THIS_RUN. DEFENDER_PER_ATTACKER =
TRANSPORT_PASS/NOT_DEALT_THIS_RUN. BLOCKERS = TRANSPORT_PASS/NOT_DEALT.
COMBAT_DAMAGE_ASSIGNMENT = CORE_BOUNDARY. ALTERNATE_COST =
TRANSPORT_PASS/OBSERVED_AS_CHOICE_MECHANISM. COMMANDER_MOVEMENT =
TRANSPORT_PASS/OBSERVED_AS_CHOOSE_USE_FRAME. CONCESSION = FAIL_CLOSED
(CORE_BOUNDARY). PRINCIPAL_SCOPING = PASS. STALE_DECISION_REJECTION = PASS.
WRONG_ACTOR_REJECTION = PASS. UNKNOWN_OPTION_REJECTION = PASS.
REPLAYED_SUBMISSION_REJECTION = PASS. REQUESTED_OPTION_FILTERING = ABSENT.
INTERNAL_XMAGE_AI_AUTHORITY = ABSENT. GUI_DEFAULT_AUTHORITY = ABSENT.
SECOND_RULES_ENGINE = ABSENT. DECISION_KIND_CENSUS_20 = non-scoring
artifact in `DECISION_KIND_CENSUS.json` (6/20 observed this run; remainder
classified per run cause, not as behavior). GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0.
FULL107 = NOT_RUN. RAW_GIT_PUSH_USED = NO. ARCHITECTURE_FREEZE = NOT_CLAIMED.
PRODUCTION_PROVIDER = NOT_SELECTED.
