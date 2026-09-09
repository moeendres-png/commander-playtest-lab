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
3. ChatGPT Work with GPT-5.6 Sol Medium, exceptional only

Muse Spark 1.3 is a single AI model identity and must not be split into Muse and Spark resources.

The only authorized OpenCode provider/model is:

`opencode-go/muse-spark-1.3-contributor`

Allowed OpenCode reasoning effort is High or XHigh only. High is both the minimum and the default. Medium, low, minimal, none, off, and any lower effort are not authorized for project execution.

Use High for normal implementation, tests, debugging, audits, CI, runtime qualification and bounded remediation. Use XHigh for especially difficult nonlocal implementation, complex debugging, high-risk remediation or other tasks where additional reasoning materially improves correctness.

OpenCode Zen free models are not part of current routing while OpenCode Go is active. No other OpenCode model or provider may be substituted without a newer direct user instruction and corresponding policy/config update.

Historical instructions such as one Work chat only, single ChatGPT Work chat, Work-first execution, separate Muse and Spark routing, Muse High/XHigh as separate model identities, use of another OpenCode model, or permission to run OpenCode below High are no longer operationally authoritative.

Technical findings, source locks, defect registers, Rules analysis and evidence from historical handoffs remain provenance unless superseded by fresher technical or domain truth.

Current routing is:

- normal Sol High for coordination, research, architecture, Rules and Oracle analysis, review and evidence adjudication
- OpenCode Go with Muse Spark 1.3 Contributor at High or XHigh for repository implementation, debugging, CI, qualification, audits and mechanical repository work
- Work with Sol Medium only after WORK_NECESSITY = PASS

WORK_NECESSITY = PASS requires that the exact missing capability is identified, normal Sol High is inadequate, OpenCode Go with Muse Spark 1.3 Contributor is inadequate, the capability is genuinely required, and the Work scope is minimized.

If any condition is missing, WORK_NECESSITY = FAIL and Work is not used.

This policy migration must not disturb source-valid qualification work. Do not rewrite immutable WS-47 authority, do not modify active WS-48 or WS-49 implementation or evidence merely for routing changes, and do not grant or revoke runtime credit because of worker choice alone.

Before assigning another OpenCode lane, verify the latest remote head, active owner, touched files and semantic surface, and active qualification runs. Avoid competing edits to the same implementation surface and fail closed rather than overwrite another worker.
