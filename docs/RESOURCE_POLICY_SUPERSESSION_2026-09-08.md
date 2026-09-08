# Commander Simulation Foundry - Execution Routing Supersession

Status: ACTIVE
Date: 2026-09-08

Canonical policy: PROJECT_EXECUTION_POLICY.md

This note supersedes historical execution-routing instructions without rewriting their technical evidence.

The current project has exactly three execution paths:

1. normal ChatGPT with GPT-5.6 Sol High
2. OpenCode with Muse Spark 1.3
3. ChatGPT Work with GPT-5.6 Sol Medium, exceptional only

Muse and Spark 1.3 are not separate resources in this project. The OpenCode resource is OpenCode with Muse Spark 1.3.

Historical instructions such as one Work chat only, single ChatGPT Work chat, Work-first execution, or separate Muse and Spark routing are no longer operationally authoritative.

Technical findings, source locks, defect registers, Rules analysis and evidence from historical handoffs remain provenance unless superseded by fresher technical or domain truth.

Current routing is:

- normal Sol High for coordination, research, architecture, Rules and Oracle analysis, review and evidence adjudication
- OpenCode with Muse Spark 1.3 for repository implementation, debugging, CI, qualification, audits and mechanical repository work
- Work with Sol Medium only after WORK_NECESSITY = PASS

WORK_NECESSITY = PASS requires that the exact missing capability is identified, normal Sol High is inadequate, OpenCode with Muse Spark 1.3 is inadequate, the capability is genuinely required, and the Work scope is minimized.

If any condition is missing, WORK_NECESSITY = FAIL and Work is not used.

This policy migration must not disturb source-valid qualification work. Do not rewrite immutable WS-47 authority, do not modify active WS-48 or WS-49 implementation or evidence merely for routing changes, and do not grant or revoke runtime credit because of worker choice alone.

Before assigning another OpenCode lane, verify the latest remote head, active owner, touched files and semantic surface, and active qualification runs. Avoid competing edits to the same implementation surface and fail closed rather than overwrite another worker.
