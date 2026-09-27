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

## Pull request lanes

| Lane | Pull requests | Rule |
| --- | --- | --- |
| Active campaign | #275 (WSR23), #271 (governance), #269 (WSR22) | Owned by a running workstream. Do not close, rebase or take over. |
| Active provider lanes | #163 (WS-48 Forge), #164 (WS-49 XMage) | Owned by their workers. Do not disturb. |
| Provenance, do not close | #122, #126, #128, #132, #135–#160, #165 | Unique content, never merged. Preserve branch + PR. |
| Lineage-superseded provenance | #142, #145, #155, #158, #159, #160 | Superseded in lineage, deliberately not merged; some are still cited by the live v1.0.5 contract as record provenance. |
| Terminal fail-closed records | #154, #156, #159, #160 | Document blocked-by-immutable-upstream outcomes. Keep as records. |
| Merged, evidence preserved | #266, #270, #272, #273 | Current-main deliveries; receipts recorded in their workstream packets. |

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

## Open issues

| Issue | State |
| --- | --- |
| #255 | Final pre-Freeze critical path (XMage vs Forge provider adjudication). Active decision lane. |
| #263 | WSR23 project integration, hygiene and publication closure. Active. |
| #267 | WSR24 Architecture Freeze and production bootstrap readiness. Active. |
| #193 | WS93 COMPLETE receipt, but terminal commit `48daaf9` is **local-only** — publish before closing. |
| #192 | Accidental direct-to-main commit `6eea80fb` still present in `main` history; revert-vs-accept decision pending. |
| #204 | Publisher effective-target identity gap still unaddressed in `tools/foundry/`. |
| #205 | Forge WS236-S1: publication done, authorization half blocked by #204. Forge Muse owns closure. |
| #190, #191, #196 | Standing Foundry capability workstreams (resilience, quota economy, cross-repo tool routing). |

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
