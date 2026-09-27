# WSR25 Handoff — RG-07/RG-08 Current-Pin Lab Evidence Port (2026-09-27)

## Source Lock
- Lab base: `origin/main 8d2aacd530ea47d3ef39f4ab4f974f301da3cf24`, tree `b54ea3992bd2d58712c3e6d5e6daa63349802ab1`.
- XMage pin: `b19596980f2734496ea1896504253e1bdd2756dd` (`config/rules_engines.json`, `XmageProvider.ENGINE_COMMIT`).
- Bridge: `xmage-engine-bridge 0.1.0-SNAPSHOT`, xmage `1.4.61`, Lab protocol `2.0.0`,
  decision protocol `xmage-external-decision-protocol-1.0.0`.
- Camp provenance: `camp/rg-closure-20260925 @ ca8950e5` (immutable source, not merged).
- Meta-Qualification v1: MERGED (PR #262, Coordinator-verified — not investigated).

## Branch / Worktree
- Branch: `wsr25/xmage-rg07-rg08-current-pin-evidence-port-20260927` (isolated worktree
  `/home/moeen/code/wsr25-rg07-rg08-port`, from fresh `origin/main`).
- Untouched: `camp/rg-closure-20260925`, WSR22/WSR23 branches, Space Bunny PB-03 worktrees,
  WS-48 stash `9429face`, `forge-candidate-h4f`, Mage PRs #13-16, `xmage-ws49-baseline` history.

## Active Ownership Verification
- Space Bunny owns WSR23/WSR22-successor/PB-03/comparison assembly. This workstream edited
  ONLY: 2 new test files + 3 additive doc notes + WSR25 evidence packet.
- PB-03 surfaces (`run_current_boundary_qualification.py`, `full107.py`,
  `XmageNativeStateRestoration.java` production) NOT modified. Disjoint test-only extension used.

## RG-07 Source Provenance
- Mage: `sol/rg07-exact-n-target-offer-20260924`, ancestor of `b1959698` (Mage #14, DO NOT MERGE).
- Lab donor: camp `XmageFullGameHexOfferTest.java` (blob commit `22121f8c`), BYTE-COPIED.
- Vehicle: Hex exact-6, homogeneous Swamps, Grizzly Bears, seed 424242, explicit offered options only.

## RG-07 Current Runtime Result: PASS (6/6)
- `mvn -o test -Dtest=XmageFullGameHexOfferTest`: Tests run 6, Failures 0, Errors 0.
- Covers: exact-6 offered / absent-with-5 / 7-targets-cast-6-leaves-7th / duplicate-target
  distinctness / hexproof pool reduction / illegal-target resolution. No fabricated targets,
  no requested-option filtering, malformed input fail-closed, principal/decision identity exact.

## RG-08 Source Provenance
- Mage: `sol/rg08-replacement-regressions-20260924`, ancestor of `b1959698` (Mage #15, DO NOT MERGE).
- Lab donor: camp `XmageFullGameReplacementTest.java` (blob commit `684939fe`), REWRITTEN
  minimally (unique semantic keys for current-main `DUPLICATE_SEMANTIC_OBJECT` strictness).

## RG-08 Current Runtime Result: PASS (8/8)
- `mvn -o test -Dtest=XmageFullGameReplacementTest`: Tests run 8, Failures 0, Errors 0.
- Rules Core sole replacement authority; Lab only projects `replacement_effect`/`choose_use`
  and submits explicit pilot selection. Covers Dredge accept/decline/choice, Rest in Peace,
  Furnace+prevention ordering, commander-zone choice, and arrival-decline transport.

## Files Changed
- ADD `engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameHexOfferTest.java` (485 lines).
- ADD `engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameReplacementTest.java` (862 lines + key helper).
- ADD `docs/workstream_wsr25_rg07_rg08_port_20260927/` (TRANSPLANT_MANIFEST, HANDOFF, UNOWNED_* packet).
- APPEND 10 lines total: `docs/RETENTION_AND_LIFECYCLE_POLICY.md` (+2 lineage),
  `qualification/ws88-*/FINAL_REPORT.md` (+4), `qualification/ws90-*/FINAL_REPORT.md` (+4).

## Tests / Runtime Evidence
- Targeted: Hex 6/6 + Replacement 8/8 green (current pin, seed 424242).
- Regression (same run): `XmageCommanderDamageRestorationTest` 8/8,
  `XmageFull107ResidualRequalificationTest` 3/3, `XmageFullGameHiddenInformationTest` 2/2.
  Total 27/27, BUILD SUCCESS. Surefire reports under `engine-bridge/target/surefire-reports/`.
- Fail-before: Replacement 4/8 errored pre-fix with `DUPLICATE_SEMANTIC_OBJECT` (stricter
  current-main validation vs camp); fixed test-only, re-ran 8/8. No expected values altered.
- Privacy/replay: hidden-info suite green; redactor/transcript paths untouched (production
  SUPERSEDED_BY_CURRENT_MAIN, no new leak surface).

## Meta-Qualification Impact
- None: no detector-bound production surface changed (test-only + additive docs).
- Meta-Qual v1 (merged PR #262) NOT re-run; exact-head CI on PR will confirm.

## Stale Pointer Notes
- Landed: `docs/RETENTION_AND_LIFECYCLE_POLICY.md` WSR25 lineage addendum
  (`77d7646→cfc36f44→db134b97→b1959698`; docs/ is not hash-gated).
- Deferred (NOT landed): ws88/ws90 `FINAL_REPORT.md` successor notes drafted in
  `SUCCESSOR_NOTES_DEFERRED.md` but reverted — `test_ws17_qualification`
  requires `qualification/SHA256SUMS` to match every file under `qualification/`,
  and updating that sealed manifest is outside WSR25 authority. Coordinator /
  manifest owner applies note + manifest update together. No sealed body rewritten.

## Unowned Mage Patch Preservation
- Binary-safe patch + diffstat + SHA256 + base + status-before/after in
  `docs/workstream_wsr25_rg07_rg08_port_20260927/UNOWNED_MAGE_EDITS_*`.
- Forensic provenance ONLY, NO qualification credit.

## Unowned Mage Cleanup Result
- `xmage-ws49-baseline`: 7 paths restored to `0c1f455e`; `status --porcelain` EMPTY,
  `diff --stat` EMPTY. Worktree/branches/stashes/untracked untouched.
- `UNOWNED_MAGE_RESIDUE = PRESERVED_AS_PATCH_AND_REMOVED_FROM_WORKTREE`.

## Space Bunny Interaction / Non-Overlap
- No PB-03 implementation; consumption packet (§8 of adjudication) stands.
- Shared-surface use is disjoint test-only; ready-to-apply packet not needed (no conflict).
- Handoff enables Space Bunny to cite current-main RG-07/08 runtime credit in comparison.

## Remaining Mage/XMage Pre-Freeze Gaps
- PB-03 harness prefix + 11 genuinely-blocked MICRO rows (Space Bunny).
- Lab `ACTIVATED_ABILITY_PRESENT` over-refusal relaxation (post-selection Lab re-pin).
- B4-D action-submission 18 classes (WS204 line).

## Exact Next Action
- Coordinator/GitHub lane: review merge-ready PR, adjudicate drift, exact-head CI, merge when
  Space Bunny path-ownership disjoint. Then cite RG-07/08 PASS in provider comparison.
