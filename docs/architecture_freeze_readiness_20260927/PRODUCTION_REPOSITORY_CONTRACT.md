# Production Repository Contract (PRE-FREEZE PROPOSAL — repository NOT created)

Status: proposal prepared by WSR24. The private production repository MUST NOT
be created until the Coordinator claims Architecture Freeze (SLOT-10). This
contract binds the bootstrap that follows Freeze.

## 1. Single authoritative Rules Core

- Exactly one Rules provider process, running the Frozen ADR pin
  (repository + commit + tree + build artifact + SHA-256).
- The Rules Core alone owns: legal actions, costs, mana, stack, priority,
  targets, modes, choices, combat, triggers, replacement/prevention,
  continuous effects/layers, state-based actions, zones, copy/control,
  Commander rules, multiplayer rules, Rules randomness.
- No second Rules Engine anywhere: no pilot legality, no adapter legality, no
  orchestration legality, no qualification-helper legality, no test-helper
  legality on production-reachable paths.

## 2. Responsibility separation (binding)

| Component | Owns | Must NEVER |
|---|---|---|
| Rules Provider | Authoritative Rules service/process: game state, legality, RNG, events | Expose hidden info across principals; accept non-offered actions |
| Provider Adapter | Protocol translation ONLY: envelope mapping incl. the Coordinator-approved decision-identity shim (SLOT-03) | Infer/reconstruct/fabricate legality; choose options; default |
| Observation Boundary | Principal-scoped projection ONLY (per SLOT-04 channel scope) | Leak across principals in state, logs, errors, evidence |
| Decision Boundary | Engine-generated options → external selection → exact submission; stale/unknown fails closed | Filter-then-reconstruct legality; silent skip; fallback choice |
| Pilot | Discretionary strategy ONLY among offered options (may choose poorly, never invent) | Any legality inference; harness-side RNG |
| Orchestration | Process lifecycle + batching ONLY | Decide, observe beyond lifecycle needs, mutate games |
| Replay | Decisions + Rules RNG + semantic events + terminal state → deterministic rebuild | Claim replay without a clean-process twin |

## 3. Directory / module boundaries (proposal)

```text
rules-provider/        # pinned engine + bridge; built from Frozen ADR pin
adapter/               # provider-specific envelope translation + shim + fail-closed tests
contracts/             # versioned schemas: observation, legal-action, decision,
                       #   target/mode/choice, RNG, replay, failure envelopes
pilot/                 # discretionary strategy; consumes contracts, offers no legality
orchestration/         # process lifecycle, batch runner, isolation controls
replay/                # tape writer/reader, checkpoint + state-hash verification
qualification/         # gates, fixtures, requalification impact tooling (WSR24 validators vendored)
evidence/              # sealed runs (hashes, identities; no hidden-info leakage)
```

Dependency direction (strict, enforced by import/lint rules):
`pilot → contracts ← adapter → rules-provider`; `orchestration → {adapter,
replay}` for lifecycle only; `replay → contracts`; nothing → pilot for
decisions except orchestration's game assignment. `rules-provider` depends on
nothing in-repo except its pinned upstream sources.

## 4. Interfaces (each versioned; breaking change = new version + requalification)

- `contracts/observation/vX`: principal-scoped state schema.
- `contracts/legal-actions/vX`: engine option envelope schema.
- `contracts/decision/vX`: submission envelope incl. decision-identity field.
- `contracts/target-mode-choice/vX`: target/mode/choice sub-schemas.
- `contracts/rng/vX`: seed-binding record schema.
- `contracts/replay/vX`: tape + checkpoint + state-hash schema.
- `contracts/failures/vX`: typed failure envelopes (retryable flag, mutation
  guarantee, evidence obligation).

## 5. Failure contracts

Every cross-boundary call returns either success with engine-attributed data
or a typed failure from `contracts/failures/vX`. Unsupported
production-reachable paths fail closed (typed UNSUPPORTED, no mutation, no
default). Provider-process crash/timeout/protocol failure terminates the game
as a recorded terminal failure with its evidence bundle; orchestration
restarts nothing mid-game.

## 6. No-fallback invariants (CI-enforced)

- N1: No first-option / random-option / default yes-no choice on any
  production-reachable path (adversarial tests required).
- N2: No silent skip of an engine-offered decision.
- N3: No engine-internal AI substituting for external decision control
  (`external_control=true` mandatory at game creation; fail-closed test when
  omitted — carries PB-01 forward).
- N4: No GUI/default selections; headless only.
- N5: No manual outcome injection; no direct `resolve()` substitutes.
- N6: No harness-side RNG on production-reachable paths.
- N7: No hidden-information leakage across principals (honeycard negatives).
- N8: No `freeze_eligible=true` unless schema-validated all-PASS (WSR24
  validators vendored into `qualification/`).

## 7. Test boundaries

- Contract tests: schema validation + adversarial negatives per contract.
- Adapter tests: envelope translation incl. shim provenance (submitted
  identity byte-matches the offering frame) + fail-closed matrix.
- Provider tests: engine-owned behavior via the bridge (no Rules
  reimplementation in expectations beyond the frozen fixtures).
- Pilot tests: strategy only against scripted option sets (never live legality).
- Replay tests: clean-process twins per fixture (carries PB-08 forward).
- Isolation tests: one-game-per-process enforcement; cross-game state
  separation negatives.

## 8. Process topology

One provider process per game; adapter + pilot outside the provider process;
orchestration supervises lifecycle only. Resource limits and sandboxing per
the Frozen ADR PROCESS_ISOLATION. Batch execution is process-isolated per
game (no shared mutable engine state across games).

## 9. Governance (installed at bootstrap, before any implementation)

Source-lock mechanism (commit/tree/artifact/SHA-256 recording per build),
evidence-sealing procedure, no-fallback CI gates (N1–N8), and the
requalification impact rule: historical PASS survives only after impact
adjudication + required reruns (see SELECTED_PROVIDER_IMPACT_TEMPLATE.md).
