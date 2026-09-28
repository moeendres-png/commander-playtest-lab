# Astra project integrity and legacy consolidation

Objective: reconcile the canonical operating layer and GitHub retention state,
recover still-useful sealed legacy tooling deltas, and guard repaired behavior.

Authority: direct user assignment of 2026-09-28. Astra execution is explicitly
requested for this bounded integrity workstream; no new Work task is dispatched.

Source lock: Lab main `e91819ae18166a9f91ca52d101a72c8cb8eddade`, tree
`3568047a171e84e8f57b3b8b6c013a92b05c9f0d`.
Branch: `astra/project-integrity-20260928`. Sole writer: this Astra session.
Checkout: dedicated `work/astra-project-integrity-20260928` clone.

Owned surfaces: Foundry operating-policy consistency, selected legacy Foundry
helpers and their tests, canonical operating documentation, this audit directory,
and evidence-backed GitHub issue/retention dispositions.

Foreign-active: Space Bunny and Muse completion campaigns; #278, #269;
provider config, qualification, engine-bridge, engine/rules, freeze-readiness
packets, their manifests/state and all Forge/Mage implementation. No unpublished
campaign content is consumed. Only named sealed historical donor commits are read.
Fresh #278 changed-path inventory has no overlap with the owned tooling repairs.
The observed active WSR23 worktree has no dirty tracked paths; its metadata is
read only, and neither its worktree nor its branch is altered.

Dependencies: live GitHub refs; exact sealed donor objects when accessible;
local hermetic tests; current-main drift review and exact-head CI before merge.

Hard gates: no provider choice, freeze, evidence promotion, history rewrite,
force-push, secret output, donor deletion, foreign writer or direct-main write.
No engine qualification rerun. Missing evidence remains UNKNOWN.

Deliverables: CURRENT_PROJECT_INTEGRITY_AUDIT, GOVERNANCE_DRIFT_MATRIX,
OPEN_ISSUE_DISPOSITION, LEGACY_DONOR_ADJUDICATION, PR_BRANCH_RETENTION_LEDGER,
IMPLEMENTED_REPAIRS, regression tests, GitHub receipt and final handoff.

Persistence: source-bound JSON ledgers, scoped commits, one dedicated PR.
Stop only for completed scope or documented ownership/source/authority gate.
Retain donor/PR evidence whenever preservation or integration is unproven.

`ARCHITECTURE_FREEZE = NOT CLAIMED`
`PRODUCTION_PROVIDER = NOT SELECTED`
