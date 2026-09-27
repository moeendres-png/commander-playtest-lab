# Next step handoff — J-P0 → J-P1

## P0 content state

P0 implementation is locally complete and prepared for one final GitHub integration cycle.
The post-merge Drive closeout is the authority for the final merge SHA and remote-gate results.

## What P0 establishes

- universal typed RunIdentity schema `1.0.0`;
- deterministic run hashing/serialization;
- explicit `PRESENT / NOT_APPLICABLE / UNKNOWN / MISSING_REQUIRED` identity states;
- fail-closed prepared-source/deck/pilot/ensemble/worktree stale detection;
- explicit historical replay mode;
- RunIdentity carried by ToolService/API/MCP/agent/reporting decision paths;
- CLI structural batches emit RunIdentity and a runtime sidecar;
- Tactical and external provider identity are not conflated;
- J eval registry frozen;
- fresh `J_HOLDOUT_v1` sealed, 12 cases, both pilots, pod sizes 3/4/5, not evaluated in P0;
- old G holdout retained as legacy regression evidence only.

## Required P1 behavior

J-P1 starts only from the post-P0 canonical main recorded in Drive.

P1 must revalidate current reliability debt rather than merge either historical strict-quality branch.
Priority candidates include:

- strict blocking whole-project Ruff;
- strict blocking Mypy;
- deterministic seeds across processes/worker counts;
- runtime hygiene and clean-tree guarantees;
- Windows parity;
- dependency/security gates;
- packaging/recovery roundtrip.

Do not alter J_HOLDOUT_v1 or inspect its outcomes for tuning.

## Evidence boundaries

- Structural estimates are not empirical winrates.
- Tactical Oracle is not an external rules engine.
- Real external-engine validation remains pending for J-P3.
- Real-playtest calibration remains inactive project scope.
- No automatic canonical deck/inventory/purchase/allocation changes.

## Package / release

P0 changes package code and targets `1.14.0`.
A refreshed commit-specific recovery snapshot is required after merge.
No public GitHub release is required in P0; final release governance remains a J-FINAL decision.
