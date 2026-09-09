# ChatGPT Work Execution Handbook for Commander Simulation Foundry

**Purpose:** maximize useful engineering progress per unit of ChatGPT Work/Codex capacity while preserving Foundry correctness, independent adjudication and resumability.

This handbook is operational guidance only. It does not override `AGENTS.md`, the active Workstream Contract, current Git state, immutable artifacts, current Magic authority, or the Muse data boundary.

---

## 1. Work is the authority/integration lane

Use Work when stronger repository reasoning, live source integration or decision authority is materially valuable:

- source locks and dependency reconstruction;
- architecture and subsystem boundaries;
- difficult repository diagnosis;
- current external/primary-source research;
- MTG-authority-sensitive interpretation;
- provider-vs-engine classification;
- hidden-information / RNG / concurrency reasoning;
- high-risk edits where implementation and semantics remain tightly coupled;
- integration/review of Muse implementation commits;
- critical review and evidence adjudication;
- creation of precise Muse implementation packets.

Terra High is the normal Work-side owner/integrator. Sol High is a targeted escalation for genuinely hard or high-blast-radius reasoning.

Luna is not part of the active Foundry routing policy.

Do not spend Work capacity merely because a task can be done in Work. Once semantics and acceptance criteria are bounded, prefer Muse for substantial implementation/test/fix loops.

---

## 2. Minimal startup context

At task start, load only:

1. `AGENTS.md`;
2. active Workstream Contract;
3. `.foundry/WORKSTREAM_STATE.md` if present;
4. current `git status`, branch, and head;
5. named files/tests/evidence needed for the exact next action.

Only then broaden.

Historical material is loaded only when a current claim depends on it.

---

## 3. Lazy repository exploration

Use a funnel:

```text
exact known file/test/evidence
-> targeted symbol/search
-> local callgraph/neighbors
-> subsystem
-> repository-wide search only if required
```

Every expansion should answer a specific unresolved question.

---

## 4. Separate authority work from implementation work

Work should first determine:

- what is actually broken;
- which subsystem owns the behavior;
- what the contract/authority requires;
- what must not change;
- what evidence proves completion.

If the remaining task becomes substantial bounded coding with fixed enough semantics, persist the decision and hand implementation to Muse.

Do not delegate a materially unresolved Magic/architecture decision and ask Muse to guess.

---

## 5. Validation ladder

Always start with the cheapest authoritative discriminator.

Typical order:

1. exact reproducer / one failing test;
2. regression or negative test for the repaired behavior;
3. directly related tests;
4. affected subsystem suite;
5. lint/type/build checks affected by the patch;
6. full CI/qualification at the contract-required milestone.

A smaller PASS never substitutes for a larger required gate.

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

Do not preserve giant raw logs in Work context when a file/artifact path plus exact relevant excerpt is sufficient.

---

## 7. Checkpoint before expensive exploration

Before a new uncertain or expensive phase:

- persist the last validated milestone;
- update `.foundry/WORKSTREAM_STATE.md` when used;
- record the next question/action.

This lets Muse or another Work run resume without reconstructing earlier reasoning.

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

---

## 9. When Work should continue instead of delegating

Keep the task in Work/Terra when:

- implementation and semantic reasoning remain tightly coupled;
- every repair step may alter architecture;
- the blocker is nonlocal and poorly understood;
- current external/primary-source research is required during implementation;
- final qualification judgment must be made;
- integration of independent Muse commits must be adjudicated.

Escalate to Sol High when:

- foundational/high-blast-radius architecture is involved;
- a genuine MTG semantic dispute blocks progress;
- hidden-information or RNG/concurrency reasoning is materially difficult;
- provider-vs-engine attribution remains materially ambiguous;
- Terra has made two materially distinct evidence-driven attempts on the same hard blocker.

Return to Terra after a bounded Sol ruling when practical.

---

## 10. When Work should hand to Muse

Hand off once:

- architecture is decided enough for implementation;
- exact semantics/constraints are sufficiently fixed;
- the code surface is bounded enough to name starting points;
- tests/acceptance criteria define success;
- no unresolved authority decision remains;
- the remaining work is implementation/test/repair intensive.

Muse is the primary Foundry coding worker for that phase.

Use `docs/agent-workflows/DUAL_LANE_EXECUTION_PLAYBOOK.md` for transfer rules.

---

## 11. Muse data/access rule from Work

When preparing Muse work, do not unnecessarily redact or withhold project data.

Muse may receive all project-relevant technical data required for Foundry engineering, including source/tests/docs/configuration, qualification evidence/logs/artifacts, external-engine source, card/deck/collection data and project-specific technical metadata.

Keep unrelated personal/private data and raw credential values outside Muse context. Authenticated tools may consume configured credentials without revealing raw values.

See `docs/agent-workflows/MUSE_DATA_BOUNDARY.md`.

---

## 12. Resume prompt for Work

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

If the remaining work becomes bounded substantial implementation/test iteration with semantics already fixed, produce/update the Muse handoff packet rather than consuming Work capacity unnecessarily.

Luna is not part of the active routing policy.

Terminal objective:
[objective]
```

---

## 13. Work completion rule

Before ending a Work run:

1. ensure every material completed step is persistent;
2. update workstream state;
3. identify exact next action;
4. state whether the next action belongs in Terra/Sol or Muse;
5. if Muse is next, leave an executable handoff packet;
6. never claim PASS beyond executed evidence.

The ideal Work run ends with **more verified durable state and less unresolved ambiguity**, not merely more prose.
