# Simulation Fidelity 124 Closeout — Current

Status date: 2026-08-21

Base main: `e8effd269252da93577c8142e48ec4286b21bfe8` (`v1.23.0`)

Repair branch: `repair/simulation-fidelity-124-closeout-v2-20260821`

Pull request: `#100`

## Scope and evidence boundary

This document closes the actionable simulator-fidelity audit against the current Optimizer-v2 1E/2F architecture. It does not claim that Structural Simulation is a full Magic rules engine. `structural_model_estimates` remain model evidence, not empirical win rates or external-rules-engine evidence.

The repository no longer contains a canonical file with the original 124 individual point labels. To avoid inventing provenance, traceability below uses the verified audit ranges/groups preserved in the repair handoff. A range marked `ROUTED_FAIL_CLOSED` is closed for decision safety even when the underlying Magic mechanic is intentionally not implemented in Structural.

## Status vocabulary

- `FIXED_MECHANISTICALLY`: an unambiguous state/fact/runtime defect is repaired in Structural.
- `ROUTED_FAIL_CLOSED`: Structural may screen, but strong confirmatory use is blocked or routed to Tactical/External rules evidence.
- `CLOSED_BY_1E_2F`: already resolved by PR #99 and retained unchanged.
- `EXPLICIT_NOT_MEASURED`: a telemetry contract exists but the metric is not fabricated until the engine measures it.
- `HISTORICAL_ONLY`: retained only for regression/provenance, never current source truth.

## Audit-range traceability

| Audit range | Theme | Closeout status | Current control/evidence |
| --- | --- | --- | --- |
| 1–10 | Card/profile foundations | `FIXED_MECHANISTICALLY + ROUTED_FAIL_CLOSED` | Current fact overlay derives type/permanency and simple colored pips; unsupported mechanics cannot become strong evidence merely because semantic metadata exists. |
| 11–16 | Stack/counter legality | `ROUTED_FAIL_CLOSED + selected mechanical fixes` | Silence is not treated as a counter; restricted/complex counter cards are excluded from the generic universal-counter resolver and require higher-layer evidence. Full counterwars remain outside Structural. |
| 17–28 | Removal/protection/wipes | `ROUTED_FAIL_CLOSED` | Target/mode/zone/wipe-protection semantics that are not rules-complete are classified Tactical/External or fail closed for confirmatory decisions. |
| 29–46 | Mana/tap/timing | `FIXED_MECHANISTICALLY + ROUTED_FAIL_CLOSED` | Simple pip multiplicity is derived from mana cost; source/tap/conditional-cost mechanics not represented exactly remain screening/higher-layer only. |
| 47–50 | Commander/partner state | `FIXED_MECHANISTICALLY` | Partner identities remain distinct; absent commanders reset transient power on zone change/recast, preventing Ishai power persistence. |
| 51–65 | RogShai combat | `ROUTED_FAIL_CLOSED` | Decision-critical combat cards requiring exact attack/block/double-strike/commander-damage semantics cannot silently drive Structural promotion. |
| 66–79 | Trigger/attachment/copy/modal/sacrifice | `ROUTED_FAIL_CLOSED` | High-risk mechanics are explicitly screening/Tactical/External instead of being represented as exact Magic rules. |
| 80–84 | Pilot robustness | `CLOSED_BY_1E_2F` | Strong deterministic, average deterministic and mulligan sensitivity remain distinct robustness axes. |
| 88–92 | Opponent/seat robustness | `CLOSED_BY_1E_2F` | 4P operational scope, seat and per-opponent robustness, exact triples diagnostic-only; no invented frequency weights. |
| 96–102 | Telemetry | `EXPLICIT_NOT_MEASURED` | Fidelity telemetry fields exist; unavailable metrics are `NOT_MEASURED`, not fabricated zeroes. |
| 103–107 | Model resolution | `CLOSED_BY_1E_2F + LEGACY_HARD_RETIRED` | Legacy effective-resolution APIs cannot authorize advancement; the current manifest-bound 1E/2F path is required. |
| 108–112 | Confirmatory partitions/robustness | `CLOSED_BY_1E_2F` | Fresh confirmatory, diagnostics and sealed holdout partitions remain separated with robustness axes. |
| 113–114 | Unified optimizer lifecycle | `CLOSED_BY_1E_2F` | `manifest → preflight → search → confirm → diagnose → holdout` remains the official lifecycle. |
| 115 | Common random numbers | `FIXED_MECHANISTICALLY` | Stochastic pilot stream derives from common match seed/seat rather than baseline-vs-variant match label. |
| 116–118 | Progress/abort semantics | `FIXED_MECHANISTICALLY + DECISION_CENSORED` | Balanced decision campaigns avoid the life-loss-only premature no-progress cutoff; aborted pairs remain visible diagnostically but are rejected at strong decision boundaries. |
| 119–120 | Structural fact-source risks | `FIXED_MECHANISTICALLY + ROUTED_FAIL_CLOSED` | Current fact overlay supersedes fragile name-table facts in the official materialization path; unsupported semantics remain gated. |
| 121 | Rules-coverage source freshness | `FIXED` | Builder uses current registries; dated canonical-import snapshots are excluded from current coverage truth; Korvold scenarios are historical/generic regression only where retained. |
| 122 | README currentness | `FIXED` | README documents the current PR #99/v1.23.0 decision architecture, repository scope, fidelity gate and evidence boundaries. |
| 123 | Legacy resolution reactivation | `FIXED` | Legacy advancement compatibility paths preserve diagnostics but cannot promote/reject from retired `effective_resolution`; Candidate Paired Triage asserts retirement. |
| 124 | Semantic evidence invalidation | `FIXED` | Structural semantic model has explicit version/identity; incompatible confirmatory artifacts fail with `STALE_MODEL_VERSION`. |

## Decision-safety contract

Mechanics fidelity tiers are:

1. `MECHANISTICALLY_SUPPORTED`
2. `APPROXIMATED_DECISION_SAFE`
3. `APPROXIMATED_SCREENING_ONLY`
4. `TACTICAL_REQUIRED`
5. `EXTERNAL_RULES_REQUIRED`
6. `UNSUPPORTED`

Only the first two tiers may support Structural confirmatory use for the changed-card question. The remaining tiers screen, route upward, or fail closed. Baseline residual approximations are not upgraded to rules-engine evidence.

## Abort/censoring contract

Raw Structural runs preserve aborted results for diagnostics. Paired campaigns publish `censored_pair_count` and `decision_evidence_eligible`. Confirmatory, critical-diagnostic and holdout decision consumers reject evidence unless `decision_evidence_eligible == true`; missing censoring metadata fails closed.

## Legacy-resolution contract

Pre-1E/2F advancement APIs remain importable only for historical compatibility and upstream diagnostics. They cannot use an `effective_resolution` threshold to authorize finalist sensitivity, rejection, promotion, holdout, or canonical mutation. Current advancement requires the manifest-bound Optimizer-v2 1E/2F workflow.

## Current-source contract

Current rules coverage is built from current deck/candidate/role/validation/opponent registries. Dated `data/canonical_import/*` snapshots may remain provenance/regression inputs elsewhere but are not current own-deck/rules-coverage truth.

## External-rules boundary

No entry in this closeout upgrades Tactical Oracle results to external-rules-engine evidence. XMage/Forge evidence may be called `external_rules_engine` only when the provider was actually executed and validated for the relevant scenario class. If a required scenario class has no validated provider, the correct decision behavior is fail closed.

## Final acceptance requirement

This closeout becomes merge-ready only when the final PR head passes all applicable repository gates, including CI (Ruff, Ruff format, strict Mypy, pytest, compile/build/security), Core Workflow Acceptance, Optimizer Workflow Acceptance, Windows Runtime Hygiene, Candidate Paired Triage, and Model Resolution Measurement.

A green closeout does not authorize a canonical deck or inventory mutation.
