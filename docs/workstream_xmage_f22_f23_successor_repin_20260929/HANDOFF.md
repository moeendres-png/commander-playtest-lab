# XMage F-22/F-23 successor repin — handoff

## Source Lock
- Commander Lab audit base: `9e5788364dfc1d73af4912cc8a1e5e1b71b8353a`
- Audit-base tree: `875f9810230b6cea4bf3e7341dd34aa3bef2eecf`
- Prior live XMage pin: `f79e4168902e65063034b21be6f4585397fd43b3`
- Frozen Mage successor: `fcfde9dad30fa56e60d5f5bc40ddce6ecd68019c`
- Successor tree: `ba0d02bdf5e9d62361d68dbdfb7e729d46ce9aed`
- Mage final merge surface: PR #26
- Mage final verification run: `36622158243`
- Lab integration PR: #360

## Work Completed
- F-22 Rules-Core remediation implemented with native replacement-protector authority.
- F-23 redesigned to preserve snapshot semantics and make current-opponent semantics explicit.
- Current-state conditions/counts/choices and audited card-local consumers migrated to current opponents.
- Vote and Myriad direct range consumers exclude departed players.
- Native actual-card/API regressions added in Mage.
- Lab live-pin consumers repinned to the frozen successor.
- Successor-specific runtime fingerprint retained through `Game.getOpponentsInGame(UUID)`.
- Lab F-22 battle and F-23 Council's Judgment regressions enabled.
- New successor source lock, qualification guard, impact adjudication and hash sealing established.
- Historical #337/WSR22 evidence remains historical rather than rewritten.
- PR #349/Mindslaver surfaces are not part of this workstream.

## New Findings
- The earlier proposal to globally redefine `Game.getOpponents()` was too broad because XMage intentionally retains turn/range snapshots for some engine semantics.
- The final candidate therefore uses explicit current-opponent semantics at gameplay consumers instead.
- A structural APNAP-only fingerprint was insufficient for later repins; `getOpponentsInGame(UUID)` supplies a successor-specific semantic fingerprint.

## Tests / Evidence
- Mage final candidate: `fcfde9dad30fa56e60d5f5bc40ddce6ecd68019c`, tree `ba0d02bdf5e9d62361d68dbdfb7e729d46ce9aed`.
- CI-only child adds only the verification workflow.
- Final Mage verification authority: Actions run `36622158243`, required jobs `targeted` and `full-mage-tests`.
- Lab runtime qualification must be taken only from the final exact #360 head after all pin/evidence updates are sealed.

## PASS / FAIL / UNKNOWN
- CODE_DERIVED implementation: PASS.
- Source lineage: PASS — successor descends from `f79e4168902e65063034b21be6f4585397fd43b3`.
- Mage runtime: PENDING run `36622158243`.
- Lab runtime on final repin head: PENDING.
- Production Provider: NOT SELECTED.
- Architecture Freeze: NOT CLAIMED.

## Remaining Blockers
1. Final Mage run `36622158243` must complete with both required jobs successful.
2. Lab #360 must pass its complete final-head workflow set after final sealing.
3. Final main-drift and #349 overlap must be re-read immediately before merge.

## Outputs
- Mage PR #26 (frozen final successor).
- Lab PR #360.
- Successor source lock and guard.
- Impact adjudication.
- Enabled F-22/F-23 Lab behavior regressions.

## Exact Next Action
When Mage run `36622158243` is green, record exact runtime evidence, reseal qualification hashes, run #360 on the final exact head, repair only attributable failures, then merge Mage PR #26 followed by Lab PR #360 with expected-head SHA protection.
