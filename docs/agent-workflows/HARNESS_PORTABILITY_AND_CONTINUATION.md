# Commander Simulation Foundry — Harness Portability and Continuation Protocol

**Purpose:** make one repository workstream resumable across normal ChatGPT, ChatGPT Work when explicitly chosen by the user, Codex, OpenCode, and later coding-model/provider changes without transferring authority to any harness.

This protocol is subordinate to `AGENTS.md`, the active Workstream Contract, immutable qualification artifacts, current Magic authority, fresh repository Source Truth, and for Muse sessions `docs/agent-workflows/MUSE_DATA_BOUNDARY.md`.

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

## 2. Active routing

Current Foundry routing is:

- **Normal GPT-5.6 Sol** — architecture, current-authority research, MTG rules adjudication, difficult root-cause work, critical review and bounded task design;
- **ChatGPT Work / Terra High** — source locks, dependency/integration ownership, difficult diagnosis, high-risk edits where semantics remain coupled, evidence adjudication and coordinator work;
- **OpenCode + Muse Spark 1.3 Contributor Free** — primary substantial bounded implementation/test/repair worker;
- **Codex Sol High** — targeted escalation for foundational, high-blast-radius or genuinely difficult nonlocal correctness problems.

Luna is not part of the active Foundry routing policy.

When the live OpenCode model catalog exposes Muse reasoning variants, prefer `high` for substantial implementation and reserve `xhigh` for genuinely difficult nonlocal debugging/integration. Do not assume a variant that the live catalog does not expose.

---

## 3. Responsibilities by layer

### `AGENTS.md`

Contains stable repository-wide policy:

- Source Truth;
- Rules-Core / pilot separation;
- fail-closed semantics;
- evidence semantics;
- persistence requirements;
- repository/build conventions;
- immutable-artifact rules;
- model/agent routing;
- Muse data boundary.

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

## 4. Standard start/resume algorithm for every harness

When beginning or resuming material work:

1. identify the repository and intended workstream branch;
2. verify `git status`, current branch, and exact current head;
3. read `AGENTS.md`;
4. locate/read the active Workstream Contract;
5. read `.foundry/WORKSTREAM_STATE.md` if present;
6. inspect the checkpoint commits and exact files/tests/evidence named there;
7. reverify mutable source locks needed for the next action;
8. continue from the newest genuinely verified persistent state;
9. do not redo completed work unless fresh evidence invalidates it.

If the local checkout is detached or on the wrong branch, correct that before editing.

---

## 5. Standard persistence algorithm

After each material independently validated milestone:

1. leave the tree in a coherent resumable state;
2. run the smallest authoritative scoped validation;
3. persist evidence/results needed for the claim;
4. update `.foundry/WORKSTREAM_STATE.md` if the branch uses it;
5. make a focused local commit;
6. record the exact resulting head and evidence identity;
7. continue automatically when remaining work is technically remediable and in scope.

For OpenCode/Muse, local commits are intentionally encouraged because Free-tier availability is dynamic.

For any harness, `git push` and remote publication follow current user authorization and repository policy.

---

## 6. Normal ChatGPT / Sol usage

Use normal Sol for:

- architecture;
- current rules/Oracle adjudication;
- difficult root cause;
- provider-vs-engine defect classification;
- differential interpretation;
- creation of bounded coding-agent Task Contracts;
- critical review of decision-relevant changes.

The preferred output passed to an implementation harness is a **Task Contract**, not a full chat transcript.

---

## 7. ChatGPT Work / Terra usage

When the user explicitly chooses Work for a Foundry task, Work should operate on the same persistence model:

- use the exact Git branch/worktree;
- read the same `AGENTS.md` and Workstream Contract;
- verify live repository state before acting;
- persist material milestones and evidence;
- produce the same Foundry handoff schema.

Terra High is the normal Work-side owner/integrator. Use Work capacity for source locks, difficult diagnosis, semantic/architecture-coupled edits, integration and evidence adjudication rather than long repetitive implementation/test/fix loops once the work is safely bounded for Muse.

Do not create parallel hidden architecture truth in Work-specific notes. Material conclusions must land in repository evidence/handoff form when they matter to later work.

---

## 8. OpenCode / Muse usage

OpenCode + Muse Spark 1.3 is the primary substantial bounded implementation harness while the endpoint remains suitable and available.

Default project model:

`opencode/muse-spark-1.3-contributor-free`

Operating style:

- one primary bounded objective per session;
- full access to project-relevant technical data needed by the task;
- normal project read/search/edit/shell/build/test autonomy;
- project-related external engine/provider checkouts allowed or approval-gated;
- continue through remediable failures;
- checkpoint commits after validated milestones;
- short continuation prompts after interruption;
- no need to paste `AGENTS.md` into task prompts;
- use `docs/agent-workflows/MUSE_SPARK_1_3_OPENCODE_HANDBOOK.md` for prompt-authoring guidance, not as a substitute for the active contract.

Muse may use all project-relevant technical material, including Foundry source/tests/docs/configuration, qualification contracts/fixtures/evidence/logs/artifacts, external engine/provider source, Magic card/Oracle data, decklists, owned-card inventories, collection and matchup/deckbuilding data.

The protected boundary is **unrelated personal/private user data and raw credential values**, not ordinary project information. Already-configured credentials may be consumed indirectly by project tools without printing or exposing their raw values. See `docs/agent-workflows/MUSE_DATA_BOUNDARY.md`.

Muse is not final authority for MTG semantics, Architecture Freeze, materially ambiguous provider-vs-engine blame, hidden-information/RNG authority, or decision-critical qualification PASS.

---

## 9. Model/provider switch protocol

When switching Muse -> another implementation provider, OpenCode -> Codex, Work -> OpenCode, or any other harness/provider transition:

Do not hand off a giant conversation transcript.

The receiving harness reads:

1. `AGENTS.md`;
2. active Workstream Contract;
3. `.foundry/WORKSTREAM_STATE.md` if present;
4. current Git head / checkpoint commits;
5. exact named evidence/tests.

Then it independently verifies the next-action facts and continues.

Previous-model prose is provenance only.

---

## 10. Review independence

A same-model reviewer can catch ordinary bugs but does not provide strong independent evidence for high-risk semantic claims.

For changes affecting any of the following, use the Terra/Sol authority layer before production credit:

- Magic rules semantics;
- Architecture Freeze;
- provider-vs-engine blame;
- hidden-information admission;
- RNG/concurrency architecture;
- central Rules-Core behavior;
- qualification PASS used for provider selection.

The required evidence standard does not change with the reviewing model.

---

## 11. Workstream state lifecycle

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

## 12. Minimal cross-harness continuation prompt

```text
COMMANDER SIMULATION FOUNDRY — CONTINUATION

Continue the existing workstream from durable repository state. Do not restart it.

Read AGENTS.md, the active Workstream Contract, and .foundry/WORKSTREAM_STATE.md if present. Verify git status, current branch/head, checkpoint commits, and only the mutable facts needed for the next action.

Do not redo validated work unless fresh evidence invalidates it. Continue through technically remediable in-scope failures. Persist every material verified milestone and finish with the Foundry handoff schema.

If running in Muse, use all project-relevant technical data/tools needed for the task while keeping unrelated personal/private user data and raw credential values out of model context.

Terminal objective:
[objective]
```

---

## 13. Efficiency principle

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
