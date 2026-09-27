# WS80 Final Report — XMage Callback / Entrypoint Reachability + Fail-Closed Hardening

## Objective

For every currently supported XMage entrypoint, determine which discretionary
Player callbacks and Rules-randomness callbacks can actually be reached, which
component owns them, and what happens on an unsupported callback — then ensure
claimed full-game paths externalize decisions or fail closed, compatibility
paths cannot silently acquire broader production meaning, unsupported surfaces
do not return tactical defaults, Rules randomness remains XMage-owned, and
capability reporting matches reachability.

## What was done

1. XHIGH read-first adjudication (`foundry-adjudicator`) enumerated actual
   process entrypoints, traced Player implementations, mapped capability claims
   to reachable callbacks, identified the first production-reachable
   discretionary default, distinguished bounded historical compatibility from a
   genuine production-path defect, and challenged the hypothesis that
   `XmageBridgePlayer` needed modification. Findings persisted in the state
   file.
2. Minimal remediation: single `failIfExternallyControlled` guard in
   `XmageBridgePlayer` (`UNSUPPORTED_COMPATIBILITY_DECISION` via
   `XmageGameManager.GameException`) on the B4 externally controlled path,
   plus explicit `chooseAbilityForCast` / `chooseLandOrSpellAbility` overrides
   and a narrow `isStartingPlayerInitChoice` exception for validated
   `GameImpl.init` starting-player selection. Null-controller B3/Phase6
   behavior preserved byte-identically.
3. New `XmageBridgePlayerFailClosedTest` (5 tests): reflection boundary proving
   every discretionary Player callback is overridden or explicitly audited as
   `{chooseRingBearer, getMultiAmount}` delegation; fail-closed proof for all
   21 guarded surfaces; observable-old-default proof (announceX min, getAmount
   min, replacement 0, null trigger/mode, no-op combat); null-controller
   bounded-behavior preservation.
4. Machine-readable outputs in `qualification/ws80-xmage-callback-reachability/`:
   source lock, entrypoint reachability, callback inventory, capability mapping,
   risk matrix, adjudication, validation, final report, state, and a
   deterministic verifier (`verify.py`).

## Changes

- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageBridgePlayer.java`:
  imports for `ActivatedAbility`/`SpellAbility`; `failIfExternallyControlled`
  plus `isStartingPlayerInitChoice`; guards on 19 discretionary stubs plus 2
  new inherited-choice overrides; updated class Javadoc.
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageBridgePlayerFailClosedTest.java`:
  new boundary and negative tests (no production logic).
- `qualification/ws80-xmage-callback-reachability/`: 8 evidence artifacts plus
  verifier (no production semantics).
- No `Main` routing, capability, pin, full-game lane, Docker, workflow, or
  pilot-policy change. No engine repin. No capability promotion.

## Tests / Evidence

- Java `mvn verify`: 54 run, 0 failures (`XmageBridgePlayerFailClosedTest` 5,
  `XmageFullGamePlayerBoundaryTest` 4, `XmageFullGameBridgeContractTest` 2,
  `XmageFullGameInventoryTest` 1, `XmageFullGameCastChoiceTest` 1,
  `XmageExternalDecisionTest` 1, `XmageActionSubmissionTest` 1,
  `XmageEventLogLifecycleTest` 1, `XmageGameManagerTest` 10, `JsonlBridgeTest` 8,
  `XmageStateObservationTest` 1, `XmageDeckImporterTest` 10,
  `Phase6DifferentialAdapterValidationTest` 9). `RUNTIME_VERIFIED`.
- Python: 11 plus 58 passed (compat provider, full-game, decision matrix, H4
  workflow/materialization). `RUNTIME_VERIFIED`.
- Source inspection is `CODE_DERIVED` unless runtime-verified above. A unit test
  for one callback does not prove every callback; reflection plus inventory
  plus 64-decision integration bound the surface as `CODE_DERIVED`.
- Initial unconditional guard broke B4 start at starting-player selection
  (diagnostic evidence, not a stop condition); refined narrowly with
  integration proof. First Phase6 failures post-fix were `INFRASTRUCTURE_DEFECT`
  (`/tmp` full from unrelated workstreams); rerun with isolated
  `java.io.tmpdir` passed.

## Verdicts

- `ENTRYPOINT_INVENTORY=PASS`
- `CALLBACK_INVENTORY=PASS`
- `PRODUCTION_REACHABLE_DEFAULT_DECISIONS=0`
- `FULL_GAME_FAIL_CLOSED=PASS`
- `RULES_RANDOMNESS_ENGINE_OWNED=PASS` (full-game; compat explicitly not owned
  by design, documented as not evidence)
- `CAPABILITY_TRUTH=PASS`
- `ENGINE_PIN_CHANGE=0`
- `BEHAVIOR_CREDIT_CHANGE=0`
- `ARCHITECTURE_FREEZE=NOT_CLAIMED`
- `PRODUCTION_PROVIDER=NOT_SELECTED`

No XMage provider-wide qualification, RQ-C3 promotion, or Full107 credit is
claimed.
