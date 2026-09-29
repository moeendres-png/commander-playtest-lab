# Commander Playtest Lab

Local, reproducible decision system for Commander deck validation, Structural simulation, pilot/ensemble analysis, paired comparisons, ablation, holdout, sensitivity and constrained optimization.

## Project authority — read these before anything else

This README is an orientation summary, not authority. Where it disagrees with a
governing document, the governing document wins.

| Question | Authoritative source |
|---|---|
| Durable rules every session must follow | [`AGENTS.md`](AGENTS.md) — including the source-truth order, rules authority, evidence semantics, Git/worktree authority, and the fact that filenames containing `CURRENT`/`FINAL`/`LATEST` prove nothing |
| Governing mission and gates | [`docs/PROJECT_MISSION.md`](docs/PROJECT_MISSION.md) — outranks any summary, including the one on this page |
| Current engine pins | [`config/rules_engines.json`](config/rules_engines.json) — the sole machine-readable pin authority. Do not restate pins from prose |
| Current execution authority (who runs what, at which effort) | [`docs/COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md`](docs/COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md) with `AGENTS.md` §6–§7 |
| Foundry execution system | [`docs/foundry-execution/README.md`](docs/foundry-execution/README.md) — start a workstream with `.opencode/skills/workstream-bootstrap/SKILL.md` |
| Documentation map | [`docs/README.md`](docs/README.md) |
| Live PRs, issues and branches | [`docs/REPOSITORY_TRIAGE_INDEX.md`](docs/REPOSITORY_TRIAGE_INDEX.md) |

## Project identity, licensing, and third-party software

Commander Playtest Lab / Commander Simulator Next is an independent, unofficial research and engineering project. It is not maintained by XMage or Forge and is not affiliated with or endorsed by Wizards of the Coast.

The Lab's own package metadata currently declares `LicenseRef-Proprietary`. Public repository visibility does not by itself grant a license to reuse the Lab's original code or documentation. That project-level status does not replace or absorb third-party rights: third-party engines, data, rules text, card names, artwork, and other materials remain subject to their respective licenses and rights holders.

Current external rules-engine candidates are tracked under their own upstream licenses:

- [XMage](https://github.com/magefree/mage) — MIT-licensed upstream project. The separate [Commander Simulator Next XMage fork](https://github.com/moeendres-png/mage) retains XMage's upstream [`LICENSE.txt`](https://github.com/magefree/mage/blob/master/LICENSE.txt) and copyright/permission notice.
- [Forge](https://github.com/Card-Forge/forge) — GPL-3.0-licensed upstream project. The Lab's current Forge topology treats Forge as a separately built and launched provider process; this repository's proprietary package metadata does not relicense Forge.

The Lab does not claim legal clearance for all uses of Wizards intellectual property merely by being public or by linking to the [Wizards Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy). Magic: The Gathering and related Wizards materials remain property of their respective rights holders. This section records attribution and repository-status boundaries; it is not legal advice or a substitute for a separate legal-clearance decision.

These statements are not a production-provider decision. Architecture Freeze and production-provider selection remain governed by the project's qualification gates.

## Commander Simulator Next: project goal

The end goal is the best realistically achievable, maximally rules-correct full-rules
Commander simulator, with reproducible gameplay evidence from which to learn about
play, matchups and deck construction and improve pilots and deckbuilding decisions.
Rules Correctness takes precedence over performance, convenience and pilot strength.

Four players (one own deck and three opponents) is the primary benchmark and decision
mode, not an architecture constraint. Technical conformance must cover 2–5 players.
Prefer 6+ or generally variable player counts when they improve Rules Correctness,
simplicity, reuse, testability, or research/implementation, without weakening required
conformance. These are target requirements, not claims of implemented support.

Architecture selection is outcome-first: existing engines, complete simulators and
frameworks may replace entire workstreams when evidence shows a better route to the
goal. Neither current candidates nor invested work confer architectural priority.
See [the project mission](docs/PROJECT_MISSION.md) for the governing policy and gates.

## Runtime truth

Do not treat a commit SHA copied into this README as canonical current software truth. At execution time, resolve the repository default branch and pin the exact commit/tree in the run manifest. Package version alone is not a sufficient software identity.

The current decision architecture includes:

- Optimizer-v2 1E hierarchical gates + Pareto;
- 2F sequential paired precision;
- question-specific mechanics-fidelity routing;
- Structural simulator fidelity corrections;
- abort/censoring fail-closed decision evidence;
- content-addressed current decision/semantic inputs.

The existing Structural simulation's operational decision scope remains **4-player
Commander only**. This implementation boundary does not constrain Commander Simulator
Next's architecture or research scope. Other player counts require their own qualified
runtime and decision evidence; this documentation change does not enable them.

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

### Run the suite this way, or expect a red baseline

Install the dev extra before running the suite. Two failure modes follow from skipping it,
and both are environmental rather than product defects:

- `tests/integration/test_phase5_server.py` and `tests/unit/test_phase5_openai_adapter.py`
  fail to **collect** because `httpx2` and `pytest-asyncio` (declared dev dependencies,
  `pyproject.toml`) are not installed. `test_phase10_acceptance.py` fails for the same root
  cause: `src/commander_lab/acceptance/phase10.py` catches the resulting exception and
  reports `failed` instead of `passed_with_limitations`.
- Tests that spawn a child interpreter cannot import the project, because
  `pythonpath = ["src"]` in `pyproject.toml` applies to the pytest process only and is not
  inherited by children. The `subprocess_env` fixture in `tests/conftest.py` handles this for
  the tests that need it, so these are covered either way — but a bare run is still the
  supported way to work.

CI runs the suite with the project installed (`pip install --no-deps -e .`). A local run that
matches CI needs the same install.

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
