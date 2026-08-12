# Changelog

## 1.17.1 - 2026-08-12

- Binds decision-weighted Semantic Evidence to the fresh candidate/cut frontier before expensive paired simulation; material profile/projection conflicts are deferred for adjudication rather than silently promoted or rejected.
- Normalizes the public priority comparison path to the validated single-worker execution policy while preserving requested-worker provenance as execution metadata only.
- Allows the preregistered 1024 adaptive ceiling to use a bounded 300-second execution envelope without changing deck/simulation semantics or the four public workflows.
- Adds regressions for the Evendo-style semantic conflict, simple Opt agreement, worker fallback, full candidate recall, and the semantic-defer DecisionInformationState route.
- Keeps the canonical RogShai deck, inventory, allocations, opponent observations, and evidence boundaries unchanged.

## 1.17.0 - 2026-08-12

- Unifies current-truth and provenance boundaries for the post-J RogShai-only workflow; stale handoffs remain historical rather than competing current authority.
- Adds decision-weighted semantic-evidence provenance without introducing a universal card-power score or promoting LLM inference to canonical fact.
- Separates global governance identity from workflow-semantic identity so unrelated config/history changes no longer invalidate current paired structural cache entries, while declared dependencies fail closed.
- Adds `DecisionInformationState` to distinguish useful additional paired sampling from model-metric, tactical-evidence and opponent-uncertainty limits, including a material indifference stop region.
- Adds explicit observed/plausible-envelope/stress opponent uncertainty contracts that forbid synthetic assumptions from becoming observations.
- Ships a conservative quality-first adaptive budget policy over the existing CRN framework; noisy early elimination remains benchmark-only and blocked when it loses material finalists.
- Adds a provider-independent targeted tactical-evidence request/result boundary and consolidates current XMage/Forge technical truth as PARTIAL / `NO_PROVIDER_READY`.
- Simplifies the optional OpenAI path to one thin four-public-tool synthesis agent; deterministic validation, simulation, scheduling, hashing and provenance remain outside the LLM.
- Keeps RogShai decklist, inventory, physical allocations and real opponent observations unchanged.

## 1.16.0 - 2026-08-12

- Streamlined the end-to-end Build → Test → Diagnose → Bundle workflow to four public high-level tools, added deterministic model-informativeness/advancement gates, and reused immutable workflow state.
- Kept low-level optimization and diagnostic primitives behind the expert surface and preserved structural/tactical/external evidence boundaries.

## 1.15.0 - 2026-08-10

- Roadmap J-P2 modeling/data-quality candidate: separates active own optimization targets (Korvold/RogShai) from frozen opponent-only Kaervek across swap/package/allocation paths.
- Adds explicit opponent evidence taxonomy and validates current structural opponent evidence kinds without promoting unknown or synthetic slots to observation.
- Fixes current-opponent rules-coverage scoping so deck-specific gates no longer merge unrelated `opponent/*` versions.
- Corrects RunIdentity opponent/pod inference for multi-deck analysis contexts and removes stale protected-card metadata that no longer belongs to canonical current decks.
- Routes current opponent strategy labels to existing public-information archetype pilots instead of the catch-all GenericCommanderPilot, reducing systematic opponent-policy asymmetry without inferring hidden cards.
- Propagates explicit 1-based seat position into structural pilot decision state and golden-eval state so future seat-sensitive policy logic receives the actual scenario seat.
- Keeps canonical decks, inventory, purchases, physical allocations and opponent list contents unchanged; `J_HOLDOUT_v1` remains sealed during development.

## 1.14.1 - 2026-08-10

- Hardened Roadmap J-P1 reliability and reproducibility without changing canonical decks, inventory, purchases, allocations, opponent assumptions, pilot strategy, optimizer objectives, or simulation-model tuning.
- Added blocking whole-tree Ruff lint/format and strict Mypy gates; resolved the historical quality debt instead of reverting to changed-files-only checks or making Mypy non-blocking.
- Verified deterministic ProcessPool execution across workers 1/2/4, stable seed behavior across batch sizes/reruns, runtime clean-tree hygiene, canonical data audit, and package/RunIdentity version consistency.
- Fixed XLSX read-only worksheet compatibility and retained regression coverage for `read_only=True` imports.
- Final strict-quality candidate before this documentation-only closeout passed Ruff, Ruff format, Mypy over 127 source files, compileall, and the full suite with 336 PASS / 1 expected configured-XMage-or-Forge differential SKIP.
- Removed temporary J-P1 bootstrap workflows after controlled materialization of the validated quality fixes.
- `J_HOLDOUT_v1` remained frozen and unevaluated throughout J-P1; no holdout tuning was performed.

## 1.14.0 - 2026-08-09

- Completed Roadmap J-P0 universal fail-closed `RunIdentity`, canonical hashing/serialization, and Eval Registry foundations.
- Froze `J_HOLDOUT_v1` with 12 Korvold/RogShai cases across 3/4/5-player pods; mutable=false and used_for_tuning=false.
- Preserved Tactical Oracle and real external-rules-engine identities as distinct evidence levels and retained the project truth boundaries.
- Created and roundtrip-verified the P0 main recovery snapshot before opening J-P1.

## 1.13.3 - 2026-08-08

- Synchronized Korvold and RogShai program snapshots to the canonical 2026-08-07 final workbook without performing a new deck optimization.
- Synchronized the current physical inventory and opponent evidence boundaries, including Morcant 54 hard / 18 provisional / 28 synthetic-basic slots and verified Kaervek correction.
- Expanded structural identity/profile coverage from 161 to 195 retained card profiles and rebuilt rules coverage for the current candidate universe.
- Added explicit `commander-lab data audit` and non-mutating `commander-lab data sync --dry-run` source gates.
- Migrated 12 pilot profiles to current deck hashes, retained 13 compatible active primer rules, deactivated one stale combat-draw-aura rule, and classified 14 compatible versus 6 historical/stale package records.
- Replaced obsolete current-deck optimization test fixtures with explicit technical smoke candidates; no smoke candidate is an upgrade recommendation.
- Real playtest calibration remains outside the active project scope; external XMage/Forge validation remains pending with zero external observations.


## 1.13.2 - 2026-08-07

- Sync direct physical correction for `kaervek/current`: Midnight Reaper removed because the copy could not be found; Warstorm Surge / Anschwellender Kriegssturm from Leons Box added.
- Refresh Kaervek hash, role profile, registry, provenance and current inventory derivatives.
- Historical Kaervek snapshots/imports remain unchanged for reproducibility.

## 1.10.3 – Phase 12.15–12.17 completion repair

- Replaced synthetic-only policy claims with real Structural Simulator policy-tournament and same-policy self-play execution across 3/4/5-player pods.
- Preserved exact Cosmic (4/96), Morcant (53/47), and Doom precon-plus-unknown-upgrade uncertainty boundaries without inventing cards.
- Expanded the read-only physical candidate universe to 569 structurally screenable cards with conservative `project_inferred` semantics and uncertainty penalties.
- Executed politics/pod sensitivity and relevant Tactical Oracle gates in the multi-fidelity optimizer; external provider evidence remains strictly gated on a real runtime.
- Updated MCP to the stateless 2026-07-28 core with separate 2025-11-25 legacy compatibility and real in-flight stdio cancellation.
- Added OpenAI Agents SDK stdio configuration, while keeping the live SDK test blocked when `openai-agents` is absent.
- Preserved canonical deck, inventory and allocation unchanged and applied no recommendation.

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
