# Limitation Remediation Report — Audit Point D

Date: 2026-08-08
Baseline: `1.13.4` / `main` / `c969fef5f0e78caade87187d44524d959568d434`
Merged D implementation: PR #15 / `b70dda42778f61a8be5b62c79f39a385ad7c07e1`
Scope: technical truth/binding limitations only. No deck, inventory, opponent-content, or modeling changes.

## D register

| Component | Before | Limitation | D action | After | Remaining boundary |
|---|---|---|---|---|---|
| Structural Simulator | verified_with_limitations | Structural abstraction, not a rules engine | No modeling expansion in D | verified_with_limitations | Rules/card fidelity belongs to G/P3 |
| Mulligan Lab | verified_with_limitations | Depends on current deck/pilot context | Run identity now records deck, pilot, policy, inventory and data hashes | verified_with_limitations | Heuristic hand quality remains modeling work |
| Pilots | verified_with_limitations | Run metadata did not bind the complete pilot registry/parameters | Pilot registry and every registered `parameter_hash` are bound into run identity | verified_with_limitations | Decision quality belongs to G/P4 |
| Opponent Ensembles | verified_with_limitations | Opponent inputs could be insufficiently explicit in generic tool metadata | Opponent deck hashes plus opponent-registry hash are bound | verified_with_limitations | Synthetic/uncertain opponents remain explicitly uncertain |
| Optimizer | verified_with_limitations | Decision runs did not have a universal complete identity | Central `_invoke` metadata now binds current decision inputs and rejects mid-run drift | verified_with_limitations | Structural objective quality belongs to G/P5 |
| Counterfactual Replay | verified_with_limitations | External mode flag could suggest an external boundary without an executor | External counterfactual mode now fails closed; engine mode, validation level and result provenance must agree | verified_with_limitations | External legal-action replay requires a real engine executor |
| Diagnostics | verified_with_limitations | Claims inherit underlying run/model limits | Complete run identity is attached through the common tool boundary | verified_with_limitations | Epistemic separability remains a modeling limit |
| Threat Assessment | verified_with_limitations | Heuristic | No feature expansion in D | verified_with_limitations | G/P4 |
| Politics | verified_with_limitations | Stress/hypothesis regimes, not learned human politics | Registry hash is bound into run identity | verified_with_limitations | G/P4 |
| Primer-to-Pilot | verified_with_limitations | Existing hash scoping was good, but policy-eval could filter scenarios before proving current-deck compatibility | `run_policy_eval` now rejects `policy.deck_hash != current deck_hash` before evaluation | verified_with_limitations | Primer quality remains modeling work |
| Meta Knowledge Base | implemented_not_recently_verified / verified_with_limitations | Active meta pointer was not explicit in generic run identity | Active meta manifest and pointed snapshot hashes are bound | verified_with_limitations | Research freshness belongs to G |
| Agent Layer | verified_with_limitations | Agent claims depend on deterministic tool evidence | No separate agent-side identity system added; central tool metadata remains the source of truth | verified_with_limitations | Live LLM behavior remains non-deterministic and bounded by tools |
| Run Provenance | partial | Missing inventory, pilot-parameter, policy, meta and per-source hashes in universal tool metadata | Added complete run identity and `run_identity_hash`; source imports from `data/sync/current_sources.json` are hashed; non-mutating calls reject drift | verified_with_limitations | Cross-release canonical pointer cleanup belongs to F/H/J-P0 |
| Tactical Oracle | verified_with_limitations | Internal tactical evidence could be confused with external validation downstream | Counterfactual model validators enforce tactical vs external evidence labels | verified_with_limitations | Tactical Oracle remains non-external by design |

## Run identity after D

Every tool response produced through `CommanderToolService._invoke` now records:

- `git_commit`
- `engine_version`
- aggregate `data_snapshot_hash`
- named `data_snapshot_hashes`
- canonical `inventory_hash`
- `deck_hashes`
- `opponent_hashes`
- `opponent_registry_hash`
- `pilot_hashes`
- every registered pilot `parameter_hash`
- aggregate `policy_hash`
- active `meta_snapshot_hash`
- `scenario_hash`
- configuration hash
- seed / iterations when applicable
- composite `run_identity_hash`

The identity sources are resolved from current project registries instead of silently assuming an unversioned external state. For non-identity-mutating tools, the identity is recomputed after execution and the result is rejected if it changed during the call.

Identity-mutating authoring tools (`create_meta_snapshot`, `compile_pilot_policy`) are intentionally exempt from the after/before equality check because changing an identity source is their purpose; their response still records the pre-execution identity.

## Counterfactual truth boundary

- Structural branchpoints require `structural_model_estimates`.
- Tactical Oracle branchpoints require `tactical_oracle`.
- External branchpoints require `external_rules_engine`.
- `CounterfactualResult` rejects mismatched branchpoint/provenance validation levels.
- External-engine claims require `external_engine_used=true` plus explicit external-engine evidence.
- The current counterfactual implementation has no real external executor, so `EXTERNAL_ENGINE` execution fails closed even if an availability flag is supplied.
- Counterfactual outputs remain model alternatives and cannot be marked historical facts.

## Pilot / primer binding

The project already enforced deck hashes in compiled rules and pilot profiles. D adds the missing service-level guard: `run_policy_eval` rejects a compiled policy whose `deck_hash` differs from the requested current deck before scenario evaluation.

## Final verification

Local verification on the D patch:

- `python -m compileall -q src tests`: PASS
- `git diff --check`: PASS
- targeted D/unit regression set: 71 PASS
- complete unit suite split into two batches: 134 PASS + 104 PASS = 238 PASS
- property/golden/contract/regression: 27 PASS
- integration batch A: 8 PASS
- integration batch B: 14 PASS
- test collection: 309 tests

GitHub validation on the final focused D PR head:

- CI workflow run `31273590294`: SUCCESS
  - changed-file Ruff lint: PASS
  - changed-file Ruff format check: PASS
  - full test suite: 308 PASS, 1 SKIP, 0 FAIL
  - `compileall`: PASS
  - secret-pattern scan: PASS
  - wheel build: PASS
  - Phase 8.6 audit command executed under the existing acceptance contract
- Security job: SUCCESS
  - dependency audit: PASS
  - CycloneDX SBOM: PASS
  - license report: PASS
- Release Artifacts workflow run `31273590309`: SUCCESS
  - full suite, build, manifests/checksums and roundtrip verification: PASS
- Windows Runtime Hygiene workflow run `31273590256`: SUCCESS
  - Windows full suite and clean-tree/runtime-hygiene checks: PASS

### Mypy status

`mypy src/commander_lab` was executed by CI. The repository still has an established strict-type baseline of 268 errors in 36 files, so this is **not** represented as a clean strict-Mypy pass. The CI `Mypy baseline` gate completed successfully under the repository's existing baseline policy, and D does not broaden scope into repository-wide type-debt cleanup. This debt remains explicit rather than being hidden or reclassified.

### Known E reproduction signals retained

The Phase 8.6 audit output still reports tracked/runtime audit-generation concerns and the local D run previously showed post-test process-cleanup delay. These are intentionally not reclassified as D failures; they are the inputs to E and must be reproduced before repair:

- `BUG-AUDIT-001`: audit/acceptance execution may dirty tracked audit/schema artifacts.
- `BUG-PERF-001`: multiprocessing may show negative scaling and/or resource-cleanup warnings.

## Deliberately not remediated in D

The following are real limits, not D-level technical binding defects:

- Structural Simulator rules fidelity
- missing/high-impact card profiles
- pilot decision quality
- threat/politics realism
- opponent uncertainty quality
- meta research freshness
- real XMage/Forge execution
- external legal actions / external counterfactual executor
- repository-wide strict-Mypy debt

These remain correctly scoped to later audit/roadmap work.
