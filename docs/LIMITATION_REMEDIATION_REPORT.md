# Limitation Remediation Report — Audit Point D

Date: 2026-08-08
Baseline: `1.13.4` / `main` / `c969fef5f0e78caade87187d44524d959568d434`
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

## Verification

Local verification on the D patch:

- `python -m compileall -q src tests`: PASS
- `git diff --check`: PASS
- targeted D regression tests: 4 PASS
- relevant D cross-suite: 111 PASS
- complete unit suite split into two batches: 134 PASS + 104 PASS = 238 PASS
- property/golden/contract/regression: 27 PASS
- integration batch A: 13 PASS
- integration batch B: 14 PASS
- agent_evals/architecture/differential/fuzz/mutation: 12 PASS, 1 legitimate external-engine SKIP
- root pretest deck variants: 4 PASS
- segmented complete suite: 308 PASS, 1 SKIP, 0 FAIL
- test collection: 309 tests collected
- Ruff: unavailable in the local isolated package index; required on GitHub CI
- Mypy: unavailable in the local isolated package index; required on GitHub CI

One local unit batch completed all 134 tests successfully but the harness reported a timeout during process cleanup after pytest had printed the final PASS summary. This is not counted as a test failure and belongs to the existing runtime/performance cleanup work in E.

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

These remain correctly scoped to G and the later J roadmap.
