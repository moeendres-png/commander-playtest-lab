# Muse Spark 1.3 + OpenCode Handbook for Commander Simulation Foundry

**Status:** living operational handbook  
**Research lock:** 2026-09-08  
**Scope:** prompt design, session design, persistence, quota-aware execution, and handoff practices for using Muse Spark 1.3 Contributor Free through OpenCode on `commander-playtest-lab`.

This handbook is model/harness guidance. It does **not** override `AGENTS.md`, an active Workstream Contract, current Magic authority, or fresh repository Source Truth.

---

## 1. Executive operating rule

Use Muse Spark 1.3 as a high-capacity implementation worker, not as the final authority for Magic rules or qualification credit.

Preferred division of labor:

```text
normal ChatGPT / high-capability planning-review layer
    -> bounded Task Contract
    -> OpenCode + Muse Spark 1.3 Contributor Free
    -> implementation / tests / local evidence / checkpoint commits
    -> high-capability review for decision-critical changes
```

For ordinary implementation, allow Muse to work through the complete bounded task rather than artificially limiting it to a few turns. Preserve progress frequently so an upstream rate limit or interrupted session is cheap to recover from.

Global Foundry invariants already live in `AGENTS.md`. Do not paste those 400+ lines into every Muse prompt. Task prompts should add only the information that is specific to the current objective.

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

OpenCode V2 treats discovered `AGENTS.md` files as privileged instructions throughout a session. It can also discover nested `AGENTS.md` files as relevant areas are read.

For Foundry this means:

- stable project invariants belong in `AGENTS.md`;
- workstream-specific facts belong in the Workstream Contract and workstream state;
- a prompt should not re-transmit stable repo policy unless a task requires a deliberate exception.

OpenCode V2 also performs automatic context compaction. Its compaction checkpoint records objective, requirements, decisions, completed/active work, blockers, next moves, relevant files, and recent context. This makes long sessions practical, but compaction is lossy; branch-persisted workstream state remains the stronger recovery mechanism.

Primary sources:

- https://opencode.ai/v2/docs/instructions
- https://opencode.ai/v2/docs/compaction

---

## 3. What is actually known about the free limit

### 3.1 Official Free-tier statement

As of the research lock, OpenCode Zen lists:

`Muse Spark 1.3 Contributor Free` / `muse-spark-1.3-contributor-free`

as a **limited-time free model**. OpenCode does **not** publish a fixed request, token, daily, weekly, or five-hour quota for this free SKU on the Zen page.

OpenCode also states that the Contributor Free endpoint is discounted/free in exchange for permission to use prompts and completions to train future Meta models. Do not send secrets, credentials, private user data, or confidential material to this endpoint.

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

Recent OpenCode community reports are inconsistent:

- some users report normal repo work without hitting a limit;
- one user reports more than 100M tokens over multiple sessions;
- another reports hitting a five-hour limit after roughly 400k-500k tokens;
- other users report rate limits after long multi-hour agent runs;
- users speculate that cache hit rate and upstream load affect practical usage.

These are anecdotes, not a published contract. They demonstrate that the free quota is generous for some users but should be treated as **dynamic and non-guaranteed**.

Examples reviewed on 2026-09-08:

- https://www.reddit.com/r/opencode/comments/1w5ziqj/meta_muse_spark_13_is_free_on_opencode_zen/
- https://www.reddit.com/r/opencode/comments/1w91y83/meta_spark_13_for_free_is_surprisingly_great_but/
- https://www.reddit.com/r/opencode/comments/1w0000t/whats_the_usage_limits_like_on_opencode_zen_free/

### 3.4 Foundry policy derived from the uncertain limit

Do **not** optimize prompts around an invented numeric Free quota.

Instead:

1. use Muse freely for bounded implementation while the endpoint is available;
2. avoid wasteful full-repository rereads and repeated restatement of `AGENTS.md`;
3. persist every material milestone;
4. allow long autonomous repair loops when the task remains in scope;
5. when rate-limited, resume from the last branch checkpoint rather than replaying the session;
6. keep a provider-neutral handoff so DeepSeek or another model can take over without reconstruction.

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

This structure helps the model preserve constraints during long tool loops.

### 4.3 Point to files instead of pasting them

Prefer:

> Read `candidate-qualification/.../WORKSTREAM_CONTRACT.md`, then inspect `XmageFoo.java` and `XmageFooTest.java`.

Do not paste large repository files into the chat unless the model cannot access them.

The repository is the source of implementation truth. Re-reading the exact file is safer than relying on a copied stale excerpt.

### 4.4 Use lazy context loading

Tell Muse where to start and when broader search is justified:

> Start from the named files and current workstream evidence. Broaden repository search only if a named source is absent, stale, or contradicted by fresh code.

This saves tokens while still allowing the model to investigate when needed.

### 4.5 Do not duplicate `AGENTS.md`

The prompt should say, at most:

> Obey the repository `AGENTS.md`; the task-specific rules below add to it.

Repeating the whole policy wastes input and creates conflict risk when the file changes.

### 4.6 Tell it what to do after a failure

For Foundry, explicitly state:

> A failing intermediate test is not a stop condition if the failure is technically remediable within scope. Diagnose, repair, rerun, and persist each verified milestone. Stop only on a proved terminal blocker.

This is preferable to prompting one edit at a time.

### 4.7 Make ambiguity resolution hierarchical

Muse 1.3 is trained to ask clarifying questions. For autonomous repo work, narrow that behavior:

> First try to resolve ambiguity from the current Workstream Contract, fresh repository state, tests, and named authority. Ask the user only when a material choice remains genuinely unresolved and choosing incorrectly would change semantics or scope.

This avoids unnecessary interruptions without encouraging guessing.

### 4.8 Define evidence, not merely code output

Bad acceptance criterion:

> Code looks correct.

Good acceptance criteria:

- exact scoped test passes;
- negative test proves fail-closed behavior;
- no fallback was introduced;
- requested and constructed state digests match where required;
- evidence JSON names the exact source/build identity;
- final diff contains no unrelated semantic changes.

Muse performs better when the finish line is executable.

### 4.9 Ask for checkpoint commits, not one giant final commit

For long work:

> After each material independently validated milestone, update workstream state and make a focused local commit. Do not push without authorization.

This is the main protection against rate-limit loss.

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

This also makes a provider/model switch cheap.

---

## 5. Recommended session size

### Use one session when

- there is one primary workstream objective;
- the model is still operating on the same branch and semantic contract;
- tool history remains relevant;
- continuation benefits from recent failures/results.

Muse 1.3 is specifically improved for this type of long thread.

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

For substantial branches, maintain a branch-local `.foundry/WORKSTREAM_STATE.md` based on the repository template.

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

The project configuration should favor productive use of the free Muse capacity without sacrificing repository safety.

### Implementer

- default model: `opencode/muse-spark-1.3-contributor-free`;
- no small artificial `steps` limit;
- edits and ordinary local shell/test commands allowed;
- local commits allowed for resumability;
- `git push`, destructive Git operations, and destructive filesystem operations require approval;
- secrets/environment files denied;
- automatic compaction enabled with a larger retained recent-context tail than the OpenCode default.

### Reviewer

Use a separate read-only agent/session. A Muse-on-Muse review is useful for catching ordinary mistakes but is **not independent model-family evidence** and must not be treated as final Rules/Architecture authority.

### Current OpenCode V2 caveat

As of 2026-09-08, OpenCode V2 documentation states that the `instructions` array is parsed but its file/URL entries are not yet resolved into active model instructions. Therefore this repository relies on `AGENTS.md` discovery rather than an `instructions` entry in `opencode.json`.

Recheck this caveat when OpenCode V2 changes.

---

## 8. Standard Muse implementation prompt

Use this as the default prompt body after normal high-capability planning has produced a bounded task.

```text
COMMANDER SIMULATION FOUNDRY

Obey the repository AGENTS.md. This prompt adds only task-specific instructions.

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
- [...]

IN SCOPE
- [...]

OUT OF SCOPE
- [...]

START HERE
Read these first in one batch where practical:
- [file/class]
- [file/test]
- [.foundry/WORKSTREAM_STATE.md if present]
Broaden search only when the named sources are absent or contradicted.

REQUIRED WORK
1. [...]
2. [...]
3. [...]

VALIDATION
Run the smallest authoritative checks first, then broaden only as needed:
[commands]

PERSISTENCE
Treat the run as interruptible. After each material validated milestone:
- update .foundry/WORKSTREAM_STATE.md when this branch uses it;
- make a focused local commit;
- record exact test/evidence identity.
Do not push without authorization.

EXECUTION RULE
Continue automatically through technically remediable in-scope failures. First resolve ambiguity from the contract, repository and tests. Ask only when a material semantic/scope choice genuinely cannot be resolved from authority.

ACCEPTANCE CRITERIA
- [...]
- [...]

STOP CONDITIONS
Only a proven terminal blocker, immutable out-of-scope contract change, unavailable required authority/tooling, or forbidden architecture change.

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

Do not reconstruct the entire project in prose. Use:

```text
COMMANDER SIMULATION FOUNDRY — CONTINUATION

Continue the existing workstream; do not restart it.

1. Read AGENTS.md.
2. Read the active Workstream Contract.
3. Read .foundry/WORKSTREAM_STATE.md if present.
4. Verify git status, current branch/head, and the newest relevant checkpoint commits.
5. Reverify only mutable facts required for the next action.
6. Continue from the newest genuinely verified persistent state.

Do not redo completed work unless fresh evidence invalidates it.
Do not stop at a technically remediable in-scope failure.
Persist every new material milestone.

Terminal objective:
[objective]
```

This prompt is intentionally small because the repository contains the state.

---

## 10. Prompt when switching Muse -> DeepSeek

The handoff should be provider-neutral:

```text
COMMANDER SIMULATION FOUNDRY — PROVIDER/HARNESS CONTINUATION

You are taking over an existing repository workstream from another coding model.
Do not trust the previous model's prose as Source Authority and do not restart the work.

Read, in order:
1. AGENTS.md
2. active Workstream Contract
3. .foundry/WORKSTREAM_STATE.md if present
4. git status / current branch / recent checkpoint commits
5. exact files and tests named by the state file

Verify the newest persistent facts and continue from the exact next action.
Do not redo validated milestones unless later evidence invalidates them.
Do not reinterpret qualification PASS/FAIL labels without required evidence.

Terminal objective:
[objective]
```

No Muse-specific assumptions should appear in the actual workstream state.

---

## 11. Prompt for a bounded bug with known failing test

```text
Obey AGENTS.md.

OBJECTIVE
Fix [bug] without changing [semantic contract].

REPRODUCTION
[exact failing command/test]

EXPECTED BOUNDARY
[what subsystem owns legality/behavior]

START HERE
[file list]

REQUIRED METHOD
- reproduce first;
- trace the production-reachable call/data path;
- implement the minimum sound repair;
- add/strengthen a regression test that fails on the original bug;
- run neighboring authoritative tests;
- inspect the final diff for fallback or semantic leakage;
- checkpoint commit after validated repair.

Do not weaken the test or move Rules logic into the pilot/harness.
Continue through remediable failures until complete or terminally blocked.
```

---

## 12. Prompt for read-only review

```text
Review the current branch/diff against AGENTS.md and the active Task/Workstream Contract.
Do not edit files.

Check in this order:
1. exact source identity;
2. contract compliance;
3. Rules-Core / pilot separation;
4. hidden-information leakage;
5. unsupported/fallback paths;
6. RNG/replay authority where relevant;
7. multiplayer/Commander semantics where relevant;
8. tests proving behavior rather than parsing/construction only;
9. evidence supporting every claimed PASS;
10. unrelated changes or weakened assertions.

Return findings by severity with file/line references, then PASS / FAIL / PARTIAL / UNKNOWN.
```

---

## 13. Anti-patterns

Avoid these with Muse:

### Giant history dump

Do not paste every prior workstream. Use the current contract, state file, and exact handoff.

### Vague autonomy

`Work on this repo until it is better` wastes the free quota and increases regression risk.

### Excessive micromanagement

Do not require permission after every file edit or test if the branch and scope are already safe. Muse 1.3 is designed for longer tool-driven work.

### Premature stop prompts

`Try once and report` is wrong for ordinary Foundry remediation. Require continued repair through remediable failures.

### Model as authority

Muse output never outranks fresh Git state, current CR/Oracle, immutable contracts, or runtime evidence.

### Free quota as reliability guarantee

The endpoint can rate-limit or disappear. Persist work continuously.

### Independent review illusion

Muse reviewing its own Muse-generated patch can catch mistakes but is not strong independent evidence for architecture or Rules correctness.

---

## 14. When to use Muse aggressively

Good candidates while the free endpoint is available:

- bounded multi-file implementation with explicit acceptance tests;
- provider adapters after architecture is decided;
- state-loader extensions with exact mappings;
- qualification harness plumbing;
- test-suite expansion;
- evidence serialization;
- repetitive but nontrivial refactors;
- compilation/test/fix loops;
- documentation tied directly to verified code;
- repository exploration when the question is technical rather than authoritative MTG adjudication.

Use high-capability review before relying on Muse alone for:

- architecture freeze;
- MTG rules adjudication;
- final provider-vs-engine blame;
- hidden-information security admission;
- concurrency/RNG architecture changes;
- central Rules-Core patches with high blast radius;
- qualification PASS that affects production-provider selection.

---

## 15. Rate-limit recovery procedure

When the provider returns a rate-limit error:

1. do not undo the working tree;
2. inspect whether the last material milestone was committed;
3. if uncommitted but coherent and tested, commit it manually or with another trusted tool/model;
4. ensure `.foundry/WORKSTREAM_STATE.md` names the exact active failure/next action;
5. later resume Muse with the short continuation prompt, or switch to DeepSeek using the provider-neutral continuation prompt;
6. re-run the smallest authoritative validation before granting new credit.

The recovery unit is the Git checkpoint, not the conversation transcript.

---

## 16. Periodic re-research triggers

Recheck this handbook when any of the following changes:

- Muse Spark model version;
- OpenCode Zen Free model availability;
- OpenCode publishes a formal Free quota;
- OpenCode V2 changes `AGENTS.md`, compaction, agent, or instruction semantics;
- Contributor Free data-use terms change;
- the project switches its default coding provider;
- empirical Foundry runs show a recurring Muse failure pattern.

When updating, distinguish:

- `OFFICIAL_VERIFIED`;
- `COMMUNITY_ANECDOTE`;
- `FOUNDRY_DERIVED_POLICY`.

Never silently turn an anecdotal quota number into a contractual limit.

---

## 17. Source index

### Official / primary

- Meta, *Introducing Muse Spark 1.3* (2026-09-02): https://research.meta.ai/blog/introducing-muse-spark-1-3
- OpenCode Zen model catalog and Contributor terms: https://opencode.ai/docs/zen
- OpenCode V2 Instructions: https://opencode.ai/v2/docs/instructions
- OpenCode V2 Compaction: https://opencode.ai/v2/docs/compaction
- OpenCode V2 Agents: https://opencode.ai/v2/docs/agents
- OpenCode V2 Permissions: https://opencode.ai/v2/docs/permissions
- OpenCode V2 Config: https://opencode.ai/v2/docs/config
- OpenCode Go published usage estimates: https://dev.opencode.ai/docs/go/

### Community evidence used only for practical quota uncertainty

- https://www.reddit.com/r/opencode/comments/1w5ziqj/meta_muse_spark_13_is_free_on_opencode_zen/
- https://www.reddit.com/r/opencode/comments/1w91y83/meta_spark_13_for_free_is_surprisingly_great_but/
- https://www.reddit.com/r/opencode/comments/1w0000t/whats_the_usage_limits_like_on_opencode_zen_free/
- https://www.reddit.com/r/opencodeCLI/comments/1w6zgqp/love_the_new_muse_spark_model_but_got_rate/

**Research conclusion:** Muse Spark 1.3 Contributor Free is worth using generously while available, but there is no official fixed Free quota to optimize against. Design the workflow for long useful runs and cheap interruption recovery rather than for a guessed token ceiling.
