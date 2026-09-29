# XMage F-22/F-23 successor repin — handoff

## Source Lock
Commander Lab `main@9e5788364dfc1d73af4912cc8a1e5e1b71b8353a`, tree `875f9810230b6cea4bf3e7341dd34aa3bef2eecf`.

XMage prior pin `f79e4168902e65063034b21be6f4585397fd43b3` -> candidate `4277b90b4ee49acd945e82335a9a04c4536f5340`, tree `d23b2bfc14a25a2aec2dec7eadd3994913cb4e31`, Mage PR #25.

## Work Completed
- Re-pinned all production-reachable Lab XMage identity consumers to the F-22/F-23 successor.
- Preserved historical pin epochs unchanged.
- Strengthened the runtime fingerprint with successor-only `Game.getOpponentsInGame(UUID)`.
- Enabled the Lab F-22 battle-protector regression.
- Enabled the Lab F-23 Council's Judgment departed-voter regression.
- Added a new machine-readable successor source lock and qualification guard.
- Added explicit impact adjudication for the generic F-23 Rules-Core change.

## New Findings
- The prior runtime fingerprint used only F-21 APNAP methods, so a stale `f79e4168` engine artifact could satisfy that structural fingerprint even after a later repin. The new successor-specific method closes that identity gap.
- F-23 is broader than the original three proven consumers because the default opponent-query contract is shared by counts, comparisons, membership and random-opponent consumers. Prior pin-wide qualification cannot be silently inherited.

## Changes
See Mage PR #25 for Rules-Core changes. Lab changes are pin identity, fingerprint, enabled actual-card regressions, successor lock/guards and evidence documentation. PR #349 surfaces are not edited.

## Tests / Evidence
Candidate verification workflow: Mage run `36616702280`, code head `4277b90b...`, CI-only workflow commit `9284d611...`. Status is recorded in the successor lock and must be updated from PENDING only from GitHub Actions readback.

Lab runtime/CI evidence is pending until the repin PR executes.

## PASS / FAIL / UNKNOWN
- CODE_DERIVED implementation: PASS.
- Source lineage: PASS — candidate is a direct descendant of `f79e4168`.
- Mage successor runtime: UNKNOWN pending exact-head candidate CI.
- Lab successor runtime: NOT_RUN until PR CI.
- External Rules validation: current official Wizards rules were checked for battle protector replacement and multiplayer leaving/range semantics.
- Production Provider: NOT SELECTED.
- Architecture Freeze: NOT CLAIMED.

## Remaining Blockers
1. Exact successor Mage targeted + full tests must finish successfully.
2. Exact Lab repin branch must pass bridge and repository qualification on the new engine.
3. Any CI failure must be diagnosed and repaired without weakening gates.

## Outputs
- Mage PR #25.
- Lab successor source lock.
- Successor repin guard.
- Impact adjudication.
- Enabled F-22/F-23 Lab behavior regressions.

## Dependencies Unblocked
A green Mage candidate run permits the Lab repin PR to claim runtime-verified engine evidence and proceed through its own CI gates.

## Exact Next Action
Read Mage run 36616702280. On success, update the source lock/evidence record to the exact result, seal its hashes, open the Lab repin PR, execute its CI, repair any attributable failures, and merge the Lab PR only after all required gates pass.
