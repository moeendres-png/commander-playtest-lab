# Commander Simulation Foundry — Dual-Lane Execution Playbook

**Purpose:** run the same Foundry workstream efficiently across two execution lanes without changing Source Truth or evidence standards:

1. **ChatGPT Work / Codex lane** — high-capability, quota-sensitive, context-efficient execution.
2. **OpenCode + Muse Spark 1.3 Contributor Free lane** — comparatively generous long-running implementation/test/repair execution.

This document is subordinate to `AGENTS.md`, the active Workstream Contract, current Git state, immutable qualification artifacts, and current Magic authority.

---

## 1. Core architecture

The two lanes share one durable state model:

```text
AGENTS.md
+ active Workstream Contract
+ exact Git branch/head
+ .foundry/WORKSTREAM_STATE.md
+ persisted evidence
+ focused checkpoint commits
+ final self-contained handoff
```

The conversation/session is never the authoritative state container.

A lane switch must be possible without replaying the prior chat or asking the previous model to summarize its private reasoning.

---

## 2. Lane A — ChatGPT Work / Codex: quota-efficient high-capability mode

Use this lane when the task benefits materially from stronger repository reasoning, browser/computer workflows, cross-file execution, integrated review, or difficult diagnosis.

### Resource posture

Treat Work/Codex capacity as valuable and finite.

Do not spend it on unnecessary repository ingestion or repetitive mechanical loops that can be delegated safely to Muse later.

### Start algorithm

On every new or resumed substantial task:

1. verify repository, branch, head, and clean/dirty status;
2. read `AGENTS.md`;
3. read only the active Workstream Contract;
4. read `.foundry/WORKSTREAM_STATE.md` if present;
5. inspect only files/tests named by the contract/state first;
6. broaden search only when evidence requires it;
7. verify only mutable facts required for the next technical action.

Do **not** begin with a full-repository scan unless the workstream is explicitly an architecture-wide audit.

### Context economy rules

Prefer:

- exact file paths over broad directory reads;
- targeted search terms over full-tree inspection;
- the current failing test/log excerpt over complete historical logs;
- machine-readable evidence summaries over raw artifact dumps;
- current contract + state over historical chat transcripts;
- one coherent terminal objective per run;
- the smallest authoritative validation before full suites.

Avoid:

- re-reading already verified unchanged files;
- re-running expensive full qualification after every small edit;
- copying `AGENTS.md` into task prompts;
- loading all old handoffs merely for context;
- using Work for long mechanical formatting or repetitive test-generation loops when semantics are already fixed.

### Preferred Work/Codex responsibilities

Use this lane preferentially for:

- architecture decisions;
- difficult root-cause analysis;
- provider-vs-engine defect classification;
- MTG rules / Oracle-sensitive interpretation;
- hidden-information and RNG/concurrency design;
- high-blast-radius Rules-Core changes;
- exact task decomposition before implementation;
- independent review of Muse-generated decision-critical changes;
- final adjudication of qualification evidence.

### Validation economy

Use a validation ladder:

1. exact reproducer;
2. directly neighboring tests;
3. affected subsystem suite;
4. generic CI gates only when warranted;
5. full qualification only when the contract requires it.

A smaller passing test is not allowed to substitute for a larger required gate; the ladder only avoids premature expensive runs.

### Persistence cadence

Checkpoint whenever a material independently validated milestone is reached, not after trivial edits.

Each checkpoint should record:

- exact head;
- validation command/result;
- evidence path/run ID;
- current blocker classification;
- exact next action.

This allows Work to stop at quota pressure without losing the state required by Muse.

---

## 3. Lane B — OpenCode + Muse Spark 1.3: generous implementation mode

Use Muse as a high-capacity implementation worker while the free endpoint remains available.

The Free SKU has no published contractual unlimited quota. Therefore the correct policy is **generous execution + frequent durable checkpoints**, not an assumption of infinity.

### Resource posture

Muse may spend more tool calls and context on:

- multi-file implementation;
- codebase exploration within a bounded workstream;
- compile/test/fix loops;
- regression-test expansion;
- provider adapters;
- state-loader work after semantics are fixed;
- evidence serialization;
- repetitive but nontrivial refactors;
- documentation tied to verified code.

Do not impose a small artificial step limit on the primary implementer.

### Autonomy posture

Within the active branch and Workstream Contract, Muse should normally:

1. reproduce;
2. diagnose;
3. implement;
4. test;
5. repair remediable failures;
6. checkpoint validated progress;
7. continue automatically until complete or terminally blocked.

It should not ask permission after every ordinary file edit or local test.

### Safety boundary

Muse still must not independently redefine:

- Magic rules semantics;
- architecture authority;
- qualification denominator/expected results;
- hidden-information policy;
- Rules randomness ownership;
- provider-vs-engine blame without required evidence;
- final production-provider PASS.

Remote/destructive operations remain approval-gated by `opencode.jsonc`.

---

## 4. Routing rule

Default routing for one workstream:

```text
high-capability analysis / source lock / contract
    -> Work/Codex

bounded implementation / test / repair
    -> Muse when appropriate

hard blocker or semantic ambiguity
    -> Work/Codex

long mechanical continuation
    -> Muse

final decision-critical review / evidence adjudication
    -> Work/Codex
```

Do not switch merely because a test fails. Switch when the **kind of work** changes or the current lane becomes capacity-constrained.

---

## 5. Work -> Muse handoff trigger

A Work/Codex task is ready for Muse when all of these are true:

- one terminal engineering objective is defined;
- the relevant architecture/rules semantics are fixed enough to implement;
- active branch/head is known;
- starting files/tests are named;
- acceptance criteria are executable;
- unsupported behavior/fail-closed requirements are explicit;
- `.foundry/WORKSTREAM_STATE.md` identifies the exact next action;
- no unresolved authority choice must be guessed by Muse.

At that point, prefer handing off instead of spending high-capability quota on mechanical implementation loops.

---

## 6. Work -> Muse handoff packet

The handoff should be small and repository-centered:

```text
COMMANDER SIMULATION FOUNDRY — WORK -> MUSE CONTINUATION

Continue the existing workstream. Do not restart it.

Read in order:
1. AGENTS.md
2. active Workstream Contract
3. .foundry/WORKSTREAM_STATE.md
4. exact checkpoint commits and files/tests named there

Verify current branch/head and mutable facts required for the next action.

Terminal objective:
[one objective]

Implementation boundary:
[what is already decided; what must not change]

Exact next action:
[copied from verified workstream state]

Validation required:
[commands/gates]

Continue automatically through technically remediable in-scope failures.
Checkpoint every material validated milestone.
Do not push/merge without authorization.
Stop only for a proved terminal blocker or unresolved semantic/authority choice.
```

Do not attach the entire Work transcript.

---

## 7. Muse -> Work handoff trigger

Return to Work/Codex when any of these occurs:

- Muse reaches a genuine architecture/rules ambiguity;
- two substantive repair attempts fail on the same nonlocal blocker;
- a high-blast-radius Rules-Core change becomes necessary;
- hidden-information or RNG/concurrency semantics require adjudication;
- provider-vs-engine defect classification is uncertain;
- final qualification PASS/FAIL affects provider selection;
- Muse rate-limits or becomes unavailable and remaining work warrants the higher-capability lane;
- independent review is required.

---

## 8. Muse -> Work handoff packet

```text
COMMANDER SIMULATION FOUNDRY — MUSE -> WORK CONTINUATION

Continue the existing workstream from durable repository state. Do not restart it.

Read:
1. AGENTS.md
2. active Workstream Contract
3. .foundry/WORKSTREAM_STATE.md
4. current git status/head and checkpoint commits
5. exact evidence/tests named by the state file

Do not trust prior-model prose as Source Authority.
Reverify only mutable facts needed for the next action.

Current blocker / review question:
[one precise question]

Terminal objective:
[objective]

Do not redo validated work unless fresh evidence invalidates it.
Persist every new material milestone and return the standard Foundry handoff.
```

---

## 9. Quota/capacity exhaustion procedure

### If Work/Codex capacity is exhausted

1. do not start over in Muse;
2. ensure the latest material checkpoint is committed;
3. update `.foundry/WORKSTREAM_STATE.md` with exact next action;
4. open OpenCode on the same branch/checkout;
5. use the Work -> Muse continuation prompt;
6. rerun only the smallest validation needed to trust the resumed state;
7. continue.

### If Muse rate-limits

1. preserve the working tree;
2. commit any coherent validated checkpoint;
3. update workstream state;
4. resume later with Muse or switch to Work/DeepSeek from the same persistent state;
5. do not infer PASS from interrupted execution.

---

## 10. Same evidence standard in both lanes

Resource strategy may differ. Correctness standards may not.

Both lanes must preserve:

- Source Truth hierarchy;
- Rules-Core / pilot separation;
- fail-closed unsupported paths;
- immutable qualification obligations;
- exact source/build identity;
- hidden-information guarantees;
- RNG/replay authority;
- required multiplayer/Commander scope;
- runtime evidence before runtime PASS.

`UNKNOWN != PASS` in both lanes.

---

## 11. Recommended work-package size

### Work/Codex

Prefer narrowly bounded high-information tasks:

- one difficult diagnosis;
- one architecture decision;
- one high-risk patch plus focused validation;
- one evidence adjudication;
- one precise implementation packet for Muse.

### Muse

Prefer larger coherent implementation units:

- one bounded feature end-to-end;
- implementation + regression tests + compile/test/fix loop;
- one provider remediation through scoped qualification;
- one mechanical migration with validation.

Do not fragment a single correctness invariant merely to save tokens.

---

## 12. Operational default

For future Foundry workstreams, use this default unless the active contract overrides it:

```text
Work/Codex:
  verify -> reason -> decide -> specify -> review

Muse/OpenCode:
  inspect -> implement -> test -> repair -> checkpoint -> continue
```

The repository state, not the model session, connects the two.
