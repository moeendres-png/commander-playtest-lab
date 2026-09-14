---
name: continuation
description: Resume a workstream from durable Git and state-file reality without rerunning valid evidence.
---

# Continuation

Use this after session loss, compaction, or handoff to resume the active workstream.

## Procedure

1. Verify branch, worktree identity, HEAD, tree, and `git status`. The checkout must
   match the explicit state file or the mismatch must be resolved first.
2. Read the state file: objective, Source Lock, validated gates, invalidated gates,
   do-not-rerun evidence, current failure, current hypothesis, files modified,
   remaining scope, Exact Next Action.
3. Reverify only the mutable facts needed for the next action. Do not rerun valid
   evidence for reassurance.
4. Continue from the Exact Next Action. If the state file conflicts with Git, test,
   or artifact reality, reality wins — record the discrepancy and proceed from the
   newest genuinely verified state.
   Conditional continuation past the Exact Next Action is bounded by the state's
   `continuation_policy` (default `EXACT_NEXT_ACTION_ONLY`: execute exactly the
   binding action, checkpoint, stop). Under `BOUNDED_IN_SCOPE` you may advance
   only through declared `remaining_scope` items that are inside `in_scope`,
   outside `out_of_scope`, not blocked by `authority_gates`, and free of
   branch/worktree-creation, remote-mutation, or provider-switch shapes —
   checkpointing state per milestone. The first bound violation stops that line
   fail-closed (`BLOCKED` + `AUTHORITY_GATE` entry where applicable). A capsule
   showing `remaining_scope`/`do_not_rerun` counts without content means escalate
   to `--full`/file read, never choose silently.
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
