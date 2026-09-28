# Repository Triage Index

Durable orientation for the open pull requests, issues and branches of this
repository. Maintained as a navigation aid, not as authority: `config/rules_engines.json`
remains the sole machine-readable pin authority, and the newest direct user statement
outranks every file here.

`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.

## Why this file exists

The repository accumulated 30+ draft pull requests from superseded qualification
campaigns. They are **not** clutter: the project-integration audit classified most of
them as `SUPERSEDED_BUT_UNIQUE_CONTENT_REMAINS`, meaning the evidence exists nowhere
else. Closing them would strand that evidence, and deleting their branches would
destroy it. This index makes the backlog navigable instead of deleting it.

## Pull request lanes (2026-09-28 refresh)

Current source lock and every retained branch/path are in
[the integrity ledger](project_integrity_20260928/PR_BRANCH_RETENTION_LEDGER.json).
This is a timestamped snapshot, not a permanent ownership grant.

| Lane | Pull requests / branches | Rule |
| --- | --- | --- |
| Foreign active completion | #279; `sbmax/full-completion` | Preserve ownership; launcher repair is deferred to its owner. |
| Integrated successors | #271, #274, #275, #278 | Read merged source and exact receipts; integration alone is not provider PASS. |
| WSR22 provenance | #269 | Closed externally after successor integration; immutable history retained. No Astra rewrite. |
| Historical drafts | All remaining open legacy PRs in ledger | Divergent/unique committed content retained; no safe closure inferred from green CI or ancestry. |

## Label taxonomy

| Label | Meaning |
| --- | --- |
| `campaign:active` | Owned by a running workstream. |
| `provenance:preserve` | Unique unpublished content. Never close, never delete the branch. |
| `provenance:local-only` | Evidence exists only on one machine; publish before closing its receipt. |
| `status:superseded` | Superseded in lineage, intentionally not merged. |
| `status:terminal` | Terminal fail-closed record. |
| `status:conflict` | Branch diverged from `main`; merge or archive decision pending. |
| `needs:triage` | Awaiting Coordinator adjudication. |

## Issue dispositions (2026-09-28 refresh)

[Full source-bound adjudication](project_integrity_20260928/OPEN_ISSUE_DISPOSITION.json)
records all nine initially open issues and their final observed states.

| Issue | Disposition |
| --- | --- |
| #255 | ACTIVE provider-adjudication lane; untouched qualification decisions. |
| #190 | PARTIALLY_RESOLVED_UPDATE: interruption/telemetry present; watchdog and runtime measures remain. |
| #191 | ACTIVE: natural-session efficiency/rotation benchmark remains unmeasured. |
| #192 | COORDINATOR_DECISION_REQUIRED: preserve historical-main evidence pending explicit decision. |
| #193 | PARTIALLY_RESOLVED_UPDATE: exact Forge terminal is remotely published; owner retains content/integration disposition. |
| #196 | PARTIALLY_RESOLVED_UPDATE: optional cross-repo discovery remains; old safe-push-only authority superseded. |
| #205 | PARTIALLY_RESOLVED_UPDATE: publication done and #204 dependency resolved; residual cross-repo objective remains. |
| #204 | RESOLVED_CLOSE: already closed, effective-target remediation integrated in #253 and tests freshly pass. |
| #267 | RESOLVED_CLOSE: already closed, preparation delivered by #274; no Architecture Freeze claimed. |

## Branch policy

`delete_branch_on_merge` is enabled, so merged campaign branches are removed
automatically and the backlog stops growing. Unmerged provenance branches are never
deleted automatically, which is exactly the intended protection.

## Hygiene performed 2026-09-27 (WSR25)

- Repository description and topics set (they were empty).
- Label taxonomy created; the stray `ws07-pass` label received a real description.
- Closed #169 and #194 with recorded evidence; #193 deliberately left open.
- Evidence comments added to #192, #193, #204, #205.
- Legacy projects surface left untouched; the classic-projects deprecation warning is
  known and does not affect builds, tests or merges.
