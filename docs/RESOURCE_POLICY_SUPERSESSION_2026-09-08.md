# Commander Simulation Foundry — Execution Routing Supersession

Status: **ACTIVE**  
Date: **2026-09-08**

Canonical policy: [`PROJECT_EXECUTION_POLICY.md`](PROJECT_EXECUTION_POLICY.md)

## Purpose

This note prevents historical prompts, audits and handoffs from regaining operational authority over execution-environment routing.

Technical evidence remains governed by normal Source Truth rules. This document changes only **who/what executes future work**.

## Superseded routing instructions

The following historical instruction patterns are no longer operationally authoritative:

- "one Work chat only";
- "single ChatGPT Work chat";
- instructions to continue an entire implementation/qualification sequence inside Work;
- Work as the default environment for repository research, code audit, MTG Rules research, architecture, qualification design, evidence adjudication or routine execution;
- automatic use of a high Work reasoning tier when normal Sol High/OpenCode/Muse/Spark can perform the task.

This specifically supersedes the execution-routing portions of historical artifacts such as `FINALIST_CONVERGENCE_PREAUDIT.md` that prescribed a single Work chat and Work-centric execution. Their source locks, technical findings, defect registers, Rules analysis and other evidence remain historical provenance unless separately superseded by fresher technical/domain truth.

`FINALIST_CONVERGENCE_AUDIT_COMPLETE_REVERIFIED.md` remains usable as technical audit provenance. Any execution-environment assumption embedded in or inferred from its predecessor context is governed by the current execution policy instead.

## Current routing

Use:

- **normal ChatGPT Sol High** — coordinator, integration, architecture, Rules/Oracle analysis, hard technical reasoning, evidence adjudication;
- **OpenCode** — substantial repository implementation, runtime execution, CI and remediation loops;
- **Muse** — independent audit, review and non-colliding investigations;
- **Spark 1.3** — bounded mechanical work;
- **ChatGPT Work / Sol Medium** — only after `WORK_NECESSITY = PASS`, and only for the smallest irreducible capability-specific operation.

## Active-lane preservation

This policy migration must not invalidate or disturb source-valid qualification work merely to change routing documentation.

In particular:

- do not rewrite immutable WS-47 qualification authority;
- do not modify active WS-48 Forge implementation/evidence merely for this policy migration;
- do not modify active WS-49 XMage implementation/evidence merely for this policy migration;
- do not grant or revoke runtime PASS because of worker/model choice alone;
- do not merge Draft PRs solely to adopt this routing policy.

New workstream prompts and coordinator instructions must follow `PROJECT_EXECUTION_POLICY.md`.

## Collision rule

Before assigning OpenCode, Muse or another implementation-capable worker to an active workstream:

1. verify the latest remote branch head;
2. determine the current worker/owner and touched surfaces;
3. avoid duplicate edits to the same semantic implementation surface;
4. preserve source-valid in-progress qualification runs;
5. fail closed rather than overwrite another worker.

## Work Necessity reminder

Work may be used only when all ordinary paths are inadequate for a specifically identified required capability.

`WORK_NECESSITY = PASS` requires documented elimination of adequate execution through:

- normal Sol High;
- OpenCode;
- Muse;
- Spark 1.3;

plus minimized Work scope.

Otherwise:

`WORK_NECESSITY = FAIL`

and Work is not used.
