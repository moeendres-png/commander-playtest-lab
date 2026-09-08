# Muse Spark 1.3 + OpenCode Handbook for Commander Simulation Foundry

**Status:** living operational handbook  
**Research lock:** 2026-09-08  
**Scope:** prompt design, session design, persistence, quota-aware execution, and handoff practices for using Muse Spark 1.3 Contributor Free through OpenCode on `commander-playtest-lab`.

This handbook is model/harness guidance. It does **not** override `AGENTS.md`, an active Workstream Contract, current Magic authority, fresh repository Source Truth, or the binding data boundary in `docs/agent-workflows/MUSE_DATA_BOUNDARY.md`.

---

## 1. Executive operating rule

Use Muse Spark 1.3 as the Foundry's primary bounded implementation worker, not as the final authority for Magic rules, Architecture Freeze, or decision-critical qualification credit.

Preferred division of labor:

```text
normal ChatGPT / Sol authority-review layer
    -> bounded Task Contract
    -> ChatGPT Work / Terra integration where needed
    -> OpenCode + Muse Spark 1.3 Contributor Free
    -> implementation / tests / local evidence / checkpoint commits
    -> Terra/Sol review for decision-critical changes
```

For ordinary implementation, allow Muse to work through the complete bounded task rather than artificially limiting it to a few turns. Preserve progress frequently so an upstream rate limit or interrupted session is cheap to recover from.

Global Foundry invariants already live in `AGENTS.md`. Do not paste those instructions into every Muse prompt. Task prompts should add only the information that is specific to the current objective.

### Project-data rule

Muse may use all project-relevant technical data needed for Foundry work, including repository source/tests/docs/configuration, qualification artifacts/evidence/logs, external engine/provider source, Magic card data, decklists, owned-card inventories, and other MTG collection/deck information.

The protected boundary is unrelated personal/private information about the user plus raw credential values. Credentials may be consumed indirectly by already configured project tooling, but should not be printed, copied, persisted, or exposed as raw values. See `docs/agent-workflows/MUSE_DATA_BOUNDARY.md` for the binding details.

---

## 2. What is verified about Muse Spark 1.3

### 2.1 Meta's current claims

Meta's 2026-09-02 Muse Spark 1.3 announcement says the model was trained for longer-horizon agentic and coding work. The release specifically describes improved ability to:

- sustain long work across messy or conflicting sources;
- use tools to build its own working context;
- correct gaps in its plan;
- preserve detailed constraints across multi-step work;
- handle interruptions and steering inside long threads;
- ask for clarification or user help when materially stuck;
- perform long-horizon coding with fewer unnecessary turns and cleaner output.

Meta reports approximately **20% fewer tool calls** and **25% fewer tokens** than Muse Spark 1.2 in its internal coding comparisons. Treat those numbers as vendor-reported comparative results, not a Foundry benchmark.

Primary source:

- https://research.meta.ai/blog/introducing-muse-spark-1-3

### 2.2 OpenCode is a good fit for persistent project instructions

OpenCode treats discovered `AGENTS.md` files as project instructions throughout a session. It can also discover nested `AGENTS.md` files as relevant areas are read.

For Foundry this means:

- stable project invariants belong in `AGENTS.md`;
- workstream-specific facts belong in the Workstream Contract and workstream state;
- a prompt should not re-transmit stable repo policy unless a task requires a deliberate exception.

OpenCode also performs automatic context compaction. This makes long sessions practical, but compaction is lossy; branch-persisted workstream state remains the stronger recovery mechanism.

---

## 3. What is actually known about the free limit

### 3.1 Official Free-tier statement

As of the research lock, OpenCode Zen lists:

`Muse Spark 1.3 Contributor Free` / `muse-spark-1.3-contributor-free`

as a **limited-time free model**. OpenCode does **not** publish a fixed request, token, daily, weekly, or five-hour quota for this free SKU on the Zen page.

The Contributor Free endpoint has data-use terms that make it unsuitable as a confidential personal-data endpoint. Foundry therefore keeps unrelated personal/private data and raw credential values outside Muse context while allowing all project-relevant technical data needed for engineering.

Primary source:

- https://opencode.ai/docs/zen

### 3.2 Do not confuse OpenCode Go limits with the Free SKU

OpenCode publishes estimated limits for its paid **Go** plan. For `Muse Spark 1.3 Contributor`, its current table estimates approximately:

- 45,300 typical requests per 5 hours;
- 113,300 per week;
- 226,600 per month.

Those numbers are useful evidence that Muse Contributor is inexpensive relative to many other models, but they are **not the quota for `muse-spark-1.3-contributor-free`**.

Primary source:

- https://dev.opencode.ai/docs/go/

### 3.3 Community reports are highly variable

Recent OpenCode community reports are inconsistent. Treat them as anecdotes, not a published contract.

### 3.4 Foundry policy derived from the uncertain limit

Do **not** optimize prompts around an invented numeric Free quota.

Instead:

1. use Muse freely for bounded implementation while the endpoint is available;
2. avoid wasteful full-repository rereads and repeated restatement of `AGENTS.md`;
3. persist every material milestone;
4. allow long autonomous repair loops when the task remains in scope;
5. when rate-limited, resume from the last branch checkpoint rather than replaying the session;
6. keep a provider-neutral handoff so another model can take over without reconstruction.

---

## 4. Prompting principles for Muse Spark 1.3

### 4.1 Give one terminal objective

Good:

> Implement the exact provider-native state restoration required for fixture X, add regression tests, run the scoped qualification, persist evidence, and continue through remediable failures until the acceptance criteria pass or a terminal blocker is proven.

Bad:

> Improve XMage and make the simulator better.

Muse is trained for long-horizon work. That does not mean the objective should be vague. Give it a **large enough coherent task**, not an unbounded project mission.

### 4.2 Separate facts from goals

Use explicit sections:

- `OBJECTIVE`
- `SOURCE LOCK`
- `AUTHORITY`
- `KNOWN FACTS`
- `IN SCOPE`
- `OUT OF SCOPE`
- `START HERE`
- `REQUIRED DELIVERABLES`
- `VALIDATION`
- `PERSISTENCE`
- `STOP CONDITIONS`

### 4.3 Point to files instead of pasting them

Prefer repository paths and exact source identities. Re-reading the exact file is safer than relying on a copied stale excerpt.

### 4.4 Use lazy context loading

Start from the named files and current evidence. Broaden repository search only to answer a specific unresolved question.

### 4.5 Do not duplicate `AGENTS.md`

The repository already contains stable policy.

### 4.6 Tell it what to do after a failure

A failing intermediate test is not a stop condition if the failure is technically remediable within scope. Diagnose, repair, rerun, and persist each verified milestone.

### 4.7 Make ambiguity resolution hierarchical

First try to resolve ambiguity from the current Workstream Contract, fresh repository state, tests, evidence, and named authority. Return only materially unresolved semantic/architecture choices to Terra/Sol.

### 4.8 Define evidence, not merely code output

Good acceptance criteria include exact tests, negative fail-closed proofs, source/build identity, evidence JSON, and final-diff inspection.

### 4.9 Ask for checkpoint commits, not one giant final commit

After each material independently validated milestone, update workstream state and make a focused local commit. Do not leave hours of validated work only in ephemeral session context.

### 4.10 Keep the final report structured

Require the Foundry handoff schema:

- Source Lock
- Work Completed
- New Findings
- Changes
- Tests / Evidence
- PASS / FAIL / UNKNOWN
- Remaining Blockers
- Outputs
- Dependencies Unblocked
- Exact Next Action

---

## 5. Recommended session size

### Use one session when

- there is one primary workstream objective;
- the model is still operating on the same branch and semantic contract;
- tool history remains relevant;
- continuation benefits from recent failures/results.

### Start a fresh session when

- the primary objective changes;
- a major contract version changes;
- a different workstream begins;
- an old session has accumulated conflicting stale assumptions;
- `AGENTS.md` or nested instructions changed materially and you need a clean instruction epoch;
- you are switching from implementation to an independent review and want reduced anchoring.

Do not create a fresh session merely because a test failed.

---

## 6. Persistent state protocol

For substantial branches, maintain a branch-local `.foundry/WORKSTREAM_STATE.md` based on the repository template when the workstream uses it.

It is a **resume pointer, not Source Authority**.

Update it after material milestones with:

- current branch/head;
- active objective;
- immutable input/contract IDs;
- completed milestones;
- files changed;
- last authoritative passing tests;
- currently failing command and exact failure classification;
- unresolved blocker;
- next exact action.

At resume time:

1. read `AGENTS.md`;
2. read the active Workstream Contract;
3. read `.foundry/WORKSTREAM_STATE.md` if present;
4. verify mutable source locks that matter to the next action;
5. inspect `git status` and recent commits;
6. continue from the newest genuinely verified checkpoint.

Never treat a stale state file as stronger than current Git state.

---

## 7. OpenCode configuration strategy

The project configuration should favor productive use of Muse without sacrificing the narrow personal-data/raw-credential boundary.

### Implementer

- default model: `opencode/muse-spark-1.3-contributor-free`;
- no small artificial `steps` limit;
- normal project read/search/edit/shell/build/test autonomy;
- project-related external engine/source trees allowed or approval-gated;
- local commits allowed for resumability;
- `git push`, destructive Git operations, and destructive filesystem operations require approval;
- direct reads/edits of common raw credential files are denied;
- environment/credential dumping is denied;
- authenticated tooling may consume already configured credentials without exposing raw values;
- automatic compaction enabled.

### Reviewer

Use a separate read-only agent/session. A Muse-on-Muse review is useful for catching ordinary mistakes but is **not independent model-family evidence** and must not be treated as final Rules/Architecture authority.

---

## 8. Standard Muse implementation prompt

```text
COMMANDER SIMULATION FOUNDRY

Obey the repository AGENTS.md and the binding Muse data boundary. This prompt adds only task-specific instructions.

OBJECTIVE
[one terminal engineering result]

SOURCE LOCK
Repository: moeendres-png/commander-playtest-lab
Branch: [branch]
Required starting head: [commit or VERIFY_LIVE]
Immutable contract/input: [artifact/version/digest]
Engine pin if relevant: [repo@commit]

AUTHORITY
[exact contract / CR / Oracle / source authority]

KNOWN FACTS
- [...]

IN SCOPE
- [...]

OUT OF SCOPE
- [...]

START HERE
Read these first:
- [file/class]
- [file/test]
- [.foundry/WORKSTREAM_STATE.md if present]
Broaden search only when evidence requires it.

PROJECT DATA / PRIVACY
Use all project-relevant technical data and normal engineering tools needed for the task. Do not expose unrelated personal/private user data or raw credential values. Authenticated tooling may consume configured credentials without printing them.

REQUIRED WORK
1. [...]
2. [...]
3. [...]

VALIDATION
Run the smallest authoritative checks first, then broaden only as needed:
[commands]

PERSISTENCE
Treat the run as interruptible. After each material validated milestone:
- update .foundry/WORKSTREAM_STATE.md when used;
- make a focused local commit;
- record exact test/evidence identity.
Do not push/merge without authorization.

EXECUTION RULE
Continue automatically through technically remediable in-scope failures. First resolve ambiguity from the contract, repository, tests, evidence and authority. Return only unresolved semantic/architecture authority questions to Terra/Sol.

ACCEPTANCE CRITERIA
- [...]

STOP CONDITIONS
Only a proven terminal blocker, immutable out-of-scope contract change, unavailable required authority/tooling, forbidden architecture change, or unresolved semantic/architecture choice the Muse lane is not authorized to decide.

FINAL HANDOFF
Source Lock
Work Completed
New Findings
Changes
Tests / Evidence
PASS / FAIL / UNKNOWN
Remaining Blockers
Outputs
Dependencies Unblocked
Exact Next Action
```

---

## 9. Continuation prompt after interruption or rate limit

```text
COMMANDER SIMULATION FOUNDRY — CONTINUATION

Continue the existing workstream; do not restart it.

1. Read AGENTS.md.
2. Read the active Workstream Contract.
3. Read .foundry/WORKSTREAM_STATE.md if present.
4. Verify git status, current branch/head, and newest relevant checkpoint commits.
5. Reverify only mutable facts required for the next action.
6. Continue from the newest genuinely verified persistent state.

Do not redo completed work unless fresh evidence invalidates it.
Do not stop at a technically remediable in-scope failure.
Persist every new material milestone.
Use all project-relevant technical data/tools needed for the task while keeping unrelated personal/private user data and raw credential values out of Muse context.

Terminal objective:
[objective]
```

---

## 10. Provider/harness switch

Handoffs should remain provider-neutral. Pass the Workstream Contract, exact branch/commits, workstream state, exact evidence/tests, and next action rather than the entire prior session.

---

## 11. Bounded bug / implementation guidance

For a known failing test or bounded bug:

1. reproduce first;
2. trace the production-reachable call/data path;
3. identify the subsystem that owns the behavior;
4. implement the minimum technically correct fix;
5. add a regression/negative test when required;
6. run the validation ladder;
7. inspect the final diff;
8. persist the checkpoint;
9. continue automatically if another in-scope remediable failure appears.

Do not move Magic legality into a pilot/harness merely because doing so is easier.

---

## 12. Final principle

Muse should be constrained by **project semantics, Source Truth, evidence requirements, branch ownership, and the personal-data/raw-credential boundary** — not by artificial restrictions on ordinary Foundry project data or normal engineering tools.
