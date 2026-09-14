# WS205 Method — qualification-only First-Wave driver

## Control path (decision-scoped generic boundary only)

Per-slot game (one fresh JVM per game, twin = another fresh JVM):

1. `XmageFullGameSession.legalActionsPayload()` — projects ONLY the exact
   currently pending native decision (`decision_scoped=true`,
   `global_capability_promoted=false`).
2. `ws205-pilot-v1` selects among the offered `actions` only.
3. Generic `ActionProposal` via `XmageFullGameSession.submitAction()`.
4. Native `XmageFullGameDecisionController.submit()` + native XMage execution
   + `awaitDecisionAdvance`.

Forbidden in the qualification path: `get_full_game_decision` /
`submit_full_game_decision` native verbs, requested-result filtering,
fabricated actions, Lab-side legality, manual outcome injection,
`sa.resolve()` / `AbilitySub` substitutes, XMage AI, GUI defaults.

## `ws205-pilot-v1` semantics (recorded per run as `decision_policy_version`)

- `mulligan`: always keep (preserves crafted scenario decks; deterministic).
- `priority`: scenario wish-list match (cast/activate named cards) else
  play-land if offered and actor lands-in-play < `play_land_max`, else pass.
- `declare_attacker`: scenario wish-list match else hold.
- `declare_blocker`: scenario wish-list match else empty selection.
- `choice` / `target` / `choose_object` / `choose_use` / `mode` / `pile` /
  `replacement_effect` / `trigger_order`: scenario wish-list match
  (case-insensitive substring over offered display label + metadata) else
  lexicographically smallest offered `action_id`.
- `mana_payment`: smallest non-cancel offered action, else smallest offered.
- `announce_x` / `amount` / `multi_amount` / `target_amount`: scenario value
  clamped to offered `numeric_min..numeric_max`, else schema minimum.
- Unknown decision class: fail closed (stop with `unhandled_decision_class`).
- Wish-list entries may name desired semantic choices ONLY as match patterns
  over authoritative offered options. No filtering by requested result, no
  independent legality. A wish-list miss falls back to the neutral rule and is
  recorded; it never invents an action.

Tie-breaks are explicit, deterministic, and recorded — never silent
first/random/default authority: every selection is an XMage-offered option.

## Scenario setup

- `NATURAL_GAME_START`: crafted 100-card Commander decks (scenario cards +
  basic-land filler, legal commander) played natively from turn 1 through the
  generic loop. No teleportation (`scenario_injection_supported=false`).
- `PRE_STEP_NATIVE_PROGRESSION`: same, plus native progression to
  `DECLARE_ATTACKERS` through the loop. No step teleport.
- `PRE_DECISION_CONSTRUCTION`: pre-first-decision seeding only, zero credit;
  no qualified mechanism exists in this lane, so such slots classify the setup
  boundary fail-closed unless native play reaches the state.
- Seeds: neutral per-slot rule `seed = 9100 + slot_index` (1..15) plus
  `+ 1000` for no-humility/clone-first H01 control constructions. Seeds are
  fixed BEFORE execution and never optimized for outcome (seed-shopping would
  be requested-result filtering).

## Evidence and classification

- Per decision: offset, class, actor seat, offered count + option-type
  histogram, selected offered label, native advancement. (`PILOT_VISIBLE`.)
- Terminal assertion state (battlefield permanents with
  name/controller/P/T/copy-flag, graveyards, life, hand/library counts —
  never hidden contents) is `QUALIFICATION_ASSERTION_ONLY`, never pilot input.
- Reachability (`REACHED`/`BLOCKED`/`UNKNOWN`) and behavior
  (`PASS`/`FAIL`/`BLOCKED`/`UNKNOWN`) classified separately. Reachability
  never promotes to behavior. Construction/import/readback never scores.
- `PASS` additionally requires: actual cards, sealed scenario binding,
  observed native decision path, selection from authoritative options, native
  advancement, required observable behavior, no falsifiers, principal scoping,
  required negative controls, exact head/engine/seed binding.
- Failure classes: `RULES_BEHAVIOR_FAIL`, `TRANSPORT_FAIL`, `HARNESS_FAIL`,
  `SCENARIO_SETUP_BLOCKER`, `ENGINE_CORE_BLOCKER`, `AUTHORITY_GATE`,
  `INFRASTRUCTURE_BLOCKER`, `UNKNOWN`.

## Twin gate

Same seed + same decks + same scenario + recorded external semantic decision
stream, fresh JVM. Twin follows the primary's recorded stream (same offset +
class ⇒ same semantic label among offered); divergence fails the gate.
Semantic transcript normalization (Python): drop process-local identities
(raw UUIDs, decision/prompt ids, private state refs); keep class, offset,
actor seat, offered counts/types, selected labels, state transitions, life,
zones, copy identity. `bit_exact_replay_validated` stays `false`.

## Negative controls

Per slot (mid-run probes at the 2nd pending decision where applicable):
wrong-actor and unknown-option submissions must reject without advancing the
native decision. Stale/replay/ordering/range boundaries are covered by the
freshly rerun WS204 generic battery (88-test green in WS205).
