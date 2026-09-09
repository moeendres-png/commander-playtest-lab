# Commander Simulation Foundry - Project Execution Policy

Status: ACTIVE / CANONICAL EXECUTION ROUTING
Effective: 2026-09-08
Updated: 2026-09-09

This policy controls how project work is executed. It does not weaken Rules correctness, evidence quality, qualification standards, fail-closed behavior, reproducibility, Source Truth, or the Rules-Core/Pilot boundary.

Older prompts or handoffs that prescribe another execution environment, OpenCode model, provider, or effort policy remain historical provenance only. Their technical evidence is not rewritten, but their execution-routing instructions are superseded here.

## 1. Available execution paths

There are exactly three project execution paths:

1. normal ChatGPT with GPT-5.6 Sol High
2. OpenCode Go with Muse Spark 1.3 Contributor
3. ChatGPT Work with GPT-5.6 Sol Medium, exceptional only

Muse Spark 1.3 is one model identity. It must never be split into separate Muse and Spark resources.

## 2. Primary operating rule

Default execution uses normal Sol High and OpenCode Go with Muse Spark 1.3 Contributor.

ChatGPT Work is not a normal project environment. It may be used only when a required capability cannot reasonably be completed through normal Sol High or OpenCode Go with Muse Spark 1.3 Contributor.

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

## 4. OpenCode Go with Muse Spark 1.3 Contributor

The current project OpenCode provider is OpenCode Go only.

Canonical OpenCode model identity:

- provider ID: `opencode-go`
- model ID: `muse-spark-1.3-contributor`
- full OpenCode model ID: `opencode-go/muse-spark-1.3-contributor`

No other OpenCode model or provider is authorized for project work unless the user explicitly changes this policy.

The allowed reasoning-effort range is exactly:

- `high`
- `xhigh`

Default effort is `high`.

Use `high` for all normal substantial repository work, including implementation, tests, debugging, audits, CI, runtime qualification and bounded remediation. Use `xhigh` for especially difficult nonlocal implementation, complex multi-file debugging, high-risk remediation, or other cases where additional reasoning materially improves correctness.

Do not use `medium`, `low`, `minimal`, `none`, `off`, or any effort below `high` for project OpenCode work.

OpenCode Zen free models are not active project routing while OpenCode Go is in use. The current Zen free listing is a different provider/model identity and must not be substituted silently. If the user later changes provider policy, the replacement must be explicitly source-locked before use.

Use OpenCode Go with Muse Spark 1.3 Contributor for substantial repository execution, including:

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

OpenCode Go with Muse Spark 1.3 Contributor may produce implementation and evidence but does not independently grant global architecture credit.

The repository root `opencode.json` is the machine-enforced project configuration for provider/model selection and allowed variants. Project prompts must not override it with another model or an effort below High.

## 5. Work budget and necessity gate

Work is forbidden for ordinary tasks that normal Sol High or OpenCode Go with Muse Spark 1.3 Contributor can perform.

Do not use Work for ordinary research, GitHub reading, repository investigation, architecture, code review, MTG Rules or Oracle work, evidence adjudication, coordination, prompt creation, test design, static analysis, candidate comparison, report reading, implementation, CI, debugging, runtime qualification or mechanical repository work when the normal paths are adequate.

Before any Work use, record:

WORK_NECESSITY = PASS or FAIL

PASS requires all of the following:

1. the exact missing capability is identified
2. normal Sol High cannot adequately perform it
3. OpenCode Go with Muse Spark 1.3 Contributor cannot adequately perform it
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

OpenCode Go with `opencode-go/muse-spark-1.3-contributor` only = repository implementation, execution, audits, debugging, qualification and mechanical repository work. Allowed effort = High or XHigh only. Default = High.

Work with Sol Medium = exceptional irreducible capability only after WORK_NECESSITY = PASS.

Never trade correctness or evidence quality for quota efficiency.
