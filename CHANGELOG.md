# Changelog

## 1.10.3 – Phase 12.15–12.17 completion repair

- Replaced synthetic-only policy claims with real Structural Simulator policy-tournament and same-policy self-play execution across 3/4/5-player pods.
- Preserved exact Cosmic (4/96), Morcant (53/47), and Doom precon-plus-unknown-upgrade uncertainty boundaries without inventing cards.
- Expanded the read-only physical candidate universe to 569 structurally screenable cards with conservative `project_inferred` semantics and uncertainty penalties.
- Executed politics/pod sensitivity and relevant Tactical Oracle gates in the multi-fidelity optimizer; external provider evidence remains strictly gated on a real runtime.
- Updated MCP to the stateless 2026-07-28 core with separate 2025-11-25 legacy compatibility and real in-flight stdio cancellation.
- Added OpenAI Agents SDK stdio configuration, while keeping the live SDK test blocked when `openai-agents` is absent.
- Preserved canonical deck, inventory and allocation data unchanged and applied no recommendation.

## 1.10.1 – Phase 12.8–12.10 completion audit

- Completed Mulligan Lab follow-up evaluation with controlled opening-hand injection into full Structural Simulator games.
- Added hand-type summaries and executed primary, holdout, opponent-ensemble and multi-pilot keep-rule validation.
- Upgraded counterfactual replay to explicit public-state deltas, four hidden-information policies and real Tactical Oracle invocation without external-engine claims.
- Added event-log-derived per-card and pilot instrumentation for decision diagnostics.
- Replaced the load-only ten-extension smoke with an executed 10/10 integration workflow retaining source hashes and validation levels.
- Added regression tests for context-sensitive mulligans, full follow-ups, Tactical Oracle counterfactuals and event-derived diagnostics.
- No canonical deck, inventory or allocation data changed.

## 1.7.0 - 2026-08-06
- Added versioned opponent ensembles for Cosmic Spider-Man, Morcant Elves and Doom Prevails with uncertainty-aware robustness tools.

## 1.6.0 - 2026-08-06
- Added append-only local meta learning, observed opponent profile versions, conservative shrinkage, drift and scenario tools.

## 1.5.0 - 2026-08-06
- Added complete source/artifact/derivation provenance graph, supersession and claim auditing.
- Added simulation identity hashes and six provenance tools.

# Changelog

## 1.4.0 - 2026-08-06

- Add weighted, explainable multi-archetype profiles and a versioned package registry.
- Add 19 curated Korvold/RogShai package IDs across 20 versioned records.
- Add package completeness, minimum-density, redundancy, orphan and diminishing-utility diagnostics.
- Add seven package tools and extend package ablation, package search, deck inspection and meta comparison.
- Attach package identities to structural cards and expose them to specialized pilot scoring.
- Reject undersampled same-format co-occurrence clusters instead of treating them as confirmed packages.
- Preserve canonical decks, inventory and allocation unchanged; no automatic package application.

## 1.3.0 - 2026-08-06

- Add five realistic Korvold and five realistic RogShai pilot profiles.
- Add versioned pilot registry, information boundaries and deterministic parameter hashes.
- Add equal/custom pilot ensembles, worst/median pilot and robustness analysis.
- Add seven multi-pilot Function Tools and ten Golden Scenario definitions.
- Move Phase-12.2 replay evidence from an ignored generated path to a tracked fixture.
- Preserve canonical decks, inventory and allocation unchanged.

## 1.2.0 - 2026-08-06

- Added a safe Primer-to-Pilot rule DSL with fixed fields and operators; primer text is never executed.
- Added Markdown, plaintext, JSON, and manually curated primer imports.
- Added source-preserving, deck-hash- and format-scoped immutable policy overlays.
- Added conflict detection, explicit resolution strategies, alternative policies, and manual activation.
- Added seven structured toolserver functions for primer import, extraction, validation, compilation, comparison, evaluation, and conflict reporting.
- Added 14 active curated Korvold/RogShai rules and eight disabled automatic candidates.
- Added Golden, Tactical-Oracle, replay-coverage, security, provenance, and no-deck-mutation tests.
- External rules-engine validation and real-playtest calibration remain pending.


## 1.0.1 - 2026-08-05

- Run the Phase-10 API self-test by default so clean repository and Git-bundle restores do not depend on an untracked API-demo artifact.
- Accept both versioned API evidence and the in-process self-test evidence shape.
- Close all contract-test subprocess pipes explicitly to prevent order-dependent suite hangs.
- Preserve all external-engine and deck-change safety gates.

## 0.8.6 - 2026-08-05

- Added Phase 8.6 trust-boundary audit and regression tests.
- Prevented legacy/mock bridges from being promoted to external rules validation.
- Corrected Phase 8.5 contract coverage and readiness semantics.
- Added atomic artifact writes, run manifests, run verification and quarantine.
- Added SQLite integrity, migration, backup, restore and sealed experiment designs.
- Added scenario fixtures, replay debugger, structured logging and metrics.
- Added architecture-boundary, deterministic fuzz and mutation-guard tests.
- Added CI and an explicitly failing-until-real GitHub Actions XMage integration workflow.
- External engine validation remains pending.

## 0.9.0 - Phase 9 real playtest calibration

- Added versioned append-only real playtest datasets.
- Expanded CSV/XLSX/JSON import to all Phase-9 observations.
- Added sealed chronological or stable-hash train/validation splits.
- Added real-versus-structural distribution comparisons and bootstrap intervals.
- Added conservative validation-gated calibration profiles with no automatic application.
- Added Korvold draw, Ishai peak-power and archenemy metrics to structural outputs.
- Added Phase-9 CLI commands, template, documentation and validation runner.
- External rules-engine validation remains pending.

## 1.10.2 – Phase 12.11 final hardening

- Isolated the Phase-10 API self-test in a bounded subprocess to eliminate order-dependent shutdown hangs.
- Closed JSONL bridge streams and joined pump threads deterministically.
- Reused one tactical bridge process for the complete protocol-contract sweep.
- Isolated Phase-8.5 test process-state writes from canonical tracked status.
- Decoupled deterministic simulation run identity from random artifact-directory UUIDs.
- Added failing-first regression tests; no deck, inventory or allocation data changed.
