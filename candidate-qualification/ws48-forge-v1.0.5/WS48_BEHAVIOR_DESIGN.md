# WS-48 BEHAVIOR (G48-09) — IMPLEMENTATION DESIGN (Muse support lane)

Status: DESIGN (pending Forge clone + local execution readiness).
Authority: immutable WS-47 v1.0.5 materialization; Rules-Core ownership unchanged.

## 1. What the contract requires

For each of the 107 denominator records, natively in Forge:

1. `NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE` — reuse construction path,
   but do NOT stop (`COMMANDER_LAB_WS40_CONSTRUCTION_ONLY=0`), game continues.
2. Interpret `native_procedure` ops in order; answer `DECISION_FRAME`s by matching
   `decision_script` entries (same `causal_step_id`) against **provider-offered
   legal options only**; zero or multiple matches → FAIL_CLOSED.
3. Scripted priority passes (`NATIVE_CONTINUE_WITH_EXPLICIT_SCRIPTED_PRIORITY_PASSES...`)
   answer PASS; they are script, not fallback.
4. Collect the native event feed; verify `expected_events` (required/forbidden/
   ordering).
5. Verify `terminal_postconditions` against terminal native snapshots.
6. Negative fixtures (`fail_closed_probe` selectors): the named unsupported path
   must terminate with a typed failure; no fallback may select an option.

## 2. Provider enrichment (GPL-side Java, new script `scripts/ws48_v105_behavior_surface.py`)

Applied on top of the exact CI provider build chain (generate → bootstrap →
successor overlay → ... → stack-modes). Enumeration stays in Forge Rules Core;
enrichment is observation/description only:

- **B1 semantic option descriptors.** Every `broker.choose*` DECISION_FRAME option
  `kind` string gains a deterministic descriptor suffix, never changing the
  offered set or order:
  - `priority`: `FORGE_LEGAL_ACTION:<cardName>:<zone>:<abilityClass>:<semanticRef|null>`
    for each `getAllPossibleAbilities` result; `PASS` stays `PASS`.
  - card/object choices: `TARGET_CARD_SEMANTIC:<ref>` when bound in
    `Ws40SuccessorState.semanticCards`, else `TARGET_CARD:<name>:<zone>:<controllerPid>`.
  - players: `PLAYER:<Pid>` (seat-derived, as today).
  - modes: `MODE:<index>:<AbilitySub description>`.
  - mana pool: `MANA:<symbols>`.
  - combat damage / amount distribution: keep existing semantic strings.
- **B2 combat declaration.** Implement `declareAttackers`/`declareBlockers` on the
  external controller: enumerate natively (`CombatUtil.getPossibleAttackers`,
  `getAllPossibleDefenders`, `canAttack`/`canBlock`, `validateAttackers`), build
  the full legal-assignment set, emit as options with
  `ATTACK_ASSIGNMENT:<attRef>=<defPid>|...` labels, apply the externally selected
  one, re-validate natively. Pattern: `finalist_apply_forge_ws05_mp_combat_4_overlay.py`
  generalized (no fixture-id gating, no hardcoded sets).
- **B3 native event feed.** `@Subscribe` GameEvent bus methods on the provider
  emitting `EVENT` protocol messages with contract-prefix names
  (`spell_cast:<name>`, `resolve:<name>`, `stack_push:<name>`,
  `attacker_declared:<ref>-><Pid>`, `decision_frame:<kind>`, `fail_closed:<code>`,
  `commander_cast`, `commander_zone_event`, `mana_paid:<symbols>`, ...).
  Event emission is observation; game semantics untouched.
- **B4 behavior snapshots.** After each submitted decision, emit
  `QUALIFICATION_STATE(stage=behavior_checkpoint)` with a live-game snapshot:
  all battlefield/hand/graveyard/exile/stack/command cards with semantic refs
  where bound + native descriptors otherwise, life/tapped/counters/P-T, turn/phase/
  priority, stack contents. Reuses `Ws40SuccessorState` readers; new objects
  (tokens/copies) appear with native descriptors (no fabrication of semantic ids).
- **B5 negative-probe gate.** `COMMANDER_LAB_WS48_UNSUPPORTED_FAMILY=<family>` makes
  `broker.choose` for that decision family throw
  `ControlledStop("UNSUPPORTED_DISCRETIONARY_DECISION:<family>")` instead of
  emitting a frame. Typed fail-closed, provider-side.
- **B6 trigger ordering.** `orderSimultaneousSa` with >1 SA: enumerate natively,
  emit labeled options, apply selected relative order (creation stays simultaneous).
  Same pattern for pile/partition/scry/announce-X/replacement/choose-use frames
  as the corresponding fixtures demand (driven by failing-first implementation).

Fail-closed invariants: unknown op, unmatched frame kind, zero/multiple semantic
matches, unbound semantic ref, any `forge.ai`/`forge.gui` import → hard failure.
`! grep -REn 'import forge\.(ai|gui)'` stays in the build recipe.

## 3. Python driver (new `candidate-qualification/ws48-forge-v1.0.5/run_fresh_behavior_107.py`)

Reuses `run_strict_no_echo_gate` transport + construction env builders with
`CONSTRUCTION_ONLY=0`, `STOP_AFTER_PRIORITY=100000`.

- Session loop handles `SESSION_CREATED` / `QUALIFICATION_STATE` (snapshots +
  observation) / `DECISION_FRAME` (dispatch by kind to selector matcher) /
  `EVENT` (append to feed) / `SESSION_RESULT`.
- Selector matchers (one per `selector_kind`): `semantic_action` (cast /
  cast_commander / activate?), `semantic_object(s)`, `semantic_player`,
  `semantic_stack_object` (`stack:<n>` = nth stack object top-down? verify against
  MICRO records), `semantic_mode_key` (contract key ↔ native mode description map
  built per fixture from card rules text — match must be against offered options;
  key→description binding needs care: provider offers descriptions, harness maps
  key via card-text knowledge. This is matching, not legality: the offered set is
  authoritative; ambiguous map → FAIL_CLOSED), `semantic_choice_key`,
  `semantic_ability_key`, `boolean`, `integer`, `mana_payment`, `attacker_assignment`,
  `blocker_assignment`, `amount_assignment`, `order`, `partition`, `fail_closed_probe`
  (assert typed termination, never submit).
- Op interpreter walks `native_procedure`; each op declares which frames/snapshots/
  events it consumes; unexpected frames → FAIL.
- Event verifier: required/forbidden/ordering/partial-order over the feed.
- Postcondition checkers: `behavior_postconditions.py` registry keyed by normalized
  template (89 templates grouped §4); snapshot-assertions first, tapes last.
- Output: `WS48_FRESH_BEHAVIOR_107.json` (row per fixture: PASS/FAIL, event proof,
  postcondition proof, digests) + `SOURCE_LOCK` + `SHA256SUMS`. Behavior credit
  only from this report; construction/readback never imported.

## 4. Postcondition checker groups (189 posts / 89 templates)

- G-A snapshot assertions (~55 templates): zones/life/tapped/counters/P-T/cast
  counts/stack-empty/commander-damage/tax/ordering-on-stack. Generic engine +
  per-template predicate with parameters parsed from the concrete string +
  record semantic ids.
- G-B decision-log assertions (~10): "among provider-offered legal options" —
  proven by driver match records (offered-set digest + selected id).
- G-C negative probes (7+7): typed termination + absence of named fallback in feed.
- G-D hidden information (3 templates × 20): viewer-state equality + prohibited-
  metadata absence + honey-sentinel absence over emitted observation channels.
  Reuses `ws45_observation` output; needs per-viewer capture design.
- G-E replay/RNG tapes (~8): DecisionTape/EventTape/RulesRngTape recording +
  fresh-process replay equality. New provider tape emission + driver rerun.
- G-F simultaneity/APNAP/layers (~6): event-set + order assertions from feed
  with generation metadata.

## 5. Sequencing

1. Forge build + construction repro (1 → subset → 107).
2. B1+B4 + driver core + G-A/G-B checkers → first cast/resolve fixtures
   (MICRO_STACK, MICRO_PRIORITY, PILOT_PRIORITY, CARD_02).
3. B2 + combat fixtures; B6 + choice/mode/target fixtures; broaden to full 107.
4. B3 + event verifier; G-D hidden-info; G-E tapes; B5 + G-C negatives.
5. AF/CARD_02 manifests from behavior rows; RNG/replay; fallback-zero runtime probes.

## 6. Open authority questions for Terra/Sol (do NOT self-adjudicate)

- Q1: RESOLVED 2026-09-08 — denominator uses `stack:1` only where exactly one
  native stack object exists (PILOT_MANA_PAYMENT, MICRO_MANA_PAYMENT). Rule:
  resolve against live native stack listing; match iff exactly one entry;
  otherwise FAIL_CLOSED (zero/multiple match).
- Q2: mode-key → native description binding source of truth (card text parsing in
  harness is matching aid; ambiguity policy = FAIL_CLOSED, but confirm).
- Q3: per-viewer observation capture requirements for HIDDEN fixtures
  (single privileged observation vs actor-scoped projections).
- Q4: RESOLVED 2026-09-08 — no tape schema exists outside the materialization
  records themselves; tape format is provider-defined, replay-equality is the
  check. Terra/Sol adjudicate sufficiency at closeout.
