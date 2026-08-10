# RogShai MVP – Next Step Handoff

Status date: 2026-08-10

## Readiness

- `ROGSHAI_FIRST_SIMULATION_READY = true`
- `ROGSHAI_FIRST_OPTIMIZATION_READY = true`
- Fresh-Rebuild bias gate: `PASS`
- MVP code commit: `a0c54276cb05eea7de589a83aa79045cb8626a17`
- Package: `commander-playtest-lab 1.15.0`
- Acceptance head: `f9ee2b63e7a9f77749325e0beaf1260ae997808d`
- CI: 346 passed / 1 expected External-Engine skip; Ruff, format, Mypy, compile, security, Windows hygiene and release artifacts passed.

## Canonical Fresh-Rebuild inputs

- RogShai candidate pool: 795 physically owned / Commander-legal / Jeskai-eligible candidate identities.
- Candidate content SHA-256: `43287c9d372c7d8ae5980f9ceea872fe55aa12e5af80cca2a9dec2e32946e39e`.
- Exact sorted candidate-name SHA-256: `44557d429d695d8c634210778c39c0507f5c87ee584c8b29dafedcb2dae64dc7`.
- K1 modeling coverage: 123 structurally modeled, 588 partially modeled, 84 structurally unmodeled.
- Partial/unmodeled cards remain eligible but may not receive an implicit quality score. Profile them sufficiently before model-dependent finalist decisions.
- Physical simultaneous buildability accounts for Korvold only as an availability constraint; current RogShai allocation/deck membership is not a quality prior.
- Basics use the project policy of at least 50 copies of each basic land type.

## Fresh-Rebuild blindness

Until Fresh finalists and a new blind holdout are frozen, do not load the current RogShai deck as quality information. Do not use historical includes/cuts, prior optimizer results, protected/favorite status, old RogShai package choices, or prior deckbuilding chats as priors.

The current RogShai list may be loaded only after the Fresh finalist/holdout freeze and must then be labeled `CONTROL_VARIANT`.

## Technical path proven by MVP

The current runtime accepts an arbitrary legal/physical 98-card RogShai mainboard plus Ishai + Rograkh and has end-to-end passing evidence for:

- `RogShaiPilot`;
- Structural Simulation;
- deterministic same-seed replay/comparison;
- paired variant comparison;
- card and package ablation;
- Commander Denial for Ishai, Rograkh and both;
- opponent-composition sensitivity;
- bounded legal variant/swap search and Pareto handling;
- provenance / RunIdentity boundaries;
- explicit opponent evidence boundaries.

These results are `structural_model_estimates`, not empirical win rates. XMage evidence remains separate `external_rules_engine` evidence and is not required for the Fresh-Rebuild structural search.

## Primary pod

Current primary 4-player context is RogShai plus:

1. High Perfect Morcant
2. Doom Prevails
3. Cosmic Spider-Man

No opponent frequency weights are assumed. Morcant/Cosmic uncertainty remains explicit; synthetic completion is not observation.

## Holdout rule

`J_HOLDOUT_v1` is already consumed validation evidence and is not unseen. The MVP consumed no new blind holdout.

After Fresh finalists are fixed, freeze one new holdout that was not used for architecture/search/tuning, document its identity, run it once on the finalists, and do not tune to it afterward. If a real technical bug invalidates that run, document invalidation before freezing a replacement.

## Deferred Roadmap J work

Forge/J-P3C, final provider selection, full external-engine automation, general J-P4/P5/P6 completion, universal Oracle grounding, real-play calibration and Korvold work remain deferred; none blocks this RogShai Fresh Rebuild.

## Shortest reproducible start instruction

Use `main` with MVP code commit `a0c54276cb05eea7de589a83aa79045cb8626a17` as the technical baseline, load the current Drive RogShai 795-card candidate universe under the K1/K2 Fresh-Rebuild/Bias/Mana/Commander-Mechanics/Multiobjective/Variant contracts, keep the current RogShai control hidden, construct materially different legal/physical 100-card Fresh variants, explicitly profile serious partial/unmodeled candidates, and evaluate them with the proven structural/paired/ablation/denial/sensitivity/search stack before freezing finalists and a new blind holdout.
