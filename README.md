# Commander Playtest Lab

Local, reproducible decision system for Commander deck validation, Structural simulation, pilot/ensemble analysis, paired comparisons, ablation, holdout, sensitivity and constrained optimization.

## Current repository truth — 2026-08-21

The canonical `main` baseline for this repair is:

- commit `e8effd269252da93577c8142e48ec4286b21bfe8`
- tree `ba1ff255d195ea7ddf701fc381ea9252ed6758f3`
- package `1.23.0`
- merged PR #99: Optimizer-v2 1E/2F decision architecture

The current RogShai optimizer control is `data/decks/rogshai_current.json`:

- Ishai, Ojutai Dragonspeaker + Rograkh, Son of Rohgahh
- 100 cards total / 98-card library
- content hash `340370dee603f7673ddc1f6c9d193923859974e222acc993aae325fefc40ed01`
- photo-verified physical build used as the current RogShai control

This repository path is the operational RogShai optimizer target. It does **not** redefine the wider MTG project's ownership status of other decks. Kaervek remains opponent-only for this project workflow.

No search, confirmatory result, diagnostic, or holdout automatically mutates the canonical/current deck.

## Optimizer-v2 decision contract

The official path is:

```text
manifest -> preflight -> run/search -> mechanics-fidelity gate -> confirm -> diagnose -> holdout
```

PR #99 retired the old `effective_resolution`/0.375 promotion architecture in favor of:

- SESOI = 0.05, separate from precision;
- paired sequential confirmatory looks at 128 / 256 / 512 / 1024 / 2048;
- multiplicity control;
- MCSE gate;
- seed stability;
- seat, pilot and opponent robustness;
- fresh critical diagnostics;
- a single frozen challenger before a fresh single-look sealed holdout.

The fidelity repair adds a question-specific mechanics contract. Exploratory Structural screening may still use bounded approximations, but confirmatory promotion is allowed only when every changed card is classified as `MECHANISTICALLY_SUPPORTED` or `APPROXIMATED_DECISION_SAFE`. `TACTICAL_REQUIRED`, `EXTERNAL_RULES_REQUIRED`, `APPROXIMATED_SCREENING_ONLY` and `UNSUPPORTED` changes fail closed for Structural confirmatory decisions unless an appropriate validated higher layer is available.

Legacy advancement APIs remain importable only for archival compatibility and cannot authorize confirmatory advancement.

## Evidence boundary

Simulator outputs are `structural_model_estimates`. They are not empirical win rates and are not external-rules-engine evidence. The Tactical Oracle is a separate bounded abstraction. XMage/Forge evidence may only be called `external_rules_engine` when a real provider run was actually executed and validated for the relevant scenario class.

A known semantic profile is not equivalent to mechanistic support. Current card facts such as `type_line` and simple mana-pip multiplicity override legacy Structural name tables in the official optimizer materialization path. Mechanics that need exact targets, modes, payment resources, stack sequencing, combat assignment, attachments, trigger copying or other rules-complete state are routed to a higher evidence layer or fail closed.

Structural semantic-model changes invalidate prior confirmatory mechanics evidence with `STALE_MODEL_VERSION`; a different Git commit alone is not treated as a sufficient semantic compatibility claim.

## Main current files

```text
data/decks/rogshai_current.txt
data/decks/rogshai_current.json
data/decks/manifest.json
data/decks/rogshai_current_card_catalog_overrides.json
data/decks/rogshai_current_structural_overrides.json
data/decision/DECISION_CONTRACT_CURRENT.json
data/sync/current_sources.json
src/commander_lab/whole_deck/mechanics_fidelity.py
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

## Source freshness

Dated `data/canonical_import/...` snapshots are historical/regression provenance, not current own-deck or current-rules truth. Current RogShai decisions must resolve through the current deck, current collection/candidate registries, current opponent registries/ensembles, current decision contract, CKB and semantic projection. Historical Korvold rules scenarios may remain useful as generic regression coverage but do not define the current RogShai optimizer input.

## Current optimization rule

Candidate changes remain read-only until explicitly accepted. The baseline can be evaluated through paired comparison, commander-denial, ablation, holdout, sensitivity, pilot and opponent-ensemble workflows only within the evidence layers that are valid for the mechanics involved.
