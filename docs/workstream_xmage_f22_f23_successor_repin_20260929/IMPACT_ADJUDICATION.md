# XMage F-22/F-23 successor repin — impact adjudication

## Source Lock
- Commander Lab base: `main@9e5788364dfc1d73af4912cc8a1e5e1b71b8353a`
- Base tree: `875f9810230b6cea4bf3e7341dd34aa3bef2eecf`
- Prior live XMage pin: `f79e4168902e65063034b21be6f4585397fd43b3`
- Successor candidate: `4277b90b4ee49acd945e82335a9a04c4536f5340`
- Successor tree: `d23b2bfc14a25a2aec2dec7eadd3994913cb4e31`
- Mage PR: #25

## Semantic delta

### F-22
`GameImpl.checkStateBasedActions` now treats a battle protector whose Player object exists but is no longer in the game as unsuitable. The existing engine-native `chooseProtector` path remains the only source of the replacement choice.

### F-23
The ordinary `Game.getOpponents(playerId)` contract now means opponents currently in the game. It delegates to the new explicit primitive `getOpponentsInGame(playerId)`.

The pre-existing overload `getOpponents(playerId, false)` remains available only for callers that deliberately require the turn-start range snapshot. This avoids deleting XMage's range-of-influence snapshot capability while removing it from ordinary opponent semantics.

Direct player-range consumers that bypass `getOpponents` are corrected separately:
- `VoteHandler`: departed players do not vote.
- `MyriadAbility`: departed players do not receive a myriad token/choice.

## Evidence impact

This is a Rules-Core semantic change. Prior pin-bound runtime evidence does **not** automatically transfer.

### Requires fresh runtime evidence
- F-22 actual-card battle behavior.
- F-23 ordinary opponent membership.
- F-23 Inspired Sphinx opponent count.
- F-23 Beza opponent comparison.
- F-23 Myriad.
- F-23 Council's Judgment voting through the Lab decision surface.
- Full Mage.Tests regression on the successor.
- Full Commander Lab XMage bridge regression on the successor.
- Current live-pin identity and source-lock guards.

### Prior evidence retained only as historical provenance
- `qualification/xmage-mp-candidate-repin-20260929/SUCCESSOR_SOURCE_LOCK.json`.
- Mage PR #24 native qualification.
- Lab #337 bridge and Python evidence.
- Any WSR22/current-boundary evidence bound to older pins.

Historical artifacts are not deleted or rewritten.

## Broad F-23 impact

Changing the default opponent membership is intentionally systemic. It reaches counts, comparisons, membership checks and random-opponent consumers that use ordinary `getOpponents(playerId)`. That is the desired Rules correction, but it prevents a narrow “only these cards changed” impact claim.

The retained explicit `getOpponents(playerId, false)` overload is the compatibility escape hatch for engine code that intentionally needs turn-start range membership. New gameplay/card code should not receive departed players merely because the range snapshot still contains them.

## Qualification boundary

A green build, import, source lock or engine fingerprint is not gameplay qualification. The successor can receive runtime credit only from executed behavior tests on the exact successor bytes.

No FULL107 row is promoted by this workstream. Production Provider remains NOT SELECTED. Architecture Freeze remains NOT CLAIMED.
