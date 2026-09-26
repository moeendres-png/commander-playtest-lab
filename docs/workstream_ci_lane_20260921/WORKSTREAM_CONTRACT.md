# Workstream Contract — R20 CI Cardinality Lane (2026-09-21)

## Objective

Reproducible per-count qualification in CI: extend
`xmage-full-game-conformance.yml` with bounded live smokes (2,3,5,6 at
calibrated targets) + fail-closed probe (7P) + trigger parity
(variable-player test on PR; agents/models/candidates on push).
Update the satisfiable parked lane tests to 2–6/7P expectations.
Environment-identity battery stays parked (separate lock/container
regime, documented, untouched).

## Source Lock

- Base: R19 tip `107db18976c76ead4f328d7cdec0de7de8a4eb1d` (Lab 2–6P).
- This branch: `cpl/ci-cardinality-lane-20260921`.
- This worktree: `/home/moeen/code/ws-ci-cardinality-lane-20260921`.
- Repo `moeendres-png/commander-playtest-lab`. No Forge/mage edits.
  No push/merge.

## In Scope

- Workflow steps: 4 smoke invocations + fail-closed probe + trigger
  additions (exact strings the parked tests assert, extended to 6/7P).
- Parked-test updates strictly to implemented reality (2,3,5,6@targets;
  fail-closed 7; no assertion weakening — every asserted invocation
  exists and runs).
- Validation: parked lane tests green + full python suite
  no-new-failures + YAML parses + script entrypoints verified
  (live smoke commands already proven in R19).

## Out of Scope

- Environment-identity battery (lock.txt regime, containers, digests —
  separate tier; stays parked with rationale).
- Other workflows; engine/bridge/pilot semantics; decks; FULL107;
  promotion; Freeze; Provider.

## Ownership

Single writer: this session on this branch/worktree only. All other
Lab worktrees/branches read-only (three-deck/physical-pool especially).

## Dependencies

- R19 tip (calibrated 6P targets + gates); parked tests (intent).

## Hard Gates

- Every asserted workflow string must correspond to a real executed
  step (no aspirational text). Tests assert implementation, never
  vice versa.
- No weakening: calibrated targets unchanged (2:25, 3:25, 5:45;
  6:55 live-calibrated in R19).
- YAML must parse; job structure preserved (single conformance job).

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no test edits that merely mirror text without
the step existing; no CI timeout gambling (bounded smokes only, full
gate untouched).

## Evidence Requirements

Workflow diff + parked-test results + full-suite delta + YAML proof.

## Persistence

Scoped validation, state update, focused local commit. End with §13
handoff.

## Stop Conditions

Stop when the lane tests for counts/fail-closed/smoke/triggers are
green with the steps implemented, or a genuine terminal blocker
appears (CI-owner conflict → park + escalate). Remediable failures
are diagnostic.
