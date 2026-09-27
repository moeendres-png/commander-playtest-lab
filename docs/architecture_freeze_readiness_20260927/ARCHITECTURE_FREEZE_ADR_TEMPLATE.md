# Architecture Freeze ADR — TEMPLATE (provider-neutral, Coordinator-fill required)

Status: DRAFT TEMPLATE. This file claims nothing. Every
`【COORDINATOR-FILL: …】` location must be completed by Sol High at Freeze time.
No `freeze_eligible=true` record may reference this template until all fills
are bound to PASS-grade evidence satisfying
`architecture_freeze_contract_v2.schema.json`.

How to finalize: copy this template to `docs/architecture_freeze/ADR.md` in
the production-bootstrap context, replace every `【COORDINATOR-FILL】` block,
attach the evidence files named in QUALIFICATION_EVIDENCE, and validate the
resulting freeze-result record against the schema with the WSR24 validators
(`tests/qualification/test_wsr24_freeze_readiness.py`).

---

## 1. RULES_CORE

【COORDINATOR-FILL: RULES_CORE — the single authoritative Rules engine:
XMage or Forge. Exactly one.】

- Role: sole authority for legal actions, costs, mana, stack, priority,
  targets, modes, choices, combat, triggers, replacement/prevention,
  continuous effects/layers, state-based actions, zones, copy/control,
  Commander rules, multiplayer rules, and Rules randomness.
- Non-authorities (explicit): adapter, pilot, orchestration, replay tooling —
  none of these may infer, reconstruct, or invent legality.

## 2. PRODUCTION_PROVIDER

【COORDINATOR-FILL: PRODUCTION_PROVIDER — must equal RULES_CORE.】

`PRODUCTION_PROVIDER = NOT SELECTED` until this fill is executed.

## 3. ENGINE_REPOSITORY

【COORDINATOR-FILL: ENGINE_REPOSITORY — exact upstream repository URL.】

## 4. ENGINE_COMMIT

【COORDINATOR-FILL: ENGINE_COMMIT — exact 40-hex commit SHA.】

Pre-qualified candidates (for reference only, not selection):
XMage `b19596980f2734496ea1896504253e1bdd2756dd`;
Forge `ef958ee91ac6c9ce0152189f2654bf6e05abf273`.

## 5. ENGINE_TREE

【COORDINATOR-FILL: ENGINE_TREE — exact 40-hex tree SHA of the pinned checkout.】

## 6. ENGINE_BUILD_ARTIFACT

【COORDINATOR-FILL: ENGINE_BUILD_ARTIFACT — exact artifact identity
(e.g., jar path / image reference / bridge version string).】

## 7. ENGINE_BUILD_SHA256

【COORDINATOR-FILL: ENGINE_BUILD_SHA256 — exact 64-hex SHA-256 of the built
artifact bytes. For Forge, see SLOT-05: either a build-derived binding or the
Coordinator-accepted provenance file recorded here.】

## 8. PROTOCOL_VERSION

`2.0.0` (fixed by the qualification boundary
`commander-lab.pre-freeze-qualification/2.0.0`).

## 9. PROTOCOL_SCHEMA_IDENTITY

`git-blob:ea8651f75a1461ecc41dc1f24586c00bff97fee5`
(source: `schemas/engine_adapter_protocol.schema.json`).

## 10. BRIDGE_ARCHITECTURE

【COORDINATOR-FILL: BRIDGE_ARCHITECTURE — selected provider's bridge mechanics:
transport (stdin/stdout JSONL), request envelope convention (payload vs params
as implemented), decision-identity fields, fail-closed codes. Must reference
the SLOT-03 shim ruling.】

- The bridge carries provider frames unchanged; the adapter normalizes only
  the decision-identity envelope per the Coordinator-approved shim.
- Forbidden in bridge/adapter: legality reconstruction, fabricated options,
  first/random/default choice, silent skip, internal AI fallback, GUI
  fallback, manual outcome injection, requested-option filtering that
  reconstructs legality.

## 11. PROCESS_TOPOLOGY

【COORDINATOR-FILL: PROCESS_TOPOLOGY — exactly one provider process per game;
Lab adapter in-process or sidecar as implemented; pilot external to the
provider process. Must satisfy WS-09 (AF11).】

- One game per provider process (required for clean-process replay twins).
- No engine code embedded in Lab; no Lab Rules logic embedded in the provider.

## 12. PLAYER_COUNTS_SUPPORTED

【COORDINATOR-FILL: PLAYER_COUNTS_SUPPORTED — the counts with AF02 PASS
evidence on the production lane (expected: 2P, 3P, 4P, 5P; bounded 6P where
proven without correctness loss).】

## 13. PLAYER_COUNTS_FAIL_CLOSED

【COORDINATOR-FILL: PLAYER_COUNTS_FAIL_CLOSED — every other count (including
1P and 7P+) fails closed with a typed error; no game starts.】

## 14. HIDDEN_INFORMATION_MODEL

【COORDINATOR-FILL: HIDDEN_INFORMATION_MODEL — principal-scoped projection;
enumerate the channels proven per SLOT-04 and any deferred channels with
fail-closed behavior. Must include honeycard leakage negatives.】

## 15. OBSERVATION_CONTRACT

- Principal-scoped state reads per seat; actor-safe identities.
- No hidden-information leakage across principals in observations, logs,
  evidence, or errors.
- Schema: 【COORDINATOR-FILL: OBSERVATION_CONTRACT — schema file + version
  pinned at Freeze.】

## 16. LEGAL_ACTION_CONTRACT

- All legal options are engine-generated; the adapter transports them
  unchanged.
- Unsupported production-reachable decisions fail closed with typed errors;
  no silent skip.
- Schema: 【COORDINATOR-FILL: LEGAL_ACTION_CONTRACT — schema file + version.】

## 17. DECISION_CONTRACT

- External selection among engine-offered options; exact submission of the
  chosen option identity (per the SLOT-03 shim).
- Stale/unknown decision identities fail closed (`STALE_EXTERNAL_DECISION` or
  equivalent); no default.
- Schema: 【COORDINATOR-FILL: DECISION_CONTRACT — schema file + version.】

## 18. TARGET/MODE/CHOICE CONTRACT

- Targets, modes, and choices are decision kinds owned by the Rules Core,
  submitted through the same decision contract.
- Schema: 【COORDINATOR-FILL: TARGET_MODE_CHOICE_CONTRACT — schema + version.】

## 19. RULES_RNG_CONTRACT

- All Rules randomness originates in the Rules Core with explicit seed
  authority; no harness-side randomness on production-reachable paths.
- Seed binding recorded per game (cf. requested_seed 424242 in WSR22 probes).
- Contract: 【COORDINATOR-FILL: RULES_RNG_CONTRACT — binding mechanism +
  version. Must resolve the lane split per SLOT-06/SLOT-07.】

## 20. SEMANTIC_REPLAY_CONTRACT

- Deterministic replay from recorded seeds + authoritative Decision Options +
  relevant semantic events + terminal state.
- One-game-per-process; clean-process twins per fixture (see SLOT-09).
- Contract: 【COORDINATOR-FILL: SEMANTIC_REPLAY_CONTRACT — tape format +
  version, checkpoint format, state-hash scheme.】

## 21. FAILURE_SEMANTICS

- Typed failures: protocol mismatch, unknown message, illegal action,
  stale/unknown decision, unsupported decision class, crash, timeout —
  each with retryability, mutation guarantees (FAILED_RESPONSE_NO_GAME_MUTATION
  where applicable), and evidence obligations.
- Crash/timeout/protocol failure of the provider process ends the game as a
  recorded terminal failure; never silently resumed or re-decided.

## 22. PROCESS_ISOLATION

- Provider process sandboxing, resource limits, and lifecycle ownership
  (orchestration owns process lifecycle/batching only).
- Isolation: 【COORDINATOR-FILL: PROCESS_ISOLATION — mechanism (e.g.,
  one-game-per-process + OS process boundary + batch-runner controls).】

## 23. ACTUAL_CARD_QUALIFICATION_BOUNDARY

- Effective 29-card corpus enumerated; CARD_02 PASS at Freeze baseline.
- Corpus execution timing per SLOT-08: 【COORDINATOR-FILL:
  ACTUAL_CARD_QUALIFICATION_BOUNDARY — pre-Freeze PASS record refs, or the
  named post-Freeze slice gate carrying the corpus obligation.】

## 24. MULTIPLAYER_COMMANDER_BOUNDARY

- WS-05 MUST semantics at required cardinalities under the effective
  FULL107 successor contract (`commander-lab.full107/1.0.6-successor`).
- Mid-game fixture basis per SLOT-02: 【COORDINATOR-FILL:
  MULTIPLAYER_COMMANDER_BOUNDARY — direct-execution refs or the
  mechanism-equivalence row mapping.】

## 25. INTEROP_LICENSE_TOPOLOGY

【COORDINATOR-FILL: INTEROP_LICENSE_TOPOLOGY — XMage MIT or Forge GPL-3.0
posture; consequences for the private production repository (linking,
distribution, process-boundary implications); WS-09 satisfaction statement.】

## 26. SOURCE_LOCK

【COORDINATOR-FILL: SOURCE_LOCK — Lab repo commit/tree at Freeze; provider
repo/commit/tree; adapter source commit/tree; build artifact + SHA-256;
protocol schema blob; contract blobs. Model on
`docs/architecture_freeze_readiness_20260927/SOURCE_LOCK.json`.】

## 27. SUPPORTED_PATHS

【COORDINATOR-FILL: SUPPORTED_PATHS — explicit list: player counts, decision
classes, deck-import shapes, seed/replay support, shutdown paths. Each entry
names its evidence.】

## 28. UNSUPPORTED_PATHS

【COORDINATOR-FILL: UNSUPPORTED_PATHS — explicit list with fail-closed
behavior per path (typed error, no mutation, no default). Includes any
SLOT-04-deferred channels and non-supported player counts.】

## 29. KNOWN_BOUNDED_LIMITATIONS

【COORDINATOR-FILL: KNOWN_BOUNDED_LIMITATIONS — the PB-01/PB-02/PB-04/PB-05
class: documented, satisfiable, non-Rules gaps with their tests. Historical
UNKNOWN_IMPACT items may NOT appear here unless re-proven.】

## 30. QUALIFICATION_EVIDENCE

【COORDINATOR-FILL: QUALIFICATION_EVIDENCE — exact file/commit/blob refs for:
AF01 20-invariant run; cardinality runs; FULL107 107-row record; hidden-info
probes; RNG/replay twins; actual-card corpus; native suites; comparison and
divergence packets. WSR22 evidence may be cited by identity; only
impact-adjudicated survivors count (see SELECTED_PROVIDER_IMPACT_TEMPLATE).】

## 31. AF00_AF11_RESULTS

【COORDINATOR-FILL: AF00_AF11_RESULTS — twelve PASS verdicts with reason +
evidence_refs each, conforming to `architecture_freeze_contract_v2.schema.json`
`gate_results` (exactly 12 entries, one per gate, verdict const PASS when
freeze_eligible=true).】

## 32. FREEZE_ELIGIBILITY

【COORDINATOR-FILL: FREEZE_ELIGIBILITY — `freeze_eligible: true` with the
schema-conformant record, OR `false` with the blocking gates named. WSR24
validators reject `true` unless every gate is PASS and every required
capability is present.】

---

## Coordinator-fill checklist (all must be checked at Freeze)

- [ ] RULES_CORE / PRODUCTION_PROVIDER bound to exactly one candidate
- [ ] ENGINE pin (repository, commit, tree, artifact, SHA-256) bound
- [ ] BRIDGE_ARCHITECTURE references the SLOT-03 shim ruling
- [ ] PROCESS_TOPOLOGY satisfies AF11/WS-09
- [ ] PLAYER_COUNTS_SUPPORTED has AF02 evidence; the rest fail closed
- [ ] HIDDEN_INFORMATION_MODEL reflects the SLOT-04 scope ruling
- [ ] All six contracts (observation, legal-action, decision,
  target/mode/choice, RNG, replay) pinned to schema + version
- [ ] FAILURE_SEMANTICS and PROCESS_ISOLATION concrete
- [ ] Card/multiplayer boundaries reflect SLOT-02/SLOT-08 rulings
- [ ] INTEROP_LICENSE_TOPOLOGY states the GPL/MIT posture
- [ ] SOURCE_LOCK complete (Lab + provider + adapter + build + schemas)
- [ ] SUPPORTED/UNSUPPORTED paths explicit with fail-closed behavior
- [ ] QUALIFICATION_EVIDENCE attached by exact identity
- [ ] AF00–AF11 twelve PASS records validate against the schema
- [ ] `ARCHITECTURE_FREEZE = CLAIMED` recorded with date and Coordinator identity
