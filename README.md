# Commander Playtest Lab

Local, reproducible decision system for Commander deck validation, structural simulation, pilot/ensemble analysis, paired comparisons, ablation, out-of-sample robustness, sensitivity and constrained optimization.

## Current own-deck scope — 2026-08-18

The project distinguishes global ownership from the smaller runtime-loaded optimization surface:

- globally active own decks:
  - `rogshai/current` — Ishai, Ojutai Dragonspeaker + Rograkh, Son of Rohgahh
  - `korvold/current` — Korvold, Fae-Cursed King
- current runtime-loaded deck: `rogshai/current`
- current optimization target: `rogshai/current`
- unresolved operational baseline: `korvold/current`
- frozen opponent-only deck: `kaervek/current`

The current RogShai runtime snapshot contains 100 cards / 98-card library / 36 lands with deck hash:

`1704b6f1574e4d3152f08cf9936c389683f0ae6efa98a8a277a64daa37f583e3`

Korvold is globally active by the newer direct project instruction, but the repository does **not** currently contain a verified operational Korvold 100-card baseline that may safely be promoted from historical data. The runtime therefore fails closed: Korvold is not loaded, its historical decklists are not treated as current, and historical Korvold allocations are not released as current free inventory.

`data/decks/manifest.json` deliberately separates `global_active_own_decks` from `runtime_loaded_decks`. Its legacy `active_own_decks` field is retained only as a `runtime_loaded_decks` compatibility alias.

Kaervek remains frozen opponent-only and is never an own-deck optimization target.

## Evidence boundary

Simulator outputs are labelled `structural_model_estimates`. They are not empirical win rates and are not external-rules-engine evidence. The Tactical Oracle is a separate bounded abstraction. XMage/Forge evidence may only be called `external_rules_engine` when a real provider run was actually executed and validated.

Current XMage status is B3-partial at the pinned `moeendres-png/mage` commit `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`: real deck import plus Commander/Partner 2–5 player game construction/start and bounded lifecycle execution are implemented. Legal-action enumeration, action submission, event logs, replay and deterministic seed control remain outside the proven bridge capability. `NO_PROVIDER_READY` therefore remains true.

Historical provider decision documents such as `docs/J_P3_PROVIDER_DECISION.json` remain immutable provenance; current provider truth is read from `config/rules_engines.json`.

Current-deck-specific inferred card/role records needed to load the provisional RogShai runtime baseline live in explicit overlay files under `data/decks/`; they do not silently promote candidate-pool coverage or external-rules validation.

Playstyle/administrative complexity is not an optimization prior. Deck strength, synergy, mana, interaction, resilience, matchup robustness and multiplayer scaling are evaluated first; subjective playstyle review is downstream only.

## Main current files

```text
data/decks/rogshai_current.txt
data/decks/rogshai_current.json
data/decks/manifest.json
data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json
data/collections/current/INACTIVE_FORMER_OWN_DECK_RELEASES.json
data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json
data/decks/rogshai_current_card_catalog_overrides.json
data/decks/rogshai_current_structural_overrides.json
data/sync/current_sources.json
config/rules_engines.json
```

The current project-context identity records global own-deck scope, runtime scope, optimization targets, unresolved operational baselines, source hashes and policy hashes separately.

Candidate evidence is deck-scoped. Candidate-pool identities bind the deck context to the inventory source, inventory snapshot, allocation snapshot and deck-specific eligibility snapshot; unresolved operational baselines do not receive fabricated deck hashes or speculative free allocations.

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

Normal users and agents use four deterministic workflow commands. They share one immutable project-context snapshot and never apply a deck change:

```bash
commander-lab decision prepare --root .
commander-lab decision run --remove "Flare of Duplication" --add-candidate-id "inventory/rootborn-defenses-677fdbcf" --root .
commander-lab decision diagnose comparison.json --root .
commander-lab decision bundle comparison.json --output-directory data/runs/decision_bundle --root .
```

The default FastAPI and MCP tool listings expose the same four contracts. The retained 100 low-level tools are available through the explicit `/v1/expert/tools` API or MCP `surface="expert"`; they are composable debugging and specialist primitives, not the normal agent surface. Keep-rule generation and cross-context validation are opt-in research work.

Before broad search, the workflow reports whether the current structural evidence can actually separate variants. A model-information limit stops seed-only escalation and produces a diagnostic next step. Only a preregistered `advance` decision can enter confirmatory finalist sensitivity.

Generic caller-supplied out-of-sample robustness is distinct from the sealed Optimizer-v2 holdout. Historical J-P5 holdout artifacts are regression/provenance evidence and are not opened by normal acceptance smoke tests.

The `synthetic/*` decks are technical engine-validation fixtures, not claims about real opponents.

## CI, acceptance and release ownership

- `CI`: generic repository quality and security.
- J-FINAL / J-P6 compatibility gates: semantic decision-workflow acceptance only.
- `Optimizer v2 Acceptance`: optimizer-specific semantic tests and CLI surface.
- `External XMage Integration`: real B3 external-rules-engine regression on relevant changes.
- `Windows Runtime Hygiene`: Windows-specific runtime/file-system behavior.
- `Release Artifacts`: packaging, checksums, installability and recovery roundtrip; it does not rerun the full generic test suite.

## Current optimization rule

No search result is automatically applied to a canonical/current deck. Candidate changes must remain read-only until explicitly accepted. Current operational baselines can be improved through the project’s paired comparison, commander-denial, ablation, out-of-sample robustness, sensitivity, pilot and opponent-ensemble workflows while preserving physical inventory constraints and evidence labels.
