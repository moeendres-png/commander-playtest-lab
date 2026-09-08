# ChatGPT Work Execution Handbook for Commander Simulation Foundry

**Purpose:** maximize useful engineering progress per unit of ChatGPT Work/Codex capacity while preserving Foundry correctness and resumability.

This handbook is operational guidance only. It does not override `AGENTS.md`, the active Workstream Contract, current Git state, immutable artifacts, or current Magic authority.

---

## 1. Work is the high-capability lane

Use Work for tasks where stronger execution/reasoning is worth the capacity cost:

- architecture and subsystem boundaries;
- difficult repository diagnosis;
- high-risk multi-file changes;
- browser/repository/application workflows;
- MTG-authority-sensitive implementation planning;
- provider-vs-engine classification;
- hidden-information / RNG / concurrency work;
- critical review and evidence adjudication;
- creation of a precise Muse implementation packet.

Do not spend Work capacity merely because a task can be done in Work.

---

## 2. Minimal startup context

At task start, load only:

1. `AGENTS.md`;
2. active Workstream Contract;
3. `.foundry/WORKSTREAM_STATE.md` if present;
4. current `git status`, branch, and head;
5. named files/tests needed for the exact next action.

Only then broaden.

Avoid loading:

- every historical handoff;
- all prior workstream reports;
- all qualification artifacts;
- entire directories without a concrete question;
- old chat transcripts.

Historical material is loaded only when a current claim depends on it.

---

## 3. Lazy repository exploration

Use a funnel:

```text
exact known file/test
-> targeted symbol/search
-> local callgraph/neighbors
-> subsystem
-> repository-wide search only if required
```

Every expansion should answer a specific unresolved question.

Do not repeatedly rescan unchanged areas after a checkpoint.

---

## 4. Separate reasoning work from mechanical work

Work should first determine:

- what is actually broken;
- which subsystem owns the behavior;
- what the contract requires;
- what must not change;
- what evidence proves completion.

Once that is stable, if the remaining work is implementation-heavy and bounded, persist the decision and hand it to Muse rather than spending Work capacity on repetitive loops.

---

## 5. Validation ladder

Always start with the cheapest authoritative discriminator.

Typical order:

1. exact reproducer / one failing test;
2. regression test for the repaired behavior;
3. directly related tests;
4. affected subsystem suite;
5. lint/type/build checks affected by the patch;
6. full CI or qualification only at the contract-required milestone.

Do not confuse `smallest authoritative first` with `smallest test is sufficient`.

---

## 6. Evidence compression

Prefer durable compact evidence:

- JSON result summaries;
- checksums/digests;
- exact run IDs;
- commit SHAs;
- short failure classifications;
- exact command + exit/result;
- focused diff summaries.

Do not preserve giant raw logs in the prompt when a file/artifact path plus exact failure excerpt is sufficient.

---

## 7. Checkpoint before expensive exploration

Before beginning a new uncertain or expensive phase:

- commit the last validated milestone;
- update `.foundry/WORKSTREAM_STATE.md`;
- record the next question/action.

If Work capacity stops during the next phase, Muse or another Work run can resume from that point without reconstructing earlier reasoning.

---

## 8. Work task shape

A good Work task has:

- one terminal objective;
- exact source lock or instruction to verify it live;
- explicit authority;
- bounded scope;
- named starting points;
- hard invariants;
- executable validation;
- persistence requirements;
- stop conditions.

Do not give Work a generic mission such as `finish the simulator` unless the workstream itself is an integration/coordinator workstream with explicit dependency state.

---

## 9. When Work should continue instead of delegating

Keep the task in Work when:

- implementation and semantic reasoning are tightly coupled;
- every repair step may alter architecture;
- the blocker is nonlocal and poorly understood;
- current external/primary-source research is required during implementation;
- final qualification judgment must be made;
- the change is too high-risk to hand to a weaker worker without first reducing uncertainty.

---

## 10. When Work should hand to Muse

Hand off once:

- architecture is decided;
- exact semantics are fixed;
- the code surface is bounded enough to name starting points;
- tests/acceptance criteria define success;
- no unresolved authority decision remains;
- the remaining work is mostly implementation/test/repair iteration.

Use `docs/agent-workflows/DUAL_LANE_EXECUTION_PLAYBOOK.md` for the exact transfer packet.

---

## 11. Resume prompt for Work

```text
COMMANDER SIMULATION FOUNDRY — WORK CONTINUATION

Continue the existing workstream from durable repository state. Do not restart it.

Read only:
1. AGENTS.md
2. active Workstream Contract
3. .foundry/WORKSTREAM_STATE.md if present
4. current branch/head/status
5. exact files/tests/evidence named for the next action

Reverify only mutable facts required for that action.
Do not redo validated work unless fresh evidence invalidates it.
Use the smallest authoritative validation first.
Persist every material verified milestone.

If the remaining work becomes bounded implementation/test iteration with semantics already fixed, produce/update the Muse handoff packet rather than consuming high-capability capacity unnecessarily.

Terminal objective:
[objective]
```

---

## 12. Work completion rule

Before ending a Work run:

1. ensure every material completed step is persistent;
2. update workstream state;
3. identify exact next action;
4. state whether the next action belongs in Work or Muse;
5. if Muse is next, leave an executable handoff packet;
6. never claim PASS beyond the executed evidence.

The ideal Work run ends with **more verified durable state and less unresolved ambiguity**, not merely more prose.
