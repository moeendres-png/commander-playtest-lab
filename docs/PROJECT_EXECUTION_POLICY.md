# Commander Simulation Foundry — Project Execution Policy

Status: **ACTIVE / CANONICAL EXECUTION ROUTING**  
Effective: **2026-09-08**

This document controls **how project work is assigned to execution environments and models**. It does not weaken Rules correctness, evidence requirements, source authority, qualification gates, fail-closed behavior, reproducibility, or the Rules-Core/Pilot boundary.

If an older prompt, handoff, audit, report, or historical artifact prescribes a different execution environment (for example, "one Work chat only"), that routing instruction is superseded by this policy. The technical evidence and historical findings in those artifacts remain provenance and are not rewritten retroactively.

## 1. Primary operating rule

ChatGPT Work is **not** a normal execution environment for this project.

Default routing is:

1. **normal ChatGPT Sol chat, High reasoning** — coordinator, architecture, difficult analysis and adjudication;
2. **OpenCode** — primary repository implementation and execution worker;
3. **Muse** — independent technical audit, review and bounded parallel investigation;
4. **Spark 1.3** — bounded mechanical work that does not require frontier-level reasoning;
5. **ChatGPT Work with Sol Medium** — exceptional, minimal, capability-specific fallback only.

Resource constraints change execution routing only. They do not reduce qualification standards.

## 2. Normal Sol High is the primary reasoning tier

Use normal Sol High chats for:

- coordinator/integration work;
- workstream contracts and handoffs;
- architecture analysis and convergence;
- source-truth adjudication;
- difficult code review and design review;
- MTG Comprehensive Rules / Oracle interpretation;
- Rules-Core/Pilot boundary analysis;
- qualification and test design;
- failure attribution;
- evidence review and PASS/FAIL/UNKNOWN adjudication;
- deciding whether reruns are required;
- deciding whether a candidate can advance toward Architecture Freeze.

Sol High should prefer directing executable or repetitive repository work to OpenCode rather than spending scarce reasoning budget on mechanical iteration.

## 3. OpenCode is the primary implementation/execution worker

Use OpenCode for substantial repository work, including:

- code changes;
- provider/bridge implementation;
- test implementation;
- build fixes;
- CI/workflow changes;
- harness work;
- repeated test/remediation cycles;
- large source-tree inspection when execution context matters;
- local/runtime qualification;
- evidence generation that requires executable code.

Every OpenCode assignment must be bounded to one workstream and include the exact repository/branch/source lock, objective, in-scope surfaces, hard gates, forbidden shortcuts, evidence requirements, persistence requirements and stop conditions.

OpenCode does not independently grant architecture credit or global PASS.

## 4. Muse is the independent audit worker

Use Muse aggressively for independent work that does not collide with the primary implementation lane, including:

- code and evidence audits;
- no-request-echo audits;
- fallback-path census;
- Rules/Pilot separation review;
- hidden-information review;
- test-gap analysis;
- likely-failure analysis;
- post-failure diagnosis;
- review of proposed fixes;
- stale-evidence detection;
- bounded experimental work on a separate surface when explicitly assigned.

Default concurrency rule:

- **OpenCode = primary implementation**
- **Muse = independent verifier/investigator**

Do not let Muse and OpenCode concurrently edit the same implementation surface unless the coordinator explicitly partitions the work.

## 5. Spark 1.3 is the bounded mechanical worker

Use Spark 1.3 for work such as:

- inventories;
- file/path mapping;
- metadata extraction;
- machine-readable comparison;
- simple static searches;
- checklist generation;
- straightforward evidence formatting/classification;
- bounded documentation extraction.

Spark may gather and structure evidence. It must not have final authority over:

- Rules correctness;
- architecture selection;
- semantic qualification;
- native-engine defect attribution;
- contract defects;
- final PASS/FAIL adjudication;
- complex multiplayer/Commander semantics;
- hidden-information correctness;
- determinism guarantees.

Consequential conclusions return to Sol High for adjudication.

## 6. ChatGPT Work is exceptional and quota-protected

Work is forbidden for ordinary tasks that can reasonably be completed by normal Sol High, OpenCode, Muse or Spark 1.3.

Do **not** use Work for:

- ordinary research;
- GitHub reading;
- architecture reasoning;
- code review;
- MTG Rules research;
- Oracle verification;
- evidence adjudication;
- coordinator work;
- prompt creation;
- test design;
- static analysis;
- candidate-engine comparison;
- reading handoffs/reports;
- routine repository investigation;
- work OpenCode can execute;
- work Muse can audit;
- mechanical work Spark can perform.

### Work Necessity Gate

Before any Work invocation, explicitly establish:

`WORK_NECESSITY = PASS`

PASS requires all of the following:

1. a required capability is identified precisely;
2. normal Sol High cannot adequately perform the task;
3. OpenCode cannot adequately perform the required execution;
4. Muse cannot adequately perform the supporting work;
5. Spark 1.3 cannot adequately perform the bounded/mechanical portion;
6. the Work assignment is reduced to the smallest possible scope.

If any condition is missing:

`WORK_NECESSITY = FAIL`

and Work must not be used.

When Work is genuinely necessary, use **Sol Medium by default**. A stronger Work reasoning level requires a task-specific justification. Work must perform only the irreducible operation, then return the result to the normal Sol High coordinator.

## 7. Workstream decomposition

For each workstream, decompose only as needed:

- **Reasoning / authority / adjudication** → Sol High
- **Implementation / runtime execution** → OpenCode
- **Independent audit / second opinion** → Muse
- **Mechanical volume** → Spark 1.3
- **Irreplaceable capability** → Work Sol Medium after `WORK_NECESSITY = PASS`

Do not assign every role automatically. Minimize duplication.

## 8. Parallelism and collision prevention

Parallelism is allowed only when work surfaces are independent.

Before starting a second implementation worker, verify:

- branch ownership;
- current remote head;
- active worker;
- files/surfaces being changed;
- expected outputs.

If two workers would modify the same semantic implementation surface:

- do not duplicate the implementation;
- do not force-push or overwrite another worker;
- preserve the newest verified remote state;
- either repartition the work or fail closed on the collision.

A running source-valid qualification workflow should not be invalidated by speculative commits merely to "keep working".

## 9. Context-efficiency rule

Do not send the complete project history to every worker.

Each worker receives a self-contained packet containing only:

- relevant global invariants;
- exact source lock;
- exact current workstream state;
- workstream contract;
- hard gates;
- known blockers;
- required evidence;
- exact next action.

The coordinator maintains integration context. Workers maintain local workstream context.

## 10. Persistence and handoff

Material progress must remain resumable.

Every workstream starts with a WORKSTREAM CONTRACT containing:

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

Every workstream ends with a SELF-CONTAINED HANDOFF containing:

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

Persist material checkpoints during long execution rather than relying on chat continuity.

## 11. Source truth and qualification remain unchanged

Tool/model choice does not determine truth.

Software truth:

fresh verified repository/branch/commit state > README/report claims.

MTG truth:

current Comprehensive Rules / official Oracle and rulings > engine behavior > secondary sources.

Project truth order:

1. newest direct user instruction;
2. freshly verified technical state;
3. current canonical domain data;
4. current primary sources;
5. historical reports/chats/artifacts as provenance.

Qualification invariants remain:

- `UNKNOWN != PASS`
- `PARTIAL != FULL`
- `NOT_RUN != PASS`
- `CODE_DERIVED != RUNTIME_VERIFIED`
- import/parsing does not prove card functionality;
- construction does not prove behavior;
- materially changed source invalidates affected stale runtime credit until impact adjudication/rerun;
- unsupported production-reachable discretionary paths fail closed.

Forbidden fallbacks remain:

- first option;
- random option;
- default yes/no;
- hidden engine AI;
- GUI default;
- silent skip;
- parent-class fallback;
- any second hidden Rules engine in pilot/provider code.

## 12. Coordinator authority

The normal Sol High coordinator decides:

- next workstream;
- worker/model routing;
- safe parallelization;
- evidence credit;
- failure attribution;
- required reruns;
- convergence timing;
- Architecture Freeze eligibility;
- whether Work use is justified.

OpenCode, Muse, Spark and Work may produce evidence and implementation, but none independently grants global architecture credit.

## 13. Default routing algorithm

For each new task:

1. Can normal Sol High solve the reasoning/adjudication directly? → use Sol High.
2. Does the task primarily require repository implementation/execution? → use OpenCode.
3. Would independent parallel technical review materially help? → use Muse.
4. Is there substantial bounded/mechanical volume? → use Spark 1.3.
5. Is a required capability still unavailable through all paths above? → only then evaluate the Work Necessity Gate and, if PASS, use minimally scoped Work Sol Medium.

## 14. Operating principle

Spend expensive reasoning on decisions.

Spend implementation workers on implementation.

Spend cheap workers on mechanical volume.

Spend Work only on genuinely irreplaceable capability.

Never trade Rules correctness or evidence quality for quota efficiency.
