# Commander Simulation Foundry - Execution Routing Supersession

Status: ACTIVE
Date: 2026-09-08
Updated: 2026-09-09

Canonical policy: PROJECT_EXECUTION_POLICY.md
Machine-enforced OpenCode config: ../opencode.json

This note supersedes historical execution-routing instructions without rewriting their technical evidence.

The current project has exactly three execution paths:

1. normal ChatGPT with GPT-5.6 Sol High
2. OpenCode Go with Muse Spark 1.3 Contributor
3. ChatGPT Work with Astra, exceptional only

Muse Spark 1.3 is a single AI model identity and must not be split into Muse and Spark resources.

The only authorized OpenCode provider/model is:

`opencode-go/muse-spark-1.3-contributor`

Allowed OpenCode reasoning effort is High or XHigh only. High is the minimum; XHigh is the default and preferred effort. Medium, low, minimal, none, off, and any lower effort are not authorized for project execution.

Use XHigh by default for substantial implementation, debugging, audits, CI/runtime qualification, provider/Rules-Core boundary work, repeated remediation, long autonomous campaigns, semantic integration, multi-file work and difficult evidence reconciliation. When uncertain between High and XHigh, choose XHigh. Use High only for clearly bounded, local, mechanical or low-ambiguity work where additional reasoning is not expected to materially improve correctness or robustness. Do not downgrade to High merely to conserve tokens when more reasoning could plausibly improve the result.

OpenCode Zen free models are not part of current routing while OpenCode Go is active. No other OpenCode model or provider may be substituted without a newer direct user instruction and corresponding policy/config update.

Historical instructions such as one Work chat only, single ChatGPT Work chat, Work-first execution, separate Muse and Spark routing, Muse High/XHigh as separate model identities, use of another OpenCode model, permission to run OpenCode below High, High as the OpenCode default, Work with Sol Medium, or a different Work effort policy are no longer operationally authoritative.

Technical findings, source locks, defect registers, Rules analysis and evidence from historical handoffs remain provenance unless superseded by fresher technical or domain truth.

Current routing is:

- normal Sol High for coordination, research, architecture, Rules and Oracle analysis, review, evidence adjudication, and maximum feasible pre-work before any Work handoff
- OpenCode Go with Muse Spark 1.3 Contributor at High or XHigh, with XHigh as default/preferred, for repository implementation, debugging, CI, qualification, audits and mechanical repository work
- Work with Astra only after WORK_NECESSITY = PASS

WORK_NECESSITY = PASS requires that the exact missing capability is identified, normal Sol High is inadequate, OpenCode Go with Muse Spark 1.3 Contributor is inadequate, the capability is genuinely required, normal Sol High has already completed all useful preparatory work it can reasonably perform, and the Work scope is minimized to the irreducible operation.

If any condition is missing, WORK_NECESSITY = FAIL and Work is not used.

When Work is required:

- Astra Medium is the default and normal Work effort.
- Astra High is used only rarely when the specific irreducible Work-only operation materially requires more reasoning than Medium.
- High is not justified merely because the parent workstream is difficult.
- Sol High must perform all useful source locking, research, authority adjudication, narrowing, planning and context reduction before opening Work.
- Work receives the minimum necessary context: exact objective, exact inputs/IDs, already-proven facts, exact blocker, scope boundaries, required output, hard gates, stop conditions and return point.
- Work must not repeat completed research, broad discovery, comparison, summarization or planning.
- Work must not expand scope merely to consume more context; if broader work becomes necessary, it returns the exact blocker to Sol High.
- Work returns control immediately after the irreducible operation is complete; Sol High performs integration, adjudication and all remaining non-Work tasks.

Token efficiency must come from reducing scope, deduplicating context and doing as much work as possible in Sol High before handoff. It must never come from weakening correctness, qualification or evidence requirements.

This policy migration must not disturb source-valid qualification work. Do not rewrite immutable WS-47 authority, do not modify active WS-48 or WS-49 implementation or evidence merely for routing changes, and do not grant or revoke runtime credit because of worker choice alone.

Before assigning another OpenCode lane, verify the latest remote head, active owner, touched files and semantic surface, and active qualification runs. Avoid competing edits to the same implementation surface and fail closed rather than overwrite another worker.
