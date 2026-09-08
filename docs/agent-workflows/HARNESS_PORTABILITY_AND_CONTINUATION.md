# Commander Simulation Foundry — Harness Portability and Continuation Protocol

**Purpose:** make one repository workstream resumable across normal ChatGPT, ChatGPT Work when explicitly chosen by the user, Codex, OpenCode, and later coding-model/provider changes without transferring authority to any harness.

This protocol is subordinate to `AGENTS.md`, the active Workstream Contract, immutable qualification artifacts, current Magic authority, and fresh repository Source Truth.

---

## 1. Core rule

The **repository is the durable workspace**. A chat/session is an execution surface, not Source Authority.

A harness change must not require reconstructing the project from conversation history.

The portable state chain is:

```text
AGENTS.md
  + active Workstream Contract
  + exact Git branch / commits
  + .foundry/WORKSTREAM_STATE.md (resume pointer, when present)
  + persisted machine-readable evidence
  + self-contained handoff
```

No model transcript outranks this chain.

---

## 2. Responsibilities by layer

### `AGENTS.md`

Contains stable repository-wide policy:

- Source Truth;
- Rules-Core / pilot separation;
- fail-closed semantics;
- evidence semantics;
- persistence requirements;
- repository/build conventions;
- immutable-artifact rules.

Do not place current workstream status or volatile engine pins here.

### Workstream Contract

Contains the current objective and exact task authority:

- Objective
- Inputs
- Authority
- In Scope
- Out of Scope
- Dependencies
- Required Deliverables
- Hard Gates
- Evidence Requirements
- Stop Conditions

### `.foundry/WORKSTREAM_STATE.md`

Optional but strongly recommended for substantial long-running branches. It records the newest resumable checkpoint and exact next action.

It is **not** authority. If it conflicts with Git or current sources, Git/current sources win.

### Machine-readable evidence

Prefer JSON, checksums, test artifacts, CI/run identities, and exact source/build hashes for qualification claims.

### Final Handoff

At terminal workstream closeout, produce the self-contained Foundry handoff defined in `AGENTS.md`.

---

## 3. Standard start/resume algorithm for every harness

When beginning or resuming material work:

1. identify the repository and intended workstream branch;
2. verify `git status`, current branch, and exact current head;
3. read `AGENTS.md`;
4. locate/read the active Workstream Contract;
5. read `.foundry/WORKSTREAM_STATE.md` if present;
6. inspect the checkpoint commits and exact files/tests named there;
7. reverify mutable source locks needed for the next action;
8. continue from the newest genuinely verified persistent state;
9. do not redo completed work unless fresh evidence invalidates it.

If the local checkout is detached or on the wrong branch, correct that before editing.

---

## 4. Standard persistence algorithm

After each material independently validated milestone:

1. leave the tree in a coherent resumable state;
2. run the smallest authoritative scoped validation;
3. persist evidence/results needed for the claim;
4. update `.foundry/WORKSTREAM_STATE.md` if the branch uses it;
5. make a focused local commit;
6. record the exact resulting head and evidence identity;
7. continue automatically when remaining work is technically remediable and in scope.

For OpenCode, local commits are intentionally encouraged because upstream free-model rate limits are dynamic.

For any harness, `git push` and remote publication follow current user authorization and repository policy.

---

## 5. Normal ChatGPT / high-capability planning-review usage

Use normal high-capability chat for:

- architecture;
- rules/Oracle adjudication;
- difficult root cause;
- provider-vs-engine defect classification;
- differential interpretation;
- creation of bounded coding-agent Task Contracts;
- critical review of decision-relevant changes.

The preferred output passed to a coding harness is a **Task Contract**, not a full chat transcript.

---

## 6. ChatGPT Work usage

When the user explicitly chooses Work for a Foundry task, Work should operate on the same persistence model:

- use the exact Git branch/worktree;
- read the same `AGENTS.md` and Workstream Contract;
- verify live repository state before acting;
- persist material milestones and evidence;
- produce the same Foundry handoff schema.

Work is not allowed to grant itself stronger Source Authority merely because it can execute longer multi-step workflows.

Do not create parallel hidden architecture truth in Work-specific notes. Material conclusions must land in repository evidence/handoff form when they matter to later work.

---

## 7. OpenCode usage

OpenCode should be used as a comparatively high-capacity implementation harness.

Default project model while the free endpoint exists:

`opencode/muse-spark-1.3-contributor-free`

Operating style:

- one primary bounded objective per session;
- broad local read/edit/test freedom;
- continue through remediable failures;
- checkpoint commits after validated milestones;
- short continuation prompts after interruption;
- no need to paste `AGENTS.md` into task prompts;
- use `docs/agent-workflows/MUSE_SPARK_1_3_OPENCODE_HANDBOOK.md` for prompt-authoring guidance, not as a substitute for the active contract.

Because Contributor Free permits training on prompts/completions, do not provide secrets, credentials, private user data, or confidential sources to that endpoint.

---

## 8. Model/provider switch protocol

When switching Muse -> DeepSeek, OpenCode -> Codex, Work -> OpenCode, or any other harness/provider transition:

Do not hand off a giant conversation transcript.

The receiving harness reads:

1. `AGENTS.md`;
2. active Workstream Contract;
3. `.foundry/WORKSTREAM_STATE.md`;
4. current Git head / checkpoint commits;
5. exact named evidence/tests.

Then it independently verifies the next-action facts and continues.

Previous-model prose is provenance only.

---

## 9. Review independence

A same-model reviewer can catch ordinary bugs but does not provide strong independent evidence for high-risk semantic claims.

For changes affecting any of the following, prefer a higher-capability or independent review before production credit:

- Magic rules semantics;
- Architecture Freeze;
- provider-vs-engine blame;
- hidden-information admission;
- RNG/concurrency architecture;
- central Rules-Core behavior;
- qualification PASS used for provider selection.

The required evidence standard does not change with the reviewing model.

---

## 10. Workstream state lifecycle

### Create

For a substantial new branch, copy:

`docs/agent-workflows/WORKSTREAM_STATE_TEMPLATE.md`

to:

`.foundry/WORKSTREAM_STATE.md`

and fill it with the active branch state.

### Update

Update after material milestones, not after every trivial edit.

### Finalize

At workstream completion:

- ensure the final handoff is self-contained;
- set the state status to `COMPLETE`, `FAIL`, or `TERMINAL_BLOCKED` as justified;
- include final exact head/evidence;
- leave the exact next action empty only when the workstream is genuinely terminal and no dependency action remains.

### Do not merge stale transient state blindly

A branch-local `.foundry/WORKSTREAM_STATE.md` may be useful execution state but should not automatically become long-lived `main` truth. Treat it like other workstream evidence and decide explicitly at merge/reconciliation time whether it belongs in the target branch.

---

## 11. Minimal cross-harness continuation prompt

```text
COMMANDER SIMULATION FOUNDRY — CONTINUATION

Continue the existing workstream from durable repository state. Do not restart it.

Read AGENTS.md, the active Workstream Contract, and .foundry/WORKSTREAM_STATE.md if present. Verify git status, current branch/head, checkpoint commits, and only the mutable facts needed for the next action.

Do not redo validated work unless fresh evidence invalidates it. Continue through technically remediable in-scope failures. Persist every material verified milestone and finish with the Foundry handoff schema.

Terminal objective:
[objective]
```

---

## 12. Efficiency principle

The efficient unit of reuse is **verified durable state**, not cached conversation.

A high-quality continuation should usually require:

```text
small prompt
+ stable AGENTS.md
+ current Workstream Contract
+ branch-local state
+ exact source/evidence
```

rather than a large historical prompt.
