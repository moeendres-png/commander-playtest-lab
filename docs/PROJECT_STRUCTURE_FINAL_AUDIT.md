# Project structure final audit – H

## Canonical technical truth

`GitHub main` is the authoritative software truth. Drive stores current status, canonical MTG data references, recovery artifacts, audit evidence and historical evidence; it is not a second source-code branch.

## Active repository structure

- `src/` – product/source code.
- `tests/` – unit/integration/contract/property/golden/regression/eval/rules tests.
- `config/` – active configuration.
- `.github/workflows/` – four active workflows only.
- `.runtime/` and `data/runs/` – ignored runtime output.
- `artifacts/` – checked-in audit/fixture/history material plus explicitly ignored generated subsets; not treated as a general runtime directory.

## Active workflows

| Workflow | Classification | Role |
|---|---|---|
| `ci.yml` | REQUIRED | quality, test, security and packaging checks |
| `release-artifacts.yml` | REQUIRED | PR release/recovery verification and canonical-main recovery snapshot |
| `windows-runtime.yml` | REQUIRED | Windows runtime and clean-tree verification |
| `external-engine-integration.yml` | OPTIONAL_MANUAL | real XMage integration boundary; not an H gate |

Historical Actions records with no corresponding file on main are `HISTORICAL_METADATA`.

## Branches

The previously retained F branches remain classified and are handed to I for final historical disposition. `audit/g-modeling-data-quality` is `DELETE_SAFE_MANUAL` and intentionally deferred by direct user instruction. H must leave no branch unclassified, but classification does not imply deletion.

## Drive

Current-looking Drive documents/artifacts that predate current GitHub main must be moved/marked historical after H's final main/recovery verification. A single current status/source index/recovery pointer must remain. Historical recovery and audit evidence is retained.

## Final target metrics

These are only set to zero after post-merge verification and Drive readback:

- `parallel_truths`
- `unclassified_active_branches`
- `unclassified_latest_files`
- `broken_active_links`

## Refreshed non-main branch classification against H baseline main

All listed non-main branches are currently `diverged` from `f8d42919a37e93f34756907ac86ceb2e6a13be4c`.

| Branch | Ahead | Behind | H action |
|---|---:|---:|---|
| `agent/audit-d-limitation-remediation` | 7 | 21 | `DEFER_TO_I` |
| `agent/limitation-remediation-d` | 3 | 21 | `DEFER_TO_I` |
| `audit/g-modeling-data-quality` | 42 | 1 | `DELETE_SAFE_MANUAL` |
| `backup/pr5-before-main-18826-sync-2026-08-08` | 12 | 79 | `DEFER_TO_I` |
| `backup/runtime-hygiene-pre-cleanup-2026-08-07` | 16 | 127 | `DEFER_TO_I` |
| `backup/windows-atomic-write-pre-main-sync-2026-08-07` | 2 | 154 | `DEFER_TO_I` |
| `docs/d-closeout-e-handoff` | 2 | 20 | `DEFER_TO_I` |
| `feature/external-engine-foundation` | 8 | 77 | `DEFER_TO_I` |
| `feature/external-engine-foundation-v2` | 7 | 77 | `DEFER_TO_I` |
| `fix/1.13.4-strict-quality` | 17 | 21 | `DEFER_TO_I` |
| `fix/1.13.4-strict-quality-controlled` | 39 | 21 | `DEFER_TO_I` |
| `measure/e-perf-32-postfix` | 33 | 19 | `DEFER_TO_I` |
| `merge/1.13.4-main-reconciliation` | 1 | 33 | `DEFER_TO_I` |
| `research/korvold-rogshai-pod-meta` | 8 | 147 | `DEFER_TO_I` |
| `sync/canonical-drive-1.13.3` | 2 | 79 | `DEFER_TO_I` |

The G branch is safe to delete because its validated final tree was squash-merged into main; its large `ahead` count reflects staging/transport history rather than unmerged product truth. The other branches retain F's fail-closed historical/exclusive-information classification and are deliberately not deleted by H.

`unclassified_active_branches = 0` for the H inventory.
