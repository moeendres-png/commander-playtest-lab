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

For real Commander deck-decision evidence, the default official scope is **exactly 4 players: one own deck plus exactly three opponents**, unless a Decision Contract explicitly defines another allowed scope. The full-rules engine itself should technically support 2P, 3P, 4P and 5P; 6P is strongly desired where it can be supported without reducing correctness.

Active own-deck scope must be read from the current project/collection scope and newer direct project truth, not inferred from this README or historical snapshots. Frozen opponent-only decks likewise come from the current opponent/project registries.

No search, confirmatory result, diagnostic, or holdout automatically mutates a canonical/current deck, inventory quantity, physical allocation, purchase state, or opponent observation.

## Project execution routing

The canonical execution-environment policy is [`docs/PROJECT_EXECUTION_POLICY.md`](docs/PROJECT_EXECUTION_POLICY.md).

There are exactly three project execution paths:

- **normal ChatGPT Sol High** for coordination, research, architecture, difficult reasoning, MTG authority work, evidence adjudication, and all useful pre-work before any Work handoff;
- **OpenCode Go with Muse Spark 1.3 Contributor** for repository implementation, debugging, CI, runtime qualification, audits and mechanical repository work;
- **ChatGPT Work with Astra** only as an exceptional minimal fallback after `WORK_NECESSITY = PASS`.

Muse Spark 1.3 is one AI model and must not be split into separate Muse and Spark resources.

The current OpenCode project lock is:

- provider: `opencode-go`
- model: `muse-spark-1.3-contributor`
- full ID: `opencode-go/muse-spark-1.3-contributor`
- allowed reasoning effort: `high`, `xhigh` only
- minimum reasoning effort: `high`
- default reasoning effort: `high`
- `medium`, `low`, `minimal`, `none`, and `off` are not authorized; medium and all lower efforts are unauthorized
- all other OpenCode providers/models are outside current project policy

Use High for all other project OpenCode work, including helpers and bounded/mechanical tasks, as well as normal repository execution. Prefer XHigh when task difficulty or length materially benefits from it, including difficult implementation, long-running autonomous campaigns, difficult debugging/root-cause analysis, complex multi-file remediation, provider/Rules-Core boundary work, qualification campaigns, semantic integration, and difficult evidence reconciliation.

Work policy:

- Astra Medium is the normal/default Work effort.
- Astra High is allowed only rarely when the exact irreducible Work-only operation materially requires it.
- Normal Sol High must do as much useful research, source locking, narrowing, adjudication, planning and context reduction as possible before Work is opened.
- Work receives only the minimum context and smallest operation that genuinely requires Work.
- Work must not repeat completed Sol/OpenCode research or broad discovery.
- Work returns control to normal Sol High immediately after the irreducible operation is complete.

The repository root [`opencode.json`](opencode.json) is the machine-enforced OpenCode configuration.

Older reports, prompts or handoffs that prescribe Work as the default execution environment, split Muse and Spark into separate resources, use another OpenCode model, permit OpenCode effort below High, or prescribe a different Work model/effort policy are historical provenance. Their technical findings remain evidence, but their execution-routing instructions are superseded by the current policy.

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

Candidate changes remain read-only until explicitly accepted. A baseline or challenger may be evaluated through paired comparison, commander-denial, ablation, holdout, sensitivity, pilot and opponent-ensemble workflows only within the evidence layers that are valid for the mechanics involved and within the current official decision scope.
