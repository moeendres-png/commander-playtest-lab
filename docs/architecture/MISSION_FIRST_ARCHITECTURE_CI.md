# Mission-first architecture and CI

## Purpose

The Commander Playtest Lab is a decision-support system. Its durable product contract is to take an
explicit own-deck context, inventory/test-candidate provenance, opponent assumptions and simulation
configuration and return reproducible decision evidence. The currently active deck is data; it is
not a generic-core default.

Evidence boundaries remain strict:

- `structural_model_estimates` are model estimates, not empirical win rates.
- `tactical_oracle` evidence is not an external rules engine.
- `external_rules_engine` is used only for a provider that was actually executed.
- `real_observation` is kept distinct from `synthetic_assumption`.
- CI/runtime smoke success is technical acceptance evidence, not deck-strength evidence.

`NO_PROVIDER_READY` remains in force until the external provider satisfies the required production
capabilities; architecture/CI cleanup cannot promote provider readiness.

## Current data state versus system capability

`data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json` is the live current-scope projection. It
currently contains one active own deck, `rogshai/current`, and retains Korvold only as historical
provenance. This is intentionally separate from multi-deck system capability.

The generic decision-context contract lives in `commander_lab.decision_context`:

- every operation selects a `deck_id` explicitly;
- physical-free candidates and explicitly supplied hypothetical test candidates are distinct;
- reserved, opponent, purchase and unknown provenance states cannot silently become simulatable
  physical inventory;
- theorycraft/test candidates never create an inventory or allocation mutation;
- run identity includes deck, variant, candidate provenance, opponent set, pilots, pod size, seed,
  evidence class and the immutable context snapshot;
- cross-deck candidate leakage fails closed.

The canonical current loader intentionally projects only physically free candidates from the
current eligibility source. Hypothetical test candidates are an explicit caller input and remain
`hypothetical_test` with quantity zero.

## Legacy/current adapters

The following RogShai references remain intentional and are not treated as generic-core contracts:

- `RogShaiCandidateScreener`: current RogShai policy/regression adapter and J-P5 challenge-set
  provenance;
- `scripts/run_j_p6_workflow_smoke.py`: current RogShai reference workflow regression;
- J-FINAL artifacts/scripts: historical RogShai decision-support regression;
- current canonical feature projection paths and current candidate eligibility data.

Legacy service/repository paths still contain current-scope conveniences. New mission-first code
must consume `DecisionContextRegistry`/deck-scoped workflow identity rather than infer that the
current one-deck state is universal. Removing the remaining legacy conveniences is a controlled
compatibility migration, not a reason to alter canonical MTG data.

## User-goal traceability

| User goal | Capability | Core component | Test / acceptance | Evidence type |
| --- | --- | --- | --- | --- |
| Select exact own deck | deck-scoped immutable context | `DecisionContextRegistry` | multi-deck fixture | technical contract |
| Preserve physical/test provenance | candidate provenance states | `CandidateProvenance` | decision-context tests | provenance, not card power |
| Keep deck runs separate | deck/variant run identity | `DecisionRunContext`, `WorkflowSemanticIdentity` | multi-deck + workflow-identity tests | reproducibility |
| Compare variants under real project workflow | paired/ablation/denial/holdout/sensitivity/search/report | existing decision services | Core Workflow Acceptance current reference regression | `structural_model_estimates` technical smoke |
| Preserve opponent uncertainty | registry/ensemble evidence labels | opponent repositories/models | normal test suite + core workflow | observed/inferred/synthetic kept distinct |
| Validate external engine boundary | provider capability gate | rules adapter / XMage bridge | External XMage Integration (manual) | `external_rules_engine` only when executed |
| Package software | deterministic release artifacts | build tooling | Release Artifacts | software artifact evidence |

## Workflow inventory and disposition

| Workflow | Trigger after audit | Contract | Evidence / cost | Disposition |
| --- | --- | --- | --- | --- |
| CI | PR, main, manual | Quality + Security | central generic checks | keep as quality owner |
| Core Workflow Acceptance | relevant PR/main, manual | decision-context + current E2E reference contract | bounded semantic smoke | replaces J-P6 Acceptance |
| Decision Support Regression | manual | historical J-FINAL RogShai regression | historical regression | replaces J-FINAL Acceptance |
| Optimizer Workflow Acceptance | optimizer paths, manual | evidence partition + CLI contract | bounded semantic gate | deduplicated |
| Model Resolution Measurement | relevant paths, manual | technical structural resolution measurement | bounded measurement | keep |
| Windows Runtime Hygiene | relevant paths/main, manual | Windows filesystem/runtime behavior | platform-specific | slimmed; no full duplicate suite |
| Release Artifacts | main/release/manual | wheel/sdist/source/bundle | packaging only | no PR full-suite duplication |
| Optimizer v2 Technical Benchmark | manual | expensive technical A/B | benchmark | keep on demand |
| External XMage Integration | manual | real pinned provider integration | expensive external engine | keep on demand |
| J-P3B XMage Native Fixtures | manual | historical native fixture evidence | expensive/historical | keep provenance |
| J-P3B XMage Real Spike | manual | historical provider spike | expensive/historical | keep provenance |
| J-P3C Forge Real Spike | old roadmap push, manual | historical Forge spike | expensive/historical | keep provenance; not PR CI |
| J-P3C Forge Runtime XVFB Probe | old roadmap push | historical Forge runtime probe | expensive/historical | keep provenance; not PR CI |
| J-P6 Performance Evidence | old roadmap push, manual | frozen performance evidence | historical/benchmark | keep on demand |

## CI ownership

`CI / quality` owns Ruff lint, Ruff format, mypy, compile, the full pytest suite, phase audit, secret
scan and wheel build. Acceptance workflows do not repeat those generic gates merely to create a
second green signal. Security remains a separate CI job because dependency/SBOM/license evidence is
a distinct contract.

Core acceptance is intentionally semantic: it checks multi-deck context separation and then runs a
small current reference user journey covering deck validation, structural matchup, paired variant,
card/package ablation, commander denial, holdout, sensitivity, variant search, recommendation and
reporting. The RogShai run is a reference fixture for that current journey, not proof that the core
supports only RogShai and not evidence of deck strength.

## Non-mutation boundary

Architecture and CI tests may create temporary fixtures and run artifacts. They must not modify
canonical deck lists, inventory quantities, physical allocations, opponent observations, purchase
state or holdout seals. A hypothetical candidate is never promoted to physical inventory by a
simulation or report.
