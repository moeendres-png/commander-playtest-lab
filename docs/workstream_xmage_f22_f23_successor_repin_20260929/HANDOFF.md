# XMage F-22/F-23 successor repin — handoff

## Source Lock
- Commander Lab audit base: `9e5788364dfc1d73af4912cc8a1e5e1b71b8353a`
- Audit-base tree: `875f9810230b6cea4bf3e7341dd34aa3bef2eecf`
- Prior live XMage pin: `f79e4168902e65063034b21be6f4585397fd43b3`
- Frozen Mage successor: `fcfde9dad30fa56e60d5f5bc40ddce6ecd68019c`
- Successor tree: `ba0d02bdf5e9d62361d68dbdfb7e729d46ce9aed`
- Mage final PR: #26 — MERGED
- Mage merge commit: `23b996a5048bf7b8e7e4a422f2f8ea4c4ba90f65`
- Lab integration PR: #360

## Work Completed
- F-22 Rules-Core remediation implemented with native replacement-protector authority.
- F-23 preserves turn/range snapshot semantics while using explicit current-opponent semantics for current-state gameplay consumers.
- Current-state conditions/counts/choices and audited card-local consumers migrated to current opponents.
- Vote and Myriad direct range consumers exclude departed players.
- Native actual-card/API regressions added in Mage.
- Mage final successor merged through PR #26.
- Lab live-pin consumers repinned to the frozen successor.
- Successor-specific runtime fingerprint uses `Game.getOpponentsInGame(UUID)`.
- Lab F-22 battle and F-23 Council's Judgment regressions enabled.
- New successor source lock, qualification guard, runtime-evidence record and impact adjudication established.
- Historical #337/WSR22 evidence remains historical rather than rewritten.
- PR #349/Mindslaver surfaces are outside this workstream.

## New Findings
- Globally redefining `Game.getOpponents()` was rejected as too broad because XMage intentionally retains turn/range snapshots for some engine semantics.
- The final design makes current-opponent semantics explicit at gameplay consumers.
- The prior APNAP-only runtime fingerprint could not distinguish later successor pins; `getOpponentsInGame(UUID)` closes that identity gap.
- The repository-native full Maven reactor has an independent `Mage.Verify` baseline failure. The exact parent `f79e4168` reproduces the exact same 15 Dragon Engine/Traxos subtype errors and 3 SLZ/FRA/MBC set errors under JDK 17.

## Tests / Evidence
### Mage final candidate
- Candidate: `fcfde9dad30fa56e60d5f5bc40ddce6ecd68019c`
- Tree: `ba0d02bdf5e9d62361d68dbdfb7e729d46ce9aed`
- Candidate verification run: `36622158243`
- Targeted job `109589982079`: **PASS**, 14 tests, 0 failures, 0 errors.
- Full job `109589982568`:
  - `Mage.Tests`: **PASS**, 7015 tests, 0 failures, 0 errors, 125 skipped.
  - `Mage.Verify`: **FAIL**, 2 tests, 18 hard data errors total.
- Exact-parent baseline run `36626307792`, job `109604066587`: **FAIL with the exact same 15 card + 3 set hard errors**.
- Adjudication: `F22_F23_RUNTIME_PASS_FULL_REACTOR_FAIL_NONATTRIBUTABLE_BASELINE`.
- Evidence: `CANDIDATE_RUNTIME_EVIDENCE.json`.

### Lab
Final exact-head qualification is required after evidence/hash sealing. Earlier green runs are supporting provenance only and are not credited to a later head.

## PASS / FAIL / UNKNOWN
- F-22 runtime behavior: **PASS — RUNTIME_VERIFIED**.
- F-23 runtime behavior: **PASS — RUNTIME_VERIFIED**.
- Mage.Tests regression: **PASS — 7015/0/0**.
- Full Maven reactor: **FAIL — NONATTRIBUTABLE_BASELINE**, not relabeled as PASS.
- Source lineage: **PASS**.
- Mage merge: **PASS / MERGED**.
- Lab final repin runtime: **PENDING final exact-head gates**.
- Production Provider: **NOT SELECTED**.
- Architecture Freeze: **NOT CLAIMED**.

## Remaining Blockers
1. Seal the final successor lock in both hash-manifest levels.
2. Run Lab #360 on the final exact head and repair only attributable failures.
3. Re-read current main drift and #349 overlap immediately before merge.
4. Merge the Lab repin with expected-head SHA protection.

## Outputs
- Mage PR #26 merged.
- Lab PR #360.
- Successor source lock and guard.
- Candidate runtime evidence.
- Impact adjudication.
- Enabled F-22/F-23 Lab behavior regressions.

## Dependencies Unblocked
The frozen Mage successor is merged and runtime-qualified for F-22/F-23. The Lab repin is the only remaining integration step.

## Exact Next Action
Reseal qualification hashes, qualify the exact final Lab head, re-read drift/non-overlap, mark #360 ready, and merge it with expected-head protection.
