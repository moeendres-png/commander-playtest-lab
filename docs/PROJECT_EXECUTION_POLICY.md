# Commander Simulation Foundry - Project Execution Policy

Status: ACTIVE / CANONICAL EXECUTION ROUTING
Effective: 2026-09-08

This policy controls how project work is executed. It does not weaken Rules correctness, evidence quality, qualification standards, fail-closed behavior, reproducibility, Source Truth, or the Rules-Core/Pilot boundary.

Older prompts or handoffs that prescribe another execution environment remain historical provenance only. Their technical evidence is not rewritten, but their execution-routing instructions are superseded here.

## 1. Available execution paths

There are exactly three project execution paths:

1. normal ChatGPT with GPT-5.6 Sol High
2. OpenCode with Muse Spark 1.3
3. ChatGPT Work with GPT-5.6 Sol Medium, exceptional only

Muse and Spark 1.3 are not separate workers or execution paths in this project. The only OpenCode resource is OpenCode with Muse Spark 1.3.

## 2. Primary operating rule

Default execution uses normal Sol High and OpenCode with Muse Spark 1.3.

ChatGPT Work is not a normal project environment. It may be used only when a required capability cannot reasonably be completed through normal Sol High or OpenCode with Muse Spark 1.3.

## 3. Normal Sol High

Use normal Sol High for:

- Coordinator and Integration
- workstream design and handoffs
- architecture and convergence
- Source Truth adjudication
- GitHub and source research
- difficult code review
- MTG Comprehensive Rules, Oracle and rulings work
- Rules-Core/Pilot boundary analysis
- qualification and test design
- failure attribution
- evidence review
- PASS, FAIL and UNKNOWN adjudication
- rerun decisions
- Architecture Freeze and production-provider decisions

Normal Sol High is the final project-level adjudicator.

## 4. OpenCode with Muse Spark 1.3

Use OpenCode with Muse Spark 1.3 for substantial repository execution, including:

- implementation
- repository edits
- provider and bridge work
- harness work
- tests
- build fixes
- CI and workflow changes
- debugging
- runtime qualification
- repeated remediation cycles
- large source-tree inspection
- static and dynamic audits
- evidence generation
- inventories, metadata extraction and other bounded mechanical repository work

Every substantial OpenCode assignment must be bounded to one primary workstream and include repository, branch, source lock, current head, objective, in-scope surface, hard gates, forbidden shortcuts, evidence requirements, persistence requirements and stop conditions.

OpenCode with Muse Spark 1.3 may produce implementation and evidence but does not independently grant global architecture credit.

## 5. Work budget and necessity gate

Work is forbidden for ordinary tasks that normal Sol High or OpenCode with Muse Spark 1.3 can perform.

Do not use Work for ordinary research, GitHub reading, repository investigation, architecture, code review, MTG Rules or Oracle work, evidence adjudication, coordination, prompt creation, test design, static analysis, candidate comparison, report reading, implementation, CI, debugging, runtime qualification or mechanical repository work when the normal paths are adequate.

Before any Work use, record:

WORK_NECESSITY = PASS or FAIL

PASS requires all of the following:

1. the exact missing capability is identified
2. normal Sol High cannot adequately perform it
3. OpenCode with Muse Spark 1.3 cannot adequately perform it
4. the capability is genuinely required
5. the Work assignment is reduced to the smallest possible operation

If any condition is missing, WORK_NECESSITY = FAIL and Work must not be used.

If Work is necessary, use GPT-5.6 Sol Medium by default. Do not give Work an entire workstream when only one operation requires it. The result returns to normal Sol High and the remaining work continues outside Work.

## 6. Parallelism

Parallelism is allowed only across independent work surfaces.

Before starting another OpenCode lane, verify branch ownership, current remote head, active worker, touched files and semantic surface, active CI or runtime runs, and expected output.

Do not run competing OpenCode edits against the same semantic implementation surface. Do not overwrite or force-push over another worker. Preserve source-valid in-progress qualification runs.

## 7. Context and persistence

Do not send the entire project history to every worker. Each workstream receives only relevant global invariants, exact source lock, current state, workstream contract, hard gates, blockers, evidence requirements and exact next action.

Every workstream starts with a WORKSTREAM CONTRACT containing Objective, Inputs, Authority, In Scope, Out of Scope, Dependencies, Required Deliverables, Hard Gates, Evidence Requirements and Stop Conditions.

Every workstream ends with a SELF-CONTAINED HANDOFF containing Source Lock, Work Completed, New Findings, Changes, Tests / Evidence, PASS / FAIL / UNKNOWN, Remaining Blockers, Outputs, Dependencies Unblocked and Exact Next Action.

Material progress must be persisted so another qualified worker can resume after interruption.

## 8. Source Truth and qualification

Project truth order remains:

1. newest direct user instruction
2. freshly verified technical state
3. current canonical domain data
4. current primary sources
5. historical reports and chats as provenance

For software, fresh repository, branch and commit state outrank reports.

For MTG, current Comprehensive Rules, official Oracle and official rulings outrank engine behavior, which outranks secondary sources.

Qualification invariants remain:

- UNKNOWN is not PASS
- PARTIAL is not FULL
- NOT_RUN is not PASS
- CODE_DERIVED is not RUNTIME_VERIFIED
- parsing or import does not prove card functionality
- construction does not prove behavior
- material source changes require impact adjudication and affected reruns where necessary
- unsupported production-reachable discretionary paths fail closed

Forbidden fallbacks remain first option, random option, default yes or no, hidden engine AI, GUI default, silent skip, parent fallback, fabricated legal actions and any second hidden Rules engine.

## 9. Coordinator authority

The normal Sol High Coordinator decides the next workstream, whether OpenCode is required, safe parallelization, evidence credit, failure attribution, required reruns, convergence timing, Architecture Freeze, production-provider selection and whether Work passes the necessity gate.

## 10. Canonical routing summary

Normal Sol High = reasoning, research, authority, coordination and adjudication.

OpenCode with Muse Spark 1.3 = repository implementation, execution, audits, debugging, qualification and mechanical repository work.

Work with Sol Medium = exceptional irreducible capability only after WORK_NECESSITY = PASS.

Never trade correctness or evidence quality for quota efficiency.
