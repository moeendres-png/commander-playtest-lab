# Commander Simulation Foundry — Dual-Lane Execution Playbook

**Purpose:** run one Foundry workstream efficiently across an authority/integration lane and a high-capacity implementation lane without changing Source Truth or evidence standards.

1. **ChatGPT / Work / Terra / Sol lane** — source truth, authority, difficult diagnosis, integration, adjudication and high-risk reasoning.
2. **OpenCode + Muse Spark 1.3 Contributor Free lane** — primary substantial bounded implementation/test/repair execution.

This document is subordinate to `AGENTS.md`, the active Workstream Contract, current Git state, immutable qualification artifacts, current Magic authority, and `docs/agent-workflows/MUSE_DATA_BOUNDARY.md`.

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

A lane switch must be possible without replaying the prior chat or asking the previous model to summarize private reasoning.

---

## 2. Lane A — ChatGPT / Work: authority and integration

Use this lane preferentially for:

- architecture decisions;
- current-authority / MTG rules adjudication;
- difficult root-cause analysis;
- provider-vs-engine classification;
- hidden-information and RNG/concurrency design;
- high-blast-radius Rules-Core changes;
- fresh source locks and dependency reconstruction;
- exact task decomposition before implementation;
- independent review of Muse-generated decision-critical changes;
- final adjudication of qualification evidence.

### Work-side default

Use **Terra High** as the normal Work-side owner/integrator.

Escalate to **Sol High** only for genuinely hard nonlocal/high-blast-radius reasoning, foundational architecture, MTG semantic disputes, difficult hidden-information/RNG/concurrency questions, or after two materially distinct Terra attempts fail on the same hard blocker.

Luna is not part of the active Foundry routing policy.

### Resource posture

Do not spend Work capacity on long repetitive implementation/test/fix loops once semantics and acceptance criteria are sufficiently fixed for Muse.

### Start algorithm

1. verify repository, branch, head and clean/dirty status;
2. read `AGENTS.md`;
3. read only the active Workstream Contract;
4. read `.foundry/WORKSTREAM_STATE.md` if present;
5. inspect only files/tests/evidence named by the contract/state first;
6. broaden search only when evidence requires it;
7. verify only mutable facts required for the next technical action.

### Validation economy

Use the smallest authoritative discriminator first, then broaden to the exact contracted gate.

---

## 3. Lane B — OpenCode + Muse Spark 1.3: primary implementation worker

Use Muse by default for substantial bounded coding once authority and semantic constraints are fixed enough to implement safely.

### Good Muse work

- multi-file implementation;
- provider adapters and state loaders;
- ordinary bugs/refactors;
- APIs/integration code;
- test-suite expansion;
- compile/test/fix loops;
- deterministic evidence/tooling;
- larger mechanical migrations;
- project setup/build/provisioning;
- external-engine integration work when contract semantics are fixed.

When the live OpenCode model catalog exposes variants, prefer Muse `high` for substantial implementation and reserve `xhigh` for genuinely difficult nonlocal debugging/integration. Do not invent a variant name that the live catalog does not expose.

### Autonomy posture

Within the active branch and Workstream Contract, Muse should normally:

1. reproduce;
2. diagnose;
3. implement;
4. test;
5. repair remediable failures;
6. checkpoint validated progress;
7. continue automatically until complete or terminally blocked.

### Authority boundary

Muse must not independently redefine:

- Magic rules semantics;
- architecture authority;
- qualification denominator/expected results;
- hidden-information policy;
- Rules randomness ownership;
- materially ambiguous provider-vs-engine blame;
- Architecture Freeze;
- final decision-critical qualification PASS.

Return those questions to Terra/Sol.

### Project-data boundary

Muse may use all project-relevant technical information needed for implementation, including Foundry source/tests/docs/config, qualification fixtures/evidence/logs/artifacts, external engine/provider source, Magic card data, decklists and owned-card inventories.

Keep unrelated personal/private data and raw credential values out of Muse context. Authenticated tools may consume configured credentials without exposing the values. See `MUSE_DATA_BOUNDARY.md`.

---

## 4. Routing rule

Default flow:

```text
authority / source lock / hard semantics
    -> Terra/Sol

bounded implementation / test / repair
    -> Muse

hard coding blocker with fixed semantics
    -> Muse High, then Muse XHigh if available/justified

semantic / architecture ambiguity
    -> Terra/Sol

final decision-critical review / evidence adjudication
    -> Terra/Sol
```

Do not switch merely because a test fails. Switch when the kind of work changes or a lane reaches its authority boundary.

---

## 5. Work -> Muse handoff trigger

A task is ready for Muse when:

- one terminal engineering objective is defined;
- architecture/rules semantics are fixed enough to implement;
- active branch/head is known;
- starting files/tests are named;
- acceptance criteria are executable;
- unsupported behavior/fail-closed requirements are explicit;
- `.foundry/WORKSTREAM_STATE.md` identifies the exact next action when used;
- no unresolved authority choice must be guessed by Muse.

Prefer handing off rather than consuming Work capacity on long implementation loops.

---

## 6. Work -> Muse handoff packet

```text
COMMANDER SIMULATION FOUNDRY — WORK -> MUSE CONTINUATION

Continue the existing workstream. Do not restart it.

Read in order:
1. AGENTS.md
2. active Workstream Contract
3. .foundry/WORKSTREAM_STATE.md if present
4. exact checkpoint commits and files/tests named there
5. MUSE_DATA_BOUNDARY.md when this is a Muse session

Verify current branch/head and mutable facts required for the next action.

Terminal objective:
[one objective]

Implementation boundary:
[what is already decided; what must not change]

Exact next action:
[copied from verified workstream state]

Validation required:
[commands/gates]

Use all project-relevant technical data/tools needed for the task. Keep unrelated personal/private data and raw credential values out of Muse context.
Continue automatically through technically remediable in-scope failures.
Checkpoint every material validated milestone.
Do not push/merge without authorization.
Stop only for a proved terminal blocker or unresolved semantic/authority choice.
```

---

## 7. Muse -> Work handoff trigger

Return to Work/Terra/Sol when any of these occurs:

- genuine architecture/rules ambiguity;
- high-blast-radius Rules-Core change;
- hidden-information or RNG/concurrency semantics require adjudication;
- provider-vs-engine defect classification remains materially uncertain;
- final qualification PASS/FAIL affects provider selection;
- independent decision-critical review is required;
- Muse becomes unavailable and remaining work warrants the authority/integration lane.

A difficult implementation bug with fixed semantics is not automatically a Work handoff; Muse High/XHigh may continue when technically appropriate.

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

## 9. Capacity exhaustion procedure

### If Work capacity is constrained

1. persist the latest material checkpoint;
2. update workstream state with the exact next action;
3. give Muse the bounded continuation packet;
4. rerun only the smallest validation needed to trust the resumed state;
5. continue.

### If Muse rate-limits

1. preserve the working tree;
2. commit any coherent validated checkpoint;
3. update workstream state;
4. resume later with Muse or another provider from the same persistent state;
5. do not infer PASS from interrupted execution.

---

## 10. Same evidence standard in both lanes

Both lanes preserve:

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

### Terra/Sol

Prefer narrowly bounded high-information tasks:

- one difficult diagnosis;
- one architecture/authority decision;
- one high-risk patch where semantics remain coupled;
- one evidence adjudication;
- one precise implementation packet for Muse.

### Muse

Prefer larger coherent implementation units:

- one bounded feature end-to-end;
- implementation + regression tests + compile/test/fix loop;
- one provider remediation through scoped implementation evidence;
- one mechanical migration with validation.

Do not fragment a single correctness invariant merely to save tokens.

---

## 12. Operational default

```text
Terra/Sol:
  verify -> reason -> decide -> specify -> integrate -> adjudicate

Muse/OpenCode:
  inspect -> implement -> test -> repair -> checkpoint -> continue
```

The repository state, not the model session, connects the lanes.
