# Final Handoff — XMage Successor Functional Integration (COMPLETE, PR-ready)

## Source Lock

- Repo `moeendres-png/commander-playtest-lab`, branch
  `cpl/xmage-successor-integration-20260919`, base `aebcfda3`.
- Worktree `/home/moeen/code/ws-successor-integration-20260919`.
- Donor (read-only) `fa4cd8d1`; engine pin `xmage-1.4.61` unchanged.

## Work Completed

- Ported the qualified XMage chain (2–5P orchestration + cardinality
  contract, replay-tape v1 package, numeric-boundary lanes, TD01/TD02/TD04
  hazard repairs, concession + Rules-seed authority): 31 prod files,
  35 test files, 14 fixtures, 2 workflow pin-default lines. Zero
  main-side overlap on all ported paths (verified vs MB 7725570b).
- Repaired 3 fail-befores on owned surfaces: Lions fixture (6 Java
  errors → 153/153), WS218/WS232 fixture inputs (canary + retention →
  green), workflow pin coherence (compat 4/4).
- Requalified on new base: bridge 153/153, python 756, retention 6/6,
  LIVE 2/3/4/5P dual-terminal gates PASS with semantic replay MATCH ×4
  (25 753 external decisions total, natural winners 1/1/3/2).
- Verified donor pin lineage on origin/mage (db134b97 descendant of
  cfc36f44, WS206/211/212) and authority-lock content hash (319e6921…).

## New Findings

- Main-line was exactly-4P-only (`len != 4`); now 2–5P capable with
  fail-closed invalid counts (re-proven live).
- 3-parallel JVM load causes card-DB bootstrap contention
  (infrastructure flake, solo rerun green) — batch runners must
  serialize engine starts or tolerate+retry this class.
- `raw_result_match=false` systematically (process-local IDs) while
  semantic MATCH holds — confirms the semantic-vs-raw replay split by
  design (bit-exact NOT claimed).

## Changes

- Commits `291dc89a` (prod), `009bf560` (tests+fixture); pending: workflow
  2-line edit, 14 fixtures, evidence docs (this package).
- MODIFY-nothing-else; donor worktrees untouched; no Forge/mage edits.

## Tests / Evidence

- See VALIDATION.md (DIRECTLY_VERIFIED throughout) + gate-evidence/*.json
  + PORT_LEDGER.md + IMPACT_ADJUDICATION.md.
- PASS: bridge 153/153 · python 756 · retention 6/6 · live gates 4/4.
- PARKED (cause recorded): 15 CI-wiring · 5 proven-pre-existing-env ·
  34 uncollectible-env · 4 governance (never ported).
- UNKNOWN/NOT_RUN: FULL107, 6P, dual-replay beyond gates, behavior credit.

## Remaining Blockers

1. Merge needs separate authorization (prepare PR from this branch; all
   publication gates re-run in CI).
2. CI smoke-lane wiring follow-up (main-CI owner): assert 2–5P smoke in
   `xmage-full-game-conformance.yml` (behavior already proven here).
3. hypothesis/openpyxl/fastapi container gaps (environment owner).

## Outputs

`docs/workstream_successor_integration_20260919/`: contract, state,
port ledger, impact adjudication, validation, seal, gate-evidence (5),
handoff, campaign checkpoint.

## Dependencies Unblocked

- Main-line (after merge) gains 2–5P conformance, replay-tape consumer,
  numeric lanes, hazard repairs — the base every future workstream builds.
- Prepare-behavior campaign can target 2–5P + replay on the integrated line.

## Exact Next Action

Commit pending files → verify clean tree + HEAD → hand Coordinator:
(a) PR authorization for this branch, (b) CI-lane follow-up scope,
(c) next campaign workstream under fresh ownership.
