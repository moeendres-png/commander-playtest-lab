# docs/ — navigation index

Maintained as a navigation aid, **not as authority**. Where this index and a governing
document disagree, the governing document wins (see `AGENTS.md` §3 Source Truth).

## Before anything else

| Question | Go to |
|---|---|
| What are the durable rules for every session? | `AGENTS.md` (repository root) |
| What is the project trying to build? | `PROJECT_MISSION.md` |
| What are the current engine pins? | `../config/rules_engines.json` — sole machine-readable pin authority |
| Who may execute what, and at which effort? | `AGENTS.md` §6–§7 and `COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md` |
| How is a Foundry workstream started? | `../.opencode/skills/workstream-bootstrap/SKILL.md` |
| How do I resume an interrupted one? | `../.opencode/skills/continuation/SKILL.md` |
| Which PRs / issues / branches are live? | `REPOSITORY_TRIAGE_INDEX.md` |
| What counts as PASS? | `AGENTS.md` §4 |

## Governing documents in this directory

- `PROJECT_MISSION.md` — governing mission policy. Outranks any summary elsewhere.
- `COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md` — current execution authority.
- `EVIDENCE_INDEX_REQUIREMENTS.md` — evidence index schema; companion to
  `RETENTION_AND_LIFECYCLE_POLICY.md`.
- `ARCHITECTURE_FREEZE = NOT CLAIMED` / `PRODUCTION_PROVIDER = NOT SELECTED` is the
  machine-readable status in `../config/rules_engines.json`. A document repeating that
  status in prose is not the source of truth for it.

## Subdirectories

| Directory | What it is |
|---|---|
| `foundry-execution/` | **Canonical** Foundry execution system. Start at its `README.md`. |
| `architecture/` | Architecture decision records and design direction. |
| `archive/legacy_phase_artifacts/` | Archived Phase 2–9 reports. Historical provenance only. |
| `project_integrity_20260928/` | Repository/PR/branch/ownership integrity records and dispositions. |
| `project_integration_hygiene_20260927/` | Prior integration/hygiene workstream packets. Dated. |
| `architecture_freeze_readiness_20260927/` | Freeze-readiness packets. Readiness evidence, not a freeze claim. |
| `pre_freeze_completion_20260927/` | Pre-freeze campaign state and provider readiness packets. Dated. |
| `claude_independent_review_20260929/`, `muse_final_integration_20260928/` | Independent review and donor-integration dispositions. Dated. |
| `workstream_*`, `1.20/`, `counterfactual/`, `diagnostics/`, `reconciliation/`, `roadmap/`, `optimizer-v2/`, `meta/`, `mulligan_lab/`, `multiplayer_findings/`, `J_P3_*_RAW_EVIDENCE/` | Dated per-workstream evidence and diagnostics. Historical unless a governing document says otherwise. |

Most `workstream_*` directories are single-workstream packets with no current action
attached. Read the packet's own status/contract before relying on it.

## Two directories that differ only by separator

`decision-quality/` (hyphen) and `decision_quality/` (underscore) both exist and are
non-empty. Neither is referenced by `AGENTS.md` or by `foundry-execution/README.md`.
Read the `README.md` inside each before assuming either is canonical.

## Filename traps

Filenames containing `CURRENT`, `FINAL`, `LATEST`, or `MASTER` **confer no authority**
(`AGENTS.md` §3). This is not a convention observed everywhere: for example
`PROJECT_UPDATE_CURRENT_STATE.md`, `CARD_COVERAGE_CURRENT.md`,
`NEXT_STEP_HANDOFF_J_P6_TO_FINAL.md`, and the directory
`../qualification/final-current-boundary-20260927/` all carry those tokens without
carrying current status. Establish authority from the governing document and the
index entry that names it, never from the filename.

The chained `NEXT_STEP_HANDOFF_*.md` files in this directory are historical handoff
snapshots. They state the authority that applied when they were written, sometimes as a
present-tense claim, and sometimes conditioned on a merge that has long since happened.
They are provenance, not a work queue. A current workstream comes from explicit user
assignment plus a dedicated state file, never from a handoff file.

## Adding to this directory

Prefer one canonical index over copying policy into new files. If a new document repeats
an existing rule, link to the governing document instead of restating it. New
`CURRENT`/`FINAL`-style names are discouraged for exactly the reason above.
