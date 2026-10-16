# Meta-Qualification v1 — Final Handoff

## Source Lock

Integration base:
- repository: `moeendres-png/commander-playtest-lab`
- main commit: `60fc3c8afbe5245ddc3a9f6262b86736e2a0a635`
- main tree: `0fe5be6d46949c74b37aba83169e38a7ecfe2068`

Historical post-#254 drift detector:
- `c5f9418e755a02ffec0e02c34b4a739baf10f5f0`
- tree `610f93d81e3b7154731d95472be6dcac05057eac`

The exact final PR head, gate run IDs, artifact digest, merge SHA and post-merge
`main` HEAD/TREE are recorded in PR #262 disposition metadata so this handoff
does not require a post-gate source mutation.

## Work Completed

- Implemented provider-neutral semantic mutation accounting over the real WS218 XMage replay tape.
- Implemented Legal Set, Decision, Rules RNG, Event, Observation, State and Terminal mutations.
- Added first-divergence correspondence checks for replay mutations.
- Added a live XMage hidden-information fault-injection oracle using a real pending decision and a real opponent-private card identity.
- Integrated the live hidden-information mutation into the meta-verification report only after the exact runtime detector passes.
- Added deterministic `PYTHONHASHSEED=0`, exact source/engine identity capture and digest-bound evidence artifacts.
- Bound the workstream to the current official Rules-authority receipt and current pre-Freeze contract.

## New Findings

- A green specialized workflow is insufficient unless its evidence is bound to the exact PR head rather than a synthetic merge ref.
- Mutation kill rate alone can hide unexecuted catalogue entries; kill rate and catalogue coverage must be separate.
- The first live hidden-information mutation implementation exposed a Java compile failure in every XMage-bound lane, demonstrating why the full triggered gate set must be required before promotion.
- The current Rules-authority freshness blocker was independently resolved by PR #260; the authoritative receipt now reports `CURRENT_OFFICIAL_SOURCE_DIRECTLY_VERIFIED`.

## Changes

Long-lived protocol:
- `qualification/protocol/meta_verification_v1/`

Implementation:
- `src/commander_lab/meta_qualification.py`
- `scripts/run_meta_verification.py`
- `.github/workflows/meta-qualification.yml`

Runtime oracle:
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameHiddenInformationTest.java`

Tests:
- `tests/qualification/test_meta_verification.py`

Workstream state:
- `docs/workstream_meta_qualification_20260927/`

## Tests / Evidence

Final admission requires one exact current-main-based PR head with:
- Meta Qualification PASS with 8 attempted / 8 killed / 0 survived / 0 NOT_RUN / catalogue coverage 1.0;
- CI PASS;
- Production Qualification PASS;
- Core Workflow Acceptance PASS;
- Windows Runtime Hygiene PASS;
- External XMage Integration PASS;
- XMage Real 4P Technical Smoke PASS;
- XMage Full Game Conformance PASS;
- H4 Docker Materialization PASS for the XMage lane.

Exact run IDs and artifact digest are intentionally recorded in PR #262 after the
gate wave completes.

## PASS / FAIL / UNKNOWN

At file creation time: `FINAL_VALIDATION_PENDING`.

No final PASS is claimed inside this source file before the exact-head gate set completes.

## Remaining Blockers

- Final exact-head gate wave.
- Merge disposition.
- Post-merge exact-main re-read and relevant push-gate confirmation.

## Outputs

- Reusable v1 meta-verification protocol and mutation catalogue.
- Deterministic machine-readable mutation report.
- Live hidden-information qualification oracle.
- Exact-head evidence artifact.

## Dependencies Unblocked

Once the final v1 gate set passes, the project may use this framework to add
production-near fault seams for SBA, Trigger, Replacement, Layers and Commander semantics
without rebuilding the meta-verification foundation.

## Exact Next Action

Construct the current-main-based PR head, run every required gate, repair any real failure,
merge PR #262 only on an all-green exact head, then re-read `main` HEAD/TREE.
