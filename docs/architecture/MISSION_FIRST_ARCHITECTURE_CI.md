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
capabilities; architecture/CI cleanup cannot promote provider readiness. The merged B3 XMage bridge
is real `external_rules_engine` evidence for pinned-runtime deck import, Commander construction and
game start only. Legal-action enumeration, action submission and event logging remain required
missing capabilities.

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

The current loader projects only physically free candidates from the current eligibility source.
Hypothetical test candidates are an explicit caller input and remain `hypothetical_test` with
quantity zero.

## Legacy/current adapters

The following RogShai references remain intentional and are not generic-core contracts:

- `RogShaiCandidateScreener`: current RogShai policy/regression adapter and J-P5 challenge-set
  provenance;
- `scripts/run_j_p6_workflow_smoke.py`: current RogShai reference workflow regression;
- J-FINAL artifacts/scripts: historical RogShai decision-support regression;
- current canonical feature projection paths and current candidate eligibility data.

Two compatibility paths still encode current-scope conveniences: the legacy candidate repository's
RogShai color mapping and `CommanderToolService.ACTIVE_OWN_DECK_IDS` in its fallback inventory path.
The latter is not used by the normal current projected-availability path. New mission-first code
must consume `DecisionContextRegistry` and deck-scoped workflow identity rather than infer that the
current one-deck state is universal. Removing these compatibility conveniences is a controlled
migration, not a reason to alter canonical MTG data.

The current project-context/inventory projection also still names the dated canonical-import
snapshot and the RogShai feature-projection directory. Those are current-data projection concerns,
not contracts of the new decision-context API; a future canonical pointer/registry can remove the
remaining path coupling without changing deck semantics.

## User-goal traceability

| User goal | Capability | Core component | Test / acceptance | Evidence type |
| --- | --- | --- | --- | --- |
| Select exact own deck | deck-scoped immutable context | `DecisionContextRegistry` | multi-deck fixture | technical contract |
| Preserve physical/test provenance | candidate provenance states | `CandidateProvenance` | decision-context tests | provenance, not card power |
| Keep deck runs separate | deck/variant run identity | `DecisionRunContext`, `WorkflowSemanticIdentity` | multi-deck + workflow-identity tests | reproducibility |
| Compare variants under real project workflow | paired/ablation/denial/holdout/sensitivity/search/report | existing decision services | Core Workflow Acceptance current reference regression | `structural_model_estimates` technical smoke |
| Preserve opponent uncertainty | registry/ensemble evidence labels | opponent repositories/models | normal test suite + core workflow | observed/inferred/synthetic kept distinct |
| Validate external engine boundary | provider capability gate | rules adapter / XMage bridge | External XMage Integration (manual) | `external_rules_engine` only when executed |
| Package software | SHA-bound wheel/sdist/source/repository/bundle | build tooling | Release Artifacts | software artifact evidence |

## Workflow inventory and disposition

| Workflow | Trigger after audit | Contract | Evidence / cost | Disposition |
| --- | --- | --- | --- | --- |
| CI | PR, main, manual | Quality + Security | central generic checks | keep as quality owner |
| Core Workflow Acceptance | relevant PR/main, manual | decision-context + current E2E reference contract | bounded semantic smoke | replaces J-P6 Acceptance |
| Decision Support Regression | own workflow/script PR, manual | historical J-FINAL RogShai regression | historical regression | replaces J-FINAL Acceptance |
| Optimizer Workflow Acceptance | optimizer paths, manual | evidence partition + CLI contract | bounded semantic gate | deduplicated |
| Model Resolution Measurement | relevant paths, manual | technical structural resolution measurement | bounded measurement | keep |
| Windows Runtime Hygiene | relevant paths/main, manual | Windows filesystem/runtime behavior | platform-specific | slimmed; no full duplicate suite |
| Release Artifacts | release contract PR, main/release/manual | SHA-bound packaging + roundtrip + truth manifest | packaging only | no broad PR full-suite duplication |
| Optimizer v2 Technical Benchmark | manual | expensive technical A/B | benchmark | keep on demand |
| External XMage Integration | manual | real pinned provider integration | expensive external engine | keep on demand |
| J-P3B XMage Native Fixtures | manual | historical native fixture evidence | expensive/historical | keep provenance |
| J-P3B XMage Real Spike | manual | historical provider spike | expensive/historical | keep provenance |
| J-P3C Forge Real Spike | old roadmap push, manual | historical Forge spike | expensive/historical | keep provenance; not PR CI |
| J-P3C Forge Runtime XVFB Probe | old roadmap push | historical Forge runtime probe | expensive/historical | keep provenance; not PR CI |
| J-P6 Performance Evidence | old roadmap push, manual | frozen performance evidence | historical/benchmark | keep on demand |

The total workflow count remains 14: two old acceptance workflows were replaced by two semantically
named workflows rather than adding another layer. The important reduction is in default execution
and duplicate work, not in file count.

## CI ownership

`CI / quality` owns Ruff lint, Ruff format, mypy, compile, the full pytest suite, secret-pattern scan
and wheel build. Security remains a separate CI job because dependency/SBOM/license evidence is a
distinct contract. Acceptance workflows do not repeat those generic gates merely to create another
green signal.

The historical Phase-8.6 audit is no longer a default PR quality step. Its useful checks remain in
the normal test suite and the audit command remains available, but its generated provider narrative
still described the pre-B3 state (for example, a missing Java bridge) after B3 had been merged. A
historical phase report that emits stale runtime truth is not a durable quality gate.

Core acceptance is intentionally semantic: it checks multi-deck context separation and then runs a
small current reference user journey covering deck validation, structural matchup, paired variant,
card/package ablation, commander denial, holdout, sensitivity, variant search, recommendation and
reporting. The RogShai run is a reference fixture for that current journey, not proof that the core
supports only RogShai and not evidence of deck strength.

Historical J-FINAL now runs only manually or when its own regression script/workflow changes. Release
packaging runs on main/release branches and on PRs that change the release contract itself. It keeps
SHA-bound repository/source artifacts, wheel verification, checksums and roundtrip validation but no
longer reruns the full Python test suite owned by CI. Current B3 external-engine truth comes from
`config/rules_engines.json`; `docs/J_P3_PROVIDER_DECISION.json` is retained explicitly as historical
P3 feasibility evidence rather than silently promoted to current truth. Windows CI is limited to
Windows-specific filesystem/runtime and external-boundary behavior rather than a second full Python
test suite.

## Non-mutation boundary

Architecture and CI tests may create temporary fixtures and run artifacts. They must not modify
canonical deck lists, inventory quantities, physical allocations, opponent observations, purchase
state or holdout seals. A hypothetical candidate is never promoted to physical inventory by a
simulation or report.
