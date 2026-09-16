# WS232 Hidden-Information Impact

## Verdict: NO_CHANGE (guarantees intact, no canary rerun required)

WS232 makes no production change to test/runtime projection paths:

- `src/**` untouched (no Rules/pilot semantic change).
- `engine-bridge/src/main/**` untouched (no projection/redactor change).
- New code is test-only orchestration under
  `qualification/ws232-retention-nscoped-requalification/bin/` (runner,
  campaigns, sealers) plus `tests/qualification/` predicate tests.

## Artifact privacy (machine-checked)

- Every WS232 run log persists, per decision: offset, class, seat number,
  option-type census, selected types, numeric bounds/choices, turn/phase,
  life vector, board-public zone name-multisets (+public pt/counters/
  tapped), hand/library/exile COUNTS only.
- NEVER persisted: hands, libraries, labels, prompts, metadata contents,
  option IDs, UUIDs, actor IDs. One joint-leg prompt carrying a
  per-process UUID was captured, detected by audit, and scrubbed
  (min/max retained); capture now strips prompts at the source.
- Full-namespace scan: 0 files contain UUIDs, hands, libraries, labels,
  prompts, or metadata contents.
- Symmetric single-card/Lions decks make the focus-card match booleans
  design-public (no asymmetry to leak).

## Rerun rationale for canaries

Touched test/runtime projection paths: none (positive impact: none), so
privacy canaries are NOT rerun (contract: rerun only on positive impact).
The standing/authority/vocab suites covering the guarantees still pass
(see VALIDATION.md).
