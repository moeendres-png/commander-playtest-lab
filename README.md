# Commander Playtest Lab

Local, reproducible decision system for Commander deck validation, structural simulation, pilot/ensemble analysis, paired comparisons, ablation, holdout, sensitivity and constrained optimization.

## Current operational own deck — 2026-08-11

There is exactly one current own-deck snapshot:

- `rogshai/current` — Ishai, Ojutai Dragonspeaker + Rograkh, Son of Rohgahh
- 100 cards total / 98-card library / 36 lands
- deck hash: `7b7d03aa16be6586df8f8a4e9f1acd30f85ad2e8e45e7889e700353a6f19c126`
- status: `current_provisional_final_for_simulator_optimization`

This list is the physically buildable current reference and the baseline for continued simulator/optimizer improvement. It is **not frozen**: later evidence may justify changes.

Superseded RogShai snapshots and former own Korvold decklists are intentionally absent from the current operational deck data. Git history may retain provenance, but history is not a current deck source. `KorvoldPilot` may remain as a legacy software capability for historical regression or explicitly supplied external decks; it does not imply an active/current Korvold own deck.

Kaervek data is opponent-only and is not part of the own-deck cleanup.

## Evidence boundary

Simulator outputs are labelled `structural_model_estimates`. They are not empirical win rates and are not external-rules-engine evidence. The Tactical Oracle is a separate bounded abstraction. XMage/Forge evidence may only be called `external_rules_engine` when a real provider run was actually executed and validated.

Current-deck-specific inferred card/role records needed to load the provisional RogShai baseline live in explicit overlay files under `data/decks/`; they do not silently promote candidate-pool coverage or external-rules validation.

Playstyle/administrative complexity is not an optimization prior. Deck strength, synergy, mana, interaction, resilience, matchup robustness and multiplayer scaling are evaluated first; subjective playstyle review is downstream only.

## Main current files

```text
data/decks/rogshai_current.txt
data/decks/rogshai_current.json
data/decks/manifest.json
data/decks/rogshai_current_card_catalog_overrides.json
data/decks/rogshai_current_structural_overrides.json
data/sync/current_sources.json
```

`data/decks/manifest.json` is the current operational deck manifest and contains only `rogshai/current`.

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

Useful project commands:

```bash
commander-lab validate-local --root .
commander-lab generate-structural-profiles --root .
commander-lab validate-structural --iterations 24 --workers 2 --seed 20260804 --root .
commander-lab validate-pilots --iterations 24 --workers 2 --seed 20260804 --root .
commander-lab probe-rules-engines --root .
```

## Standard deck-decision workflow

Normal users and agents use four deterministic workflow commands. They share one immutable
project-context snapshot and never apply a deck change:

```bash
commander-lab decision prepare --root .
commander-lab decision run --remove "Flare of Duplication" --add-candidate-id "inventory/rootborn-defenses-677fdbcf" --root .
commander-lab decision diagnose comparison.json --root .
commander-lab decision bundle comparison.json --output-directory data/runs/decision_bundle --root .
```

The default FastAPI and MCP tool listings expose the same four contracts. The retained 100
low-level tools are available through the explicit `/v1/expert/tools` API or MCP
`surface="expert"`; they are composable debugging and specialist primitives, not the normal
agent surface. Keep-rule generation and cross-context validation are opt-in research work.

Before broad search, the workflow reports whether the current structural evidence can actually
separate variants. A model-information limit stops seed-only escalation and produces a diagnostic
next step. Only a preregistered `advance` decision can enter finalist sensitivity.

The `synthetic/*` decks are technical engine-validation fixtures, not claims about real opponents.

## Current optimization rule

No search result is automatically applied to the canonical/current deck. Candidate changes must remain read-only until explicitly accepted. The current baseline can be improved through the project’s paired comparison, commander-denial, ablation, holdout, sensitivity, pilot and opponent-ensemble workflows while preserving physical inventory constraints and evidence labels.
