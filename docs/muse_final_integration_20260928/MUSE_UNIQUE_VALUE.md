# Muse unique value — final integration assessment

## Terminal integration update — 2026-09-29

The audit-time integration dependency described later in this document is now resolved.

- PR #291 merged the PB-03 dimension-admission discriminator and terminal Muse inventory.
- PR #292 merged the remaining Tier-1/Tier-2 Muse runtime-test assets after replacing donor-era sorted-first mana choices with explicit semantic-source and engine `mana_type` scripts.
- #292 exact head passed Production Qualification, CI, External XMage Integration, Full Game Conformance, Real 4P Technical Smoke and H4 Docker Materialization.
- No historical Muse PASS count was transferred.
- PR #284 remains active for broader non-Muse/current-boundary work, but its overlapping Muse test variants are superseded by current main.

Therefore there is no remaining Muse-specific integration dependency.

`MUSE_CODE_SALVAGE = COMPLETE`

`MUSE_REMAINING_INTEGRATION_READY = NO`

## Executive result

The Muse history contains real unique engineering value, but most of it is either already canonical or tied to older qualification/provider architectures.

The surviving unique value is concentrated in XMage PB-03 native-restoration tests.

No whole Muse branch should be merged.

## 1. Unique engineering that already survived into canonical project code

### Cross-repository Foundry hardening

`project/opencode-muse-cross-repo-hardening-v2-20260910@ec68024593904b648fd03d2fb518bee94cfa4d3b` is an ancestor of current main.

Disposition: **already canonical**.

### Governance / routing mechanisms

Several files from `governance/space-bunny-max-muse-xhigh-successor-20260927` are byte-identical on main, and the rest have later versions implementing the current authority model:
- Space Bunny MAX default/preferred;
- Muse XHIGH explicit alternate;
- no active Muse HIGH lane;
- normal owned-branch Git/GitHub authority;
- no mandatory `safe_push` ancestry gate.

Disposition: **already canonical or superseded by later stronger versions**.

### Privacy principle

Muse's project-data/private-data distinction survives in current `AGENTS.md`:
project technical data is permitted; unrelated private data and raw secrets are not.

The old Muse-HIGH-primary execution implementation did not survive and should not.

## 2. Unique Muse code ported during final salvage

### PB-03 dimension-admission discriminator

`XmagePb03DimensionAdmissionTest.java`

This is the cleanest immediately reusable Muse artifact.

It:
- reads the frozen PB-03 records;
- proves which records the native restoration seam can parse;
- pins exact fail-closed unsupported dimensions;
- does not turn construction into behavior credit.

It is ported onto `sol/muse-final-salvage-20260929`.

## 3. Unique Muse code integrated after audit

The PB-03 Tier-1/Tier-2 runtime suites were independently ported from the Muse donor onto a clean current-main branch and merged through PR #292.

The donor-era evidence-integrity defects are resolved in the canonical version:
- no sorted-first or action-id-based mana selection;
- mana abilities bind explicit semantic test source ids to native engine `source_object_id`;
- multi-option mana-pool decisions require explicit engine-authored `mana_type` scripts;
- ambiguous or absent matches fail closed;
- the Rules-RNG characterization still observes but does not answer the unscripted Heads/Tails call.

Integrated assets:
- `XmagePb03Tier1RowsTest.java`
- `XmagePb03Tier2CmdZoneTest.java`
- `XmagePb03Tier2ControlTurnTest.java`
- `XmagePb03Tier2StackTest.java`

These are current runtime regression assets. They do not by themselves bypass the normal receipt/impact-adjudication requirements for qualification PASS.

## 4. Muse ideas independently solved better

### PB-10 source-name false credit

Muse independently found the defect, but the current receipt model is stronger:
positive credit now requires exact runtime receipts and a positive behavior assertion.

The old Muse assembler patch is not needed.

### WS49 source identity

Muse added an optional expected Git tree check.

Current exact Git commit verification already binds the tree, while current provider handshake/source-lock/receipt machinery additionally binds the actual runtime candidate. The Muse change did not protect the offline declared-source path.

No port.

### WS49 fallback-zero inventory

The static inventory was useful as review evidence but intentionally always returned zero.

Current runtime-negative tests and Meta Qualification are stronger.

No port.

### R11 replay/paired cumulative work

The historical local commit was never published and cannot be reconstructed byte-for-byte.

Later canonical work independently provides replay-tape v1, hidden-state semantic replay and cumulative L1→L7 runtime evidence.

No attempt is made to pretend the old commit itself was merged.

## 5. Muse code rejected

### WS48 old behavior driver

Rejected for current production/evidence use because:
- it is tied to obsolete Forge v1.0.5 overlay/pin assumptions;
- the behavior driver contains unscripted sorted-first option selection;
- one fresh-run negative-cause path also picks the first sorted payment option;
- current Forge dual-identity/provider evidence and runtime negative controls are stronger.

Historical design/postcondition ideas remain useful provenance.

### Old Muse-HIGH-primary execution policy

Rejected because current direct authority requires Space Bunny MAX default and Muse XHIGH-only.

## 6. Muse evidence retained only as provenance

### Generated PB-03 Wave results

Useful for discovering tests and mechanisms, but not current PASS credit.

### Pristine Forge PB-09 experiment

Useful as control/attribution context, but its engine identity was operator-supplied while PB-05 was open.

No provider capability credit.

## 7. Local-only / unavailable work

Historical Muse R11:
- reported `7ad4e944...`;
- no GitHub object or exact published descendant was found;
- exact bytes therefore remain `UNRECOVERABLE_LOCAL_ONLY`.

The intended replay capability has later canonical replacements.

## 8. Remaining integration dependency

None that is Muse-specific.

The previously identified PB-03 mana-choice P1 was repaired and the hardened test family was merged through PR #292 with all exact-head gates green. PR #284 continues independently for broader project work; its Muse test overlap must preserve current-main semantics.

## Final answer to “did we forget good Muse work?”

No.

Every discovered Muse branch and the 12-commit current donor has a terminal disposition. The high-value PB-03 test assets are now hardened and merged on current main through PRs #291 and #292. No remaining Muse-specific code is waiting for integration, and no historical generated PASS count was promoted.

`MUSE_INVENTORY_COMPLETE = YES`

`MUSE_UNIQUE_CODE_ADJUDICATED = YES`

`MUSE_CODE_SALVAGE = COMPLETE`

`MUSE_REMAINING_INTEGRATION_READY = NO`

`MUSE_UNRESOLVED_UNKNOWN = NO`

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
