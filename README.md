# Commander Playtest Lab

Local, reproducible decision system for Commander deck validation, Structural simulation, pilot/ensemble analysis, paired comparisons, ablation, holdout, sensitivity and constrained optimization.

## Runtime truth

Do not treat a commit SHA copied into this README as canonical current software truth. At execution time, resolve the repository default branch and pin the exact commit/tree in the run manifest. Package version alone is not a sufficient software identity.

The current decision architecture includes:

- Optimizer-v2 1E hierarchical gates + Pareto;
- 2F sequential paired precision;
- question-specific mechanics-fidelity routing;
- Structural simulator fidelity corrections;
- abort/censoring fail-closed decision evidence;
- content-addressed current decision/semantic inputs.

The operational simulation scope is **4-player Commander only**. 3-player and 5-player simulation is intentionally out of scope unless the project policy is explicitly changed later.

Active own-deck scope must be read from the current project/collection scope and newer direct project truth, not inferred from this README or historical snapshots. Frozen opponent-only decks likewise come from the current opponent/project registries.

No search, confirmatory result, diagnostic, or holdout automatically mutates a canonical/current deck, inventory quantity, physical allocation, purchase state, or opponent observation.

## Optimizer-v2 decision path

The official path is:

```text
manifest -> preflight -> run/search -> mechanics-fidelity routing -> confirm -> diagnose -> holdout
```

The current architecture uses:

- SESOI separated from model precision;
- paired sequential confirmatory looks defined by the current decision contract;
- multiplicity control;
- MCSE and seed-stability gates;
- seat, pilot and opponent robustness within 4P;
- fresh critical diagnostics;
- a single frozen challenger before a fresh single-look sealed holdout.

Historical `effective_resolution` promotion logic is retired and cannot authorize advancement.

### Fidelity-aware search and confirmatory routing

Structural search is deliberately asymmetric by evidence cost:

1. legal candidates may receive the smallest Exploratory Structural screening budget;
2. a candidate whose delta is outside the question-specific Structural decision-safe mechanics contract cannot receive later Structural racing budgets;
3. screening-only / tactical / external-rules candidates do not train adaptive Structural operator or policy rewards;
4. the frontier remains auditable and keeps routed candidates visible;
5. Structural confirmatory uses only a diverse shortlist of decision-safe frontier candidates;
6. a non-decision-safe frontier candidate does not block unrelated decision-safe candidates;
7. if no decision-safe candidate remains, confirmatory fails closed.

The mechanics contract distinguishes:

- `MECHANISTICALLY_SUPPORTED`;
- `APPROXIMATED_DECISION_SAFE`;
- `APPROXIMATED_SCREENING_ONLY`;
- `TACTICAL_REQUIRED`;
- `EXTERNAL_RULES_REQUIRED`;
- `UNSUPPORTED`.

Only the first two categories can support Structural confirmatory decisions. Higher-layer candidates require an actually valid tactical/external evidence path or remain unresolved/fail-closed.

## Evidence boundary

Simulator outputs are `structural_model_estimates`. They are not empirical win rates and are not external-rules-engine evidence.

The Tactical Oracle is a separate bounded abstraction and is not an external rules engine.

XMage/Forge evidence may only be called `external_rules_engine` when a real provider run was actually executed and validated for the relevant scenario class.

A known semantic profile is not equivalent to mechanistic support. Mechanics that need exact targets, modes, payment resources, stack sequencing, combat assignment, attachments, trigger copying or other rules-complete state are routed to a higher evidence layer or fail closed.

Structural semantic-model changes invalidate prior confirmatory mechanics evidence with `STALE_MODEL_VERSION`; a different Git commit alone is not treated as a sufficient semantic compatibility claim.

## Current-source policy

Current decisions should resolve through current, content-addressed sources such as:

```text
data/decks/*current*
data/collections/current/
data/decision/DECISION_CONTRACT_CURRENT.json
data/opponents/
data/opponent_ensembles/
data/cards/
data/sync/current_sources.json
```

Dated `data/canonical_import/...` snapshots are historical/regression provenance, not current deck, inventory or rules truth.

For volatile software identity, use the actual GitHub default-branch commit/tree at execution time. A Drive status summary may be useful provenance but must not override a newer verified GitHub software state.

For deck, physical inventory, allocation and opponent truth, use the current canonical project sources and newer direct project statements according to the project source hierarchy.

## Main implementation files

```text
data/decision/DECISION_CONTRACT_CURRENT.json
src/commander_lab/whole_deck/mechanics_fidelity.py
src/commander_lab/whole_deck/optimizer_search.py
src/commander_lab/engine/structural/fact_fidelity.py
src/commander_lab/engine/structural/simulator_fidelity.py
```

## Setup and validation

```bash
uv sync --extra dev
uv run pytest
```

or:

```bash
python -m pip install -e .
pytest
```

Useful project commands include:

```bash
commander-lab validate-local --root .
commander-lab generate-structural-profiles --root .
commander-lab validate-structural --iterations 24 --workers 2 --seed 20260804 --root .
commander-lab validate-pilots --iterations 24 --workers 2 --seed 20260804 --root .
commander-lab probe-rules-engines --root .
python -m commander_lab.optimizer_v2_cli preflight --manifest <manifest> --root .
python -m commander_lab.optimizer_v2_cli fidelity --frontier <frontier> --root .
```

## Optimization rule

Candidate changes remain read-only until explicitly accepted. A baseline or challenger may be evaluated through paired comparison, commander-denial, ablation, holdout, sensitivity, pilot and opponent-ensemble workflows only within the evidence layers that are valid for the mechanics involved and within the current operational 4P scope.
