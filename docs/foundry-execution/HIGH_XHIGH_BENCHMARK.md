# HIGH / XHIGH Benchmark Harness (Design Only)

No benchmark results are claimed. This document defines the replay schema so a
controlled comparison can be run later without disrupting active qualification work.

## Policy under test

Initial policy stands: HIGH default, XHIGH evidence-based escalation. The harness
exists to confirm or revise that policy, not to presuppose an outcome.

## Task classes

1. local compile defect;
2. bounded single-file bug;
3. multi-file harness defect;
4. identity/state semantic bug;
5. ambiguous engine-vs-adapter-vs-harness failure;
6. long test-fix loop;
7. unfamiliar subsystem investigation.

## Replay protocol

Each benchmark item replays one representative historical task from an identical
recorded source lock, once at `high` and once at `xhigh`, with disjoint worktrees.
Record per attempt: final correctness; root-cause correctness; completion;
model turns (if exposed); tool calls; token usage; build/test iterations;
unnecessary edits; scope violations; reverts; human interventions; evidence
correctness. Use `tools/foundry/metrics.py` with `task_class` set to one of the
seven classes above.

## Constraints

- Do not run expensive repetitions while any qualification campaign is active.
- No benchmark repetition may touch WS48/WS49 semantic surfaces or engine sources.
- Missing measurements stay absent. A comparison with insufficient data is
  `UNKNOWN`, not a policy argument.
