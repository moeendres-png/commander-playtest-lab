# Muse final integration disposition — 2026-09-29

## Post-audit terminal integration update — 2026-09-29

This section supersedes all audit-time statements below that describe the PB-03 Tier-1/Tier-2 Muse tests as still gated on PR #284.

Canonical integration is now complete:

- PR #291 merged at `afe09c61d4ad90f89c28ff75ac7439a20b89cfdd`.
  - integrated `XmagePb03DimensionAdmissionTest.java` and the terminal Muse inventory/ledger;
  - exact PR head passed Production Qualification, CI, External XMage Integration, XMage Full Game Conformance, XMage Real 4P Technical Smoke and H4 Docker Materialization;
  - zero FULL107 behavior credit is granted merely from the dimension discriminator.
- PR #292 merged at `ca9356e3da662ce9e246e7f896f1a99772d59065`.
  - integrated the remaining Muse PB-03 Tier-1/Tier-2 runtime-test family on a clean current-main branch;
  - removed donor-era sorted-first/action-id mana selection and `firstPoolSpend`;
  - mana ability selection is bound by semantic test source id -> native `source_object_id`;
  - multi-option pool spending is permitted only through an explicit engine-authored `mana_type` script;
  - missing/ambiguous matches fail closed;
  - `MICRO_RULES_RANDOMNESS` still stops at the real Heads/Tails choice because the frozen fixture supplies no legal discretionary call;
  - exact PR head passed all six current gates listed above.
- PR #284 remains active for independent non-Muse/current-boundary work. Its overlapping Muse test paths are superseded by current main and must not overwrite #292 semantics.

No generated historical Muse PASS count was transferred. The merged tests are current regression assets; any qualification credit remains subject to the normal current receipt/impact-adjudication pipeline.

`MUSE_CODE_SALVAGE = COMPLETE`

`MUSE_SAFE_VALUE_INTEGRATED = YES`

`MUSE_REMAINING_INTEGRATION_READY = NO`

`MUSE_UNRESOLVED_UNKNOWN = NO`

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`

## Scope and source lock

This ledger closes the repository-wide Muse salvage question for Commander Simulator Next.

Audit base:
- Commander-Lab main: `3910040b3ca4eb276f8895fa4c9801af3550f123`
- main tree: `a28d98b29c84342056e5658f8f4423f927999108`
- dedicated salvage branch: `sol/muse-final-salvage-20260929`
- primary Muse donor: `donor/muse-xhigh-independent-20260928@b7b16ef858e2d88bbb2946710eb054afe1246b78`
- donor tree: `1b6320abc0024bd90c093f9e68ecf056b88c0d3f`
- donor/main convergence point: `c9277b90ed3835985dcd21824cfe1762b3f65dcd`
- broader active integration carrier observed during audit: PR #284, `sol/final-integration-salvage-20260928@a3ebf798d5734ae3bbbdb1fca2d621aca4a724c1`
- concurrent Space Bunny completion carrier: PR #289
- concurrent DeepSeek audit/Aftermath carrier: PR #287

Fresh Git wins after this source lock. This document is an integration ledger, not provider-selection evidence.

Disposition vocabulary:
- `ALREADY_CANONICAL`
- `SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION`
- `PORTED_TO_CURRENT_MAIN`
- `PORTED_TO_INTEGRATION_PR`
- `READY_FOR_LATER_CHERRY_PICK`
- `PROVENANCE_ONLY`
- `INVALID_DO_NOT_USE`
- `UNRECOVERABLE_LOCAL_ONLY`
- `REQUIRES_ACTIVE_OWNER_BEFORE_INTEGRATION`

## Complete Muse branch inventory

GitHub branch search for `muse` yields exactly six relevant branches.

| Branch | Head observed | Final disposition | Reason |
|---|---|---|---|
| `donor/muse-xhigh-independent-20260928` | `b7b16ef858e2d88bbb2946710eb054afe1246b78` | `PROVENANCE_ONLY + PARTIAL_PORT` | Immutable donor. PB-03 test assets are handled individually below; generated verdicts are not current credit. |
| `muse/ws48-forge-v1.0.5-heavy-support` | `895eca21a3f63a54e9173d0dc65f7d94e8b41818` | `INVALID_DO_NOT_USE` for production behavior driver; `PROVENANCE_ONLY` for design/test ideas | Old Forge v1.0.5 overlay. The behavior driver contains unscripted sorted-first option selection and is bound to obsolete provider/evidence architecture. |
| `muse/ws49-xmage-local-execution-readiness` | `ece12fde7b605eeafa0b0990623374551a8a3a8c` | `SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION` | Optional tree-pin idea adds no independent protection to an exact verified Git commit; static fallback-zero inventory is weaker than current runtime-negative/receipt/meta-qualification gates. |
| `project/opencode-muse-cross-repo-hardening-v2-20260910` | `ec68024593904b648fd03d2fb518bee94cfa4d3b` | `ALREADY_CANONICAL` | Exact branch head is an ancestor of current main. |
| `governance/space-bunny-max-muse-xhigh-successor-20260927` | `e75efbc73c4aa6148a39b4dbac29bad78a2103ca` | `ALREADY_CANONICAL / SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION` | Four ported blobs are byte-identical on main; the rest have later current versions with Space Bunny MAX default, Muse XHIGH-only and broader current Git authority. No old governance backport. |
| `ops/opencode-muse-primary-privacy-20260908` | `22e2a20fe2fab595f0bc01e40cf00dbdd4af856e` | `SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION`; stale execution policy `INVALID_DO_NOT_USE` | Its useful project-data/private-data boundary is already in current AGENTS policy. Its Muse HIGH-primary configuration and older Git restrictions contradict current direct authority. |

No additional Muse-named branch was found in the exhaustive branch search.

## Primary donor commit reconstruction

The donor's Muse-side ancestry was reconstructed through the non-main parent of both convergence merges. The resulting 12 Muse commits match the prior donor ledger.

| Commit | Subject | Final disposition |
|---|---|---|
| `81ada1e22d189a261e0c43de9d97cd16b540c643` | initialize Muse XHIGH completion campaign state | `PROVENANCE_ONLY` |
| `0f281841fab74dc0a5527fc09f8d840175aaf71f` | add Muse XHIGH completion contract | `PROVENANCE_ONLY` |
| `abb747a7adcab706b6e11fdbccd1e134dcf14594` | source-truth reconciliation / blocker graph / isolation | `SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION` |
| `04d3e5997f12f1154b4bbf08ac6e5c8f0021c2d8` | WSR22 current-boundary transplant | `SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION` |
| `022782ad380f9d5733596973360a2b6938ba0485` | transplant checkpoint | `PROVENANCE_ONLY` |
| `0a36e47e31f09f053c42ec5c076a6b49d6e7b981` | PB-03 Wave 1 + PB-10 + Tier-1 executions | mixed; see PB-10 and PB-03 sections |
| `c8cc9b399b94d3a9ba381350e4e8b7a22ab4b194` | PB-03 Wave 2a commander-zone characterizations | `PORTED_TO_INTEGRATION_PR` on #284 as characterization only; no automatic row credit |
| `164f166b23a87a1b5b11432cbb7844f32e16b3ba` | independent baseline + pristine Forge PB-09 run | `PROVENANCE_ONLY` |
| `cb185e580fa9af5df1a1ec9827f65a33d2a40209` | convergence merge to then-current main | `SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION` |
| `468360a8a60ae39838d9add957f1fb7cb89abfb3` | PB-03 Wave 2b/c + impact matrix | `PORTED_TO_INTEGRATION_PR` on #284, but behavior credit is gated by the discretion issue below |
| `d6d071cd92e037efdc68d6585d7aceb9331acf5e` | merge current main/#283 into Muse line | `SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION` because #283 is already canonical |
| `b7b16ef858e2d88bbb2946710eb054afe1246b78` | freeze Muse donor baseline | `PROVENANCE_ONLY` |

## PB-10 — false credit from source-text fixture mentions

Muse independently found that source-text fixture-name matching could award a row even when the named test asserted failure.

The canonical receipt implementation is stronger:
- current credit is derived from persisted, digest-verified positive execution receipts;
- a fixture-name mention gives zero credit;
- negative/rejection assertions give zero positive behavior credit;
- wrong candidate/head and construction-only assertions fail closed;
- `HIDDEN_02` has a regression for the exact false-promotion class.

Disposition:
`SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION`.

Do not port Muse's older assembler implementation.

## PB-03 dimension-admission test

Muse asset:
`engine-bridge/src/test/java/org/commanderlab/xmage/XmagePb03DimensionAdmissionTest.java`

Disposition:
`PORTED_TO_INTEGRATION_PR` and independently ported onto `sol/muse-final-salvage-20260929`.

Purpose:
- characterize the current native restoration seam;
- prove admitted dimensions and explicit fail-closed unsupported mechanisms;
- grant **zero FULL107 PASS by itself**.

The test does not convert construction/readback into behavior credit.

## PB-03 Tier-1 actual-behavior suite

Muse asset:
`XmagePb03Tier1RowsTest.java`

PR #284 has ported the exact donor file and added exact Surefire testcase receipt extraction.

Useful actual-runtime tests include:
- `MICRO_COMBAT`
- `MICRO_CONTINUOUS_EFFECTS`
- `MICRO_MODES`
- `MICRO_PREVENTION`
- `MICRO_REPLACEMENT`
- `MICRO_COSTS`
- `MICRO_STATE_BASED_ACTIONS`
- `MICRO_TRIGGERS`
- `WS05-MP-BLOCK-4`
- `WS05-MP-COMBAT-4`
- `WS05-MP-COMBAT-5`
- `WS05-CMD-ELIM-4` blocker characterization.

Coordinator adversarial review found one remaining evidence-integrity defect before behavior credit is admissible:
`payFromLabels()` sorts multiple allowed engine-offered mana actions/pool spends by `action_id` and submits element zero.

Affected positive tests include at least `MICRO_MODES`, `MICRO_PREVENTION` and `MICRO_TRIGGERS`; Tier-2 users share the helper.

This is deterministic but not semantically authorized. The fixture must either specify the source, the test must prove alternatives are outcome-equivalent, or the helper must require uniqueness/fail closed.

Disposition:
- test corpus: `PORTED_TO_INTEGRATION_PR` (#284)
- positive behavior credit: `REQUIRES_ACTIVE_OWNER_BEFORE_INTEGRATION` pending discretion hardening and fresh exact-head execution
- historical Muse PASS counts: `PROVENANCE_ONLY`

## PB-03 Tier-2 command-zone suite

Muse asset:
`XmagePb03Tier2CmdZoneTest.java`

Eight tests cover commander replacement to graveyard/exile/hand/library yes/no paths.

The current #284 receipt mapper deliberately does **not** auto-promote this class to positive fixture credit. Its existing single-frame/mode/target selections are guarded by exact-count/exact-match assertions. Mana payment still shares Tier-1's helper.

Disposition:
- characterization/regression asset: `PORTED_TO_INTEGRATION_PR` (#284)
- FULL107 behavior credit: not granted by this salvage; `REQUIRES_ACTIVE_OWNER_BEFORE_INTEGRATION` if later promoted

## PB-03 Tier-2 control / turn suite

Muse asset:
`XmagePb03Tier2ControlTurnTest.java`

Tests:
- `WS05-MP-TURN-5`: genuine Time Warp + Nexus of Fate execution, observed P3 then P2 extra-turn order;
- `MICRO_CONTROL`: genuine Control Magic cast/resolution creates owner/controller divergence.

Target selection is exact engine identity. Cleanup selection is used only after asserting all offered labels identical. Both tests currently use the shared mana helper and therefore inherit its unscripted-source-choice P1.

Disposition:
- code: `PORTED_TO_INTEGRATION_PR` (#284)
- current positive credit: `REQUIRES_ACTIVE_OWNER_BEFORE_INTEGRATION` pending mana-choice hardening and rerun

## PB-03 Tier-2 stack suite

Muse asset:
`XmagePb03Tier2StackTest.java`

High-value scenarios:
- priority response ordering;
- stack LIFO;
- Counterspell colored payment;
- spell-copy creation;
- stack-to-graveyard object identity;
- 3P/5P priority ring;
- Rules-RNG choice-point characterization.

The RNG test correctly stops at an unscripted Heads/Tails call and keeps the row BLOCKED.

Remaining defect:
`firstPoolSpend()` sorts multiple pool offers by `action_id` and submits element zero. The class is currently included in positive fixture receipt extraction on #284.

Disposition:
- code: `PORTED_TO_INTEGRATION_PR` (#284)
- positive behavior credit: `REQUIRES_ACTIVE_OWNER_BEFORE_INTEGRATION` pending hardening/rerun
- `MICRO_RULES_RANDOMNESS` characterization remains non-PASS

Coordinator gate comment: PR #284 issue comment `5879829287`.

## Muse-generated PB-03 result artifacts

Known output:
`qualification/pb03-wave1-20260928/*`

Historical Muse recomputation included PASS/BLOCKED/UNKNOWN counts.

Disposition:
`PROVENANCE_ONLY`.

Generated counts must never be copied into current qualification. Current PASS can arise only from exact current-head runtime receipt and the current credit verifier.

## Muse pristine-upstream Forge PB-09 experiment

Intended Rules Core:
`a37a865a53280dd8ad6fad3384d69611e8c5a42f`

Bridge/worktree:
`4753bb7c72ea60d653121e0bab989077b4009f9c`

Reported donor result:
PASS 1 / FAIL 4 / UNKNOWN 102 / BLOCKED 0.

The donor receipt itself records an operator-supplied `FORGE_ENGINE_SHA` while PB-05 was open.

Disposition:
`PROVENANCE_ONLY` / control evidence.

It does not replace the separately bound Commander-Lab Forge fork and earns no current provider-capability credit.

## Historical Muse WS48

Muse head:
`895eca21a3f63a54e9173d0dc65f7d94e8b41818`

Its Muse-specific delta consists of 13 behavior-driver/design/test files over the historical WS48 line.

Adversarial review found production/evidence-driver first-option behavior:
- `behavior_driver.py` sorts unscripted options by option id and chooses index zero;
- the fresh behavior runner contains a similar first payment selection in a negative-cause path;
- it targets the obsolete Forge v1.0.5 overlay/pin architecture.

Although the postcondition package contains useful negative-fallback concepts, current runtime/receipt/meta-qualification coverage is stronger and current Forge evidence uses the later fork + PR #5 dual identity.

Disposition:
- old behavior-driver/provider logic: `INVALID_DO_NOT_USE`
- design/test ideas and historical measurements: `PROVENANCE_ONLY`
- no code port

## Historical Muse WS49

Muse head:
`ece12fde7b605eeafa0b0990623374551a8a3a8c`

Muse-specific delta:
- local-execution-readiness handoff;
- static fallback-zero inventory probe;
- optional XMage source-tree check added to bootstrap.

The Git checkout path already verifies exact repository + exact commit; a Git commit cryptographically binds its tree. The Muse tree check does not cover the offline declared-snapshot path, so it does not close a distinct integrity gap there.

Current qualification additionally binds source/runtime identity through provider handshake, current-boundary source lock and verified receipts. Current negative-runtime/meta-qualification is stronger than a static reporter that always exits zero.

Disposition:
`SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION`.

No code port.

## Historical Muse governance successor

Head:
`e75efbc73c4aa6148a39b4dbac29bad78a2103ca`

Unique port set: 12 files.

Byte-identical on current main:
- `.github/workflows/opencode.yml`
- `.opencode/agents/foundry-reviewer.md`
- `docs/foundry-execution/GOVERNANCE_SUPERSESSION.md`
- `docs/foundry-execution/SAFE_AUTO_THREAT_MODEL_2026-09-10.md`

Other paths have later current versions. Current policy explicitly states:
- Space Bunny MAX = default/preferred executor;
- Muse = explicit XHIGH-only alternate;
- no active Muse HIGH lane;
- normal project-scoped owned-branch Git/GitHub authority;
- `safe_push` optional, not the sole publication authority.

Disposition:
`ALREADY_CANONICAL / SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION`.

No backport.

## Muse cross-repository hardening

Branch head:
`ec68024593904b648fd03d2fb518bee94cfa4d3b`

This head is an ancestor of current main.

Disposition:
`ALREADY_CANONICAL`.

## Historical Muse primary/privacy line

Head:
`22e2a20fe2fab595f0bc01e40cf00dbdd4af856e`

Its useful principle — project technical data may be used, unrelated private data/raw secrets must not be exposed — is already represented by current `AGENTS.md` privacy policy.

Its implementation additionally sets Muse HIGH as primary and adds old confirmation restrictions for routine Git operations. Those conflict with current direct user authority.

Disposition:
- privacy principle: `ALREADY_CANONICAL`
- old execution config / Muse-HIGH-primary policy: `INVALID_DO_NOT_USE`
- no port

## Historical local Muse R11

Reported local-only identity:
`7ad4e944...`

Reported workstream:
`cpl/r11-replay-paired-cumulative-integration-20260917`

No such commit is available on GitHub and no exact published blob lineage was found.

Disposition of the exact historical bytes:
`UNRECOVERABLE_LOCAL_ONLY`.

The intended functionality class has since been independently implemented on canonical lines, including:
- the WS213→WS232 successor chain with replay-tape v1, merged through commit `291dc89ae083b2f84eb826755439a49f8303bb3e`;
- RG-06 hidden-state semantic replay integration;
- cumulative L1→L7 residual runtime evidence on the current XMage lineage.

Therefore:
- exact R11 commit: not claimed integrated;
- intended paired/cumulative replay capability: `SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION`.

## Active-overlap adjudication

At audit time:
- PR #284 changed 38 files;
- Space Bunny PR #289 changed 22 files;
- overlap was exactly four paths:
  - `scripts/run_current_boundary_qualification.py`
  - `src/commander_lab/qualification/current_boundary/game_driver.py`
  - `tests/qualification/test_current_boundary_redaction_placeholders.py`
  - `tests/qualification/test_current_boundary_start2_observed_state.py`

The Muse Java PB-03 test files are outside that overlap.

Therefore:
- no wholesale #284 merge while active PB-03/current-boundary ownership is unresolved;
- safe Muse-only test material may be integrated separately;
- overlapping receipt/runner changes stay on #284 until Coordinator adjudication against the active completion line.

## Directly integrated by this salvage line

`XmagePb03DimensionAdmissionTest.java` is copied from the current-safe #284 port onto `sol/muse-final-salvage-20260929`.

This is intentionally a zero-credit seam characterization.

No generated Muse PASS count or old provider result is copied.

## Remaining integration-ready Muse value

None.

The remaining PB-03 Tier-1/Tier-2 runtime-test family was independently ported, discretion-hardened and merged through PR #292. The donor-era mana-choice P1 is resolved on current main.

PR #284 still contains overlapping historical/current variants of some of these test paths because it evolved into a broader completion carrier. Those Muse overlaps are not remaining value; current main is authoritative for the Muse test implementations.

## Historical Muse PR hygiene

Open-PR search after branch adjudication found one stale Muse-specific governance PR beyond the active salvage/integration carriers:

- PR #165 — `chore/foundry-dual-lane-execution@ebc318b3e90a92938e94da8067a78647ac7d304f`

A fresh path/semantic mapping proved its former unique documentation concepts now have stronger canonical successors under `docs/foundry-execution/*`, current `AGENTS.md`, the workstream state schema/validator and current `opencode.json`. Its Muse-HIGH-primary / approval-heavy routing is intentionally obsolete.

Coordinator supersession receipt: PR #165 comment `5880021755`.

PR #165 was closed without merge and without branch deletion.

Disposition:
`SUPERSEDED_BY_BETTER_CURRENT_IMPLEMENTATION`.

PR #284 is not hygiene-closed because it has evolved into an active broader completion/current-boundary carrier. Its Muse PB-03 test overlap is superseded by current main through PR #292. PR #291 and PR #292 are both merged canonical Muse-salvage carriers.

## Terminal status

`MUSE_INVENTORY_COMPLETE = YES`

`MUSE_UNIQUE_CODE_ADJUDICATED = YES`

`MUSE_SAFE_VALUE_INTEGRATED = YES` — DimensionAdmission and the hardened PB-03 Tier-1/Tier-2 runtime-test family are merged on current main through PRs #291 and #292.

`MUSE_REMAINING_INTEGRATION_READY = NO`

`MUSE_UNRESOLVED_UNKNOWN = NO`

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
