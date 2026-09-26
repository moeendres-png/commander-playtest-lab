# Audit Point F — Post-Cleanup Inventory

Date: 2026-08-08

## Canonical software state

- Version: `1.13.4`
- Branch: `main`
- Post-E merge commit at cleanup start: `ae7be044fb9edc86ed353422dbc4e16766261ad2`
- Repository visibility: public
- Canonical deck mutations during F: `0`
- Inventory/allocation mutations during F: `0`

Point F changed project organization only. It did not alter Korvold, RogShai, Kaervek, opponent content, inventory quantities, or simulation semantics.

## GitHub cleanup

A one-shot cleanup workflow (`run 31279203285`) classified every remote branch against `origin/main` and deleted a branch only when its tip was already an ancestor of `main`. The workflow completed successfully and uploaded evidence artifact `9027914170` with digest:

`sha256:750f35345a3b37d7013bab559f488c652d61c65891d8bce231d7b37196eadfb5`

### Result

- Fully merged stale branches deleted: **24**
- Branches retained because they still contain exclusive commits: **14**
- Active canonical branch: `main`
- Git tags: none
- GitHub Releases: none
- Temporary cleanup branch/workflow: self-deleted and not part of `main`

### Deleted branches

- `agent/audit-e-bug-remediation`
- `backup/external-engine-foundation-pre-rebase-2026-08-07`
- `backup/pr5-external-engine-before-rebuild-2026-08-08`
- `backup/release-1.13.1-pre-rebase-2026-08-07`
- `canonical/drive-1.13.3-exact`
- `feature/data-sync-before-xmage`
- `feature/external-engine-foundation-main`
- `fix/1.13.4-portable-snapshots`
- `fix/1.13.4-pretest-ruff`
- `fix/ci-bootstrap`
- `fix/release-1.13.1-current-deck-metadata`
- `fix/runtime-hygiene`
- `fix/runtime-hygiene-final`
- `fix/windows-atomic-write`
- `historical/github-main-pre-reconciliation-2026-08-08`
- `reconcile/1.13.3-hardening`
- `reconcile/1.13.3-hardening-runtime-port-staging`
- `release/1.13.1`
- `release/1.13.1-canonical-main`
- `release/1.13.4-final`
- `release/1.13.4-reconciliation`
- `release/canonical-1.13.3`
- `release/final-acceptance-main`
- `work/1.13.4-pretest-variants`

### Retained branches with exclusive commits

These were deliberately **not** deleted. Exclusive history is a hard stop for destructive cleanup.

| Branch | Ahead | Behind | F action |
|---|---:|---:|---|
| `agent/audit-d-limitation-remediation` | 7 | 5 | REVIEW_REQUIRED |
| `agent/limitation-remediation-d` | 3 | 5 | REVIEW_REQUIRED |
| `backup/pr5-before-main-18826-sync-2026-08-08` | 12 | 63 | KEEP_HISTORICAL |
| `backup/runtime-hygiene-pre-cleanup-2026-08-07` | 16 | 111 | KEEP_HISTORICAL |
| `backup/windows-atomic-write-pre-main-sync-2026-08-07` | 2 | 138 | KEEP_HISTORICAL |
| `docs/d-closeout-e-handoff` | 2 | 4 | REVIEW_REQUIRED |
| `feature/external-engine-foundation` | 8 | 61 | KEEP_HISTORICAL |
| `feature/external-engine-foundation-v2` | 7 | 61 | KEEP_HISTORICAL |
| `fix/1.13.4-strict-quality` | 17 | 5 | REVIEW_REQUIRED |
| `fix/1.13.4-strict-quality-controlled` | 39 | 5 | REVIEW_REQUIRED |
| `measure/e-perf-32-postfix` | 33 | 3 | REVIEW_REQUIRED |
| `merge/1.13.4-main-reconciliation` | 1 | 17 | KEEP_HISTORICAL |
| `research/korvold-rogshai-pod-meta` | 8 | 131 | KEEP_HISTORICAL |
| `sync/canonical-drive-1.13.3` | 2 | 63 | KEEP_HISTORICAL |

The strict-quality branches remain intentionally available because repository-wide strict Mypy debt is still explicit project debt; potentially useful exclusive typing work must be evaluated before those branches can be removed.

## Google Drive cleanup

### Permanently deleted

One duplicate object was proven empty before deletion:

- Empty duplicate `17_Mulligan_Lab` folder, Drive ID `1Ftt8cy9ADZ0PuLwIWGqEhT7pFsCXdXun`.

The populated `17_Mulligan_Lab` folder remains in the active project area.

### Archived rather than deleted

Unique historical evidence was preserved and moved out of the active project surface:

- stale/mixed former `00_LATEST` → `99_Historical/HISTORICAL_00_LATEST_PRE_E_2026-08-08`;
- six obsolete/superseded 1.13.3 data-sync phase folders;
- 1.13.4 pretest-variants release folder;
- older 2026-08-06 final-system-audit folder;
- stale pre-1.13.4 canonical-entry document;
- historical external-engine-fix note;
- old 1.10.3 repair and 1.12.0 intermediate folders.

### Active Drive workspace after cleanup

The active `00_CURRENT_CANONICAL_2026-08-06` project workspace now primarily contains:

- `2026-08-08_SYSTEM_AUDIT_AND_ROADMAP`;
- `22_Kaervek_Opponent_Sync`;
- phase-support folders 10–19;
- current documentation/validation/recovery/source areas;
- `99_Historical` and `99_Incomplete_or_Unverified`.

There is intentionally **no newly fabricated `00_LATEST` release pointer** after F. The old pointer was incorrect and therefore archived. A new release/pointer belongs to organizational/release work in H only after the required release gates are satisfied.

## One-current-truth result

For software source truth after F:

`GitHub main` is authoritative.

Drive is an artifact, audit, data, research, and historical-evidence store. No remaining active Drive folder is being claimed by F as a newer software release than `main`.

## Items intentionally deferred

F does not destroy or merge branches that still have exclusive commits. Those branches require semantic review, especially:

- strict-quality/type-work experiments;
- pre-main external-engine work;
- research/meta work;
- D transport/closeout branches;
- old reconciliation branches with unique commits.

Final branch/tag/release governance and simplified Drive top-level structure are H concerns, not grounds for unsafe deletion in F.

## Verification plan

This evidence-only F branch must pass the repository's public GitHub workflows before merge:

- CI / quality / security;
- Release Artifacts including clean-tree and recovery roundtrip;
- Windows Runtime Hygiene.

That verification demonstrates that cleanup did not remove a source dependency required to restore or validate the current project.
