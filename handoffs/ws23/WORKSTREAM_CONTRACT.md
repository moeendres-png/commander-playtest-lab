# WS-23 — Forge Production Rules-Service Vertical Slice + Continue/Stop Gate

## Objective

Convert the completed WS-19 isolated fail-closed Forge shell into a real engine-backed Rules Service far enough to determine whether Forge can own a persistent Magic game, expose Forge-authoritative legal player choices, round-trip exact native choices, and emit actor-scoped observations through the independent WS-10R boundary without GUI/AI/default behavior or proprietary legality reconstruction.

## Inputs

- WS-19 completed candidate branch / Draft PR #135.
- WS-10R provider-neutral Rules Service Protocol and AF00–AF11 qualification contract.
- WS-09 licensing/interoperability boundary.
- WS-05 multiplayer/Commander fixture requirements.
- WS-06 hidden-information/RNG/replay requirements.
- WS-08 proof/qualification strategy.
- WS-12 exact-main qualification framework and common fixture denominator.
- Pinned Forge candidate source.

## Authority

1. Newest direct user instruction.
2. Freshly verified repository/branch/commit state.
3. Current canonical project contracts and current canonical Magic authority for semantic expectations.
4. Runtime evidence for executed behavior.
5. Historical handoffs only as provenance.

`UNKNOWN` is not `PASS`. `PARTIAL` is not `FULL`. `NOT_RUN` is not `PASS`. `CODE_DERIVED` is not `RUNTIME_VERIFIED`.

## In Scope

- Fresh source locks and exact upstream delta recording.
- WS-19 regression preservation.
- Headless persistent Forge game/session construction in a genuine separate JVM process.
- Strict external `PlayerController` routing without GUI, AI, parent fallback, first-option, random, default yes/no, silent skip, or engine AI.
- Forge-authoritative legal-option enumeration/validation and exact native-option round trip.
- Actor-scoped Forge-side observation serialization and honeycard leakage tests.
- Bounded common-fixture vertical slice using existing canonical fixture IDs and semantics.
- Continue/Stop architecture gate.
- If the gate passes, broader 2P–5P / Commander / micro-rules / hidden-information / replay-RNG / 29-card / 135-fixture qualification.
- CI, hashes, evidence, commits, push, and a new Draft PR.

## Out of Scope

- Selecting a final Rules Core.
- Merging any PR.
- Freezing the project architecture.
- Permanently modifying upstream Forge.
- Embedding/linking GPL Forge code into the proprietary Commander Lab process.
- Copying Forge object layouts or card scripts into WS-10R/proprietary canonical data.
- Forge-only substitute fixtures that weaken common expected semantics.

## Dependencies

- WS-09 process/license boundary.
- WS-10R protocol and AF00–AF11.
- WS-19 strict-shell/source/build evidence.
- Current common-fixture manifest and expected semantics.
- Exact pinned Forge build/runtime dependencies.

## Required Deliverables

1. Fresh source locks.
2. WS-19 regression verification.
3. Real session proof.
4. Real DecisionFrame proof.
5. Strict `PlayerController` mapping.
6. Actor-observation proof.
7. Bounded common vertical-slice matrix.
8. Continue/Stop decision.
9. Broader/full-135 result if continued.
10. License/process evidence.
11. Hashes.
12. CI.
13. Draft PR.
14. `WS23_FINAL_HANDOFF.md`.

## Hard Gates

### Gate A — Real Game Session

A real persistent Forge `Game` is authoritative in the provider JVM, initially with four real seats and exact identities. No GUI and no AI. Turn/game progression must be runtime-proven or fail closed.

### Gate B — Real External Decision

Representative priority/action, target, payment/mana, combat, yes/no/modal, and reachable Commander decisions must be exposed as Forge-authoritative options. The selected protocol option must map back to the exact native Forge object/value and be validated/applied by Forge. The proprietary client may not reconstruct legality.

If a required legal-option surface can only be produced by reimplementing Forge legality externally, verdict is `FORGE_ARCHITECTURAL_STOP`.

### Gate C — Actor-Scoped Observation

The provider must serialize viewer-specific state before it crosses the process boundary. Own hand identity is visible; opponent hand identity, library order, protected face-down information, and hidden metadata in decision options are not. Public battlefield and stack information remain visible. Honeycard checks are mandatory.

### Gate D — Bounded Common Rule Paths

Execute existing common fixture IDs, at minimum: `PLAYER_COUNT_4P`, one priority, target, payment/mana, combat, trigger-order, replacement/prevention, Commander, hidden-information, replay/RNG, and one actual-card fixture if current authority permits. Expected semantics remain the common canonical semantics.

## Evidence Requirements

- Exact commit/tree/blob hashes and build inputs.
- Runtime logs/artifacts for real game/session and exact decision round trips.
- Machine-readable callback classification for every production-reachable `PlayerController` callback using only:
  - `EXTERNALLY_IMPLEMENTED`
  - `RULES_AUTOMATIC_NONDISCRETIONARY`
  - `PROVEN_UNREACHABLE`
  - `FAIL_CLOSED_UNSUPPORTED`
- Static and runtime proof that production qualification excludes `forge-ai`, `forge-gui`, `RemoteClientGuiGame`, and stock GUI/default paths.
- Viewer-scoped leakage tests with adversarial sentinel/honeycard identities.
- Common fixture IDs and expected semantics sourced from the frozen manifest.
- CI status and artifact/hash manifest.

## Stop Conditions

Return exact verdict `FORGE_ARCHITECTURAL_STOP` only when evidence shows a fundamental boundary incompatibility, including any of:

- required legal options cannot be externally represented without recreating legality outside Forge authority;
- the `PlayerController` architecture cannot sustain external player authority;
- actor-safe observation requires prohibited Forge object-model leakage;
- deterministic/replay requirements are fundamentally incompatible;
- genuine GPL process separation cannot be maintained.

An implementation bug, missing adapter work, or unexecuted test is not automatically an architectural stop; classify it as `FAIL`, `UNKNOWN`, `NOT_RUN`, or `FAIL_CLOSED_UNSUPPORTED` as appropriate.
