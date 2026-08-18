# Mission-first acceptance architecture

## Goal

The Commander Playtest Lab exists to improve real Commander deck-building decisions while preserving evidence boundaries, physical-inventory truth, and reproducibility. CI and acceptance gates should therefore test software quality once and decision-system semantics where they matter, rather than repeatedly re-running the same generic static checks under historical phase names.

## Current operational truth

- `rogshai/current` is the only active own-deck baseline today.
- The core must not assume that only one own deck can ever exist.
- Former Korvold data is historical/regression provenance only and must not reserve physical inventory or become an optimization target.
- `kaervek/current` is a frozen opponent-only baseline.
- Structural results are `structural_model_estimates`, not empirical win rates.
- Tactical Oracle evidence is not `external_rules_engine` evidence.
- XMage B3 supplies bounded real external-engine evidence for deck import, Commander/Partner construction, multiplayer game construction and game start only.
- `NO_PROVIDER_READY` remains true until a real action loop and the required production capabilities are implemented and validated.

## CI ownership model

### Old model

Generic checks were repeated across `CI`, `J-FINAL Acceptance`, and `J-P6 Acceptance`. In particular, compile, Ruff, format, Mypy, repository-diff checks, or overlapping static integrity checks appeared in multiple jobs. This increased runtime and allowed historical acceptance workflows to mix software-quality ownership with domain semantics.

### New model

`CI/quality` is the single owner of generic repository and Python quality gates:

- repository integrity and whitespace diff checks;
- Ruff lint;
- Ruff format;
- Mypy strict on `src/commander_lab`;
- full Pytest suite;
- compile of `src`, `tests`, and `scripts`;
- Phase 8.6 audit;
- secret-pattern scan;
- wheel build;
- tracked-tree cleanliness.

Specialized acceptance workflows retain only behavior that gives additional semantic evidence:

- `J-FINAL Acceptance`: current decision-support regression, candidate-discovery invariants, paired structural comparison, commander denial, ablation, sensitivity, and evidence-bundle production.
- `J-P6 Acceptance`: focused decision/runtime regressions, end-to-end core workflow smoke, package/CLI contract, holdout governance, current-scope boundary, and the workflow-side-effect cleanliness check.

Historical workflow names may remain temporarily to avoid destabilizing required-check configuration. Their job content, not the label, defines the acceptance responsibility.

## Snapshot policy

Acceptance gates must distinguish current canonical truth from incidental snapshot size.

A current operational assertion such as "RogShai is the sole active own deck" may be valid when the project manifest says so. A numeric candidate-pool size such as `795` is not a durable semantic contract. Acceptance therefore prefers invariants such as:

- the candidate universe is non-empty;
- all physically legal candidates are discoverable;
- bucket counts cover the discoverable universe exactly;
- candidate recall remains complete;
- unexplained exclusions fail the gate;
- unmodeled candidates stay discoverable but cannot silently become model-dependent recommendations.

Exact historical counts can remain in dedicated snapshot/regression tests when preserving that historical artifact is itself the purpose of the test.

## Multi-deck direction

Current data contains one active own deck, so no second canonical deck is fabricated for testing. Multi-deck readiness should be established through deck-id-parameterized core APIs and isolated fixtures. New own decks should enter through registry/manifest data, not by adding new deck-name branches throughout services, simulators, mulligan logic, or acceptance workflows.

Deck-specific policies are allowed where the policy is genuinely deck-specific. They must be selected from explicit deck/commander metadata or registries rather than from an assumption that every non-Korvold deck is RogShai.

## Opponent and provenance direction

Opponent handling should remain registry-driven and evidence-aware. `verified_full_deck`, `official_precon`, `directly_observed`, `reported`, `partially_observed`, `inferred`, `synthetic_completion`, and `unknown` must remain distinguishable. Synthetic completion must never be promoted to observation.

Physical-inventory provenance must remain distinct from explicitly authorized hypothetical test cards. Simulation authorization creates no durable reservation and must not modify canonical inventory truth.

## Traceability

| User goal | Capability | Core component | Tests / validation | Acceptance gate | Evidence type |
|---|---|---|---|---|---|
| Keep current deck legal and reproducible | Deck/inventory validation | project context, deck service, candidate inventory | full Pytest + current-scope regressions | CI + J-P6 | canonical/runtime validation |
| Find plausible improvements from real cards | candidate discovery and constraints | candidate screening, optimization constraints | candidate-discovery invariant tests | J-FINAL | structural_model_estimates / canonical inventory |
| Compare a swap fairly | paired structural comparison | priority workflow facade, structural simulator | paired workflow tests | J-FINAL / J-P6 | structural_model_estimates |
| Avoid commander over-dependence | commander-denial analysis | tool service / structural engine | denial regressions | J-FINAL | structural_model_estimates |
| Understand card/package contribution | ablation | tool service / structural engine | ablation regressions | J-FINAL / J-P6 | structural_model_estimates |
| Test robustness across pods/pilots/assumptions | sensitivity and ensembles | structural engine, pilots, opponent registries | robustness/property/integration tests | J-FINAL / J-P6 | structural_model_estimates + explicit assumptions |
| Preserve frozen opponents correctly | opponent registry/provenance | opponent repository / project context | Kaervek and opponent repository tests | CI | canonical opponent evidence |
| Use a real rules engine without overclaiming | bounded XMage bridge | engine bridge / process manager | Java bridge tests, runtime integration, capability checks | external-engine workflow | external_rules_engine for implemented capabilities only |
| Keep software maintainable | centralized quality gates | repository-wide | Ruff, format, Mypy, full Pytest, compile, security | CI | software verification |

## Phase-B completion criteria

Phase B is complete only when:

1. generic CI ownership is centralized and specialized gates are semantic;
2. core deck-facing APIs are demonstrably usable with isolated non-RogShai fixtures without creating fake canonical decks;
3. deck-family branching that incorrectly defaults unknown decks to RogShai is removed or fail-closed;
4. opponent/provenance boundaries remain explicit;
5. representative user-journey acceptance covers validate -> inspect -> candidate discovery -> compare -> robustness/evidence report;
6. structural and external-engine evidence labels remain truthful;
7. all relevant CI is green and the branch remains reproducible.

This document records the target architecture; it does not itself claim that all Phase-B completion criteria are already satisfied.
