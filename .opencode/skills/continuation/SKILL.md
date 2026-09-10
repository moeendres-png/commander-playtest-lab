---
name: continuation
description: Resume a workstream from durable Git and state-file reality without rerunning valid evidence.
---

# Continuation

Use this after session loss, compaction, or handoff to resume the active workstream.

## Procedure

1. Verify branch, worktree identity, HEAD, tree, and `git status`. The checkout must
   match `.foundry/WORKSTREAM_STATE.yaml` or the mismatch must be resolved first.
2. Read the state file: objective, Source Lock, validated gates, invalidated gates,
   do-not-rerun evidence, current failure, current hypothesis, files modified,
   remaining scope, Exact Next Action.
3. Reverify only the mutable facts needed for the next action. Do not rerun valid
   evidence for reassurance.
4. Continue from the Exact Next Action. If the state file conflicts with Git, test,
   or artifact reality, reality wins — record the discrepancy and proceed from the
   newest genuinely verified state.
5. Re-enter the autonomous loop directly: a resolved technical decision recorded in
   state (`technical_decisions`, updated hypothesis, next action) is a continuation
   signal, not a handoff to the Coordinator. Resume inspection, validation, and
   progress without asking for reassurance.

## Rules

- Compaction summaries are never authoritative. The durable source is Git plus the
  state file plus sealed evidence.
- Do not restart validated phases without a concrete invalidation reason.
- State identity (schema 2.0): `audit_base_sha` is the immutable source lock;
  `validated_head` is the newest commit with actual validation evidence (`null`
  means none beyond the base — never assume); `state_written_against_head` is
  descriptive only. Live `HEAD` (via `state.py --workdir`) wins over all three.
