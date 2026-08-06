# Phase 12.3 – Multi-Pilot Ensembles

Status: `multi_pilot_system_ready_with_limitations`

## Implemented

- Five specialized Korvold profiles and five specialized RogShai profiles.
- Versioned pilot registry with parameter hashes, source rules, utility weights, information policies, allowed deviations and supported deck hashes.
- Equal and custom-weight ensembles, worst-pilot and median-pilot summaries, robustness spread and deck-pilot interaction reporting.
- Decision traces with trigger phases, selected actions and average utility decomposition.
- Seven Function Tools for profile inspection, benchmarks, comparisons, ensembles, cross-pilot variant tests and reports.
- Ten requested Golden Scenario definitions.
- Explicit no-omniscience and legal-action-only validation.

## Validation

- Baseline restored from 1.2.0: 181 passed, 1 skipped, 2 failed because a referenced generated replay was absent from the repository artifact.
- Recovery fix: replay evidence moved to `tests/fixtures/replays/phase12_2_structural_replay.jsonl`.
- Final Phase-12.3 suite: 195 passed, 1 skipped, 0 failed.
- Saved structural ensemble benchmark: four games per profile against the configured local opponent pod.

No deck, inventory or allocation file was modified. No proposed variant was applied automatically.
