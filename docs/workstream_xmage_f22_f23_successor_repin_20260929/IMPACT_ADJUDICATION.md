# XMage F-22/F-23 successor repin — impact adjudication

## Source Lock
- Commander Lab audit base: `main@9e5788364dfc1d73af4912cc8a1e5e1b71b8353a`
- Audit-base tree: `875f9810230b6cea4bf3e7341dd34aa3bef2eecf`
- Prior live XMage pin: `f79e4168902e65063034b21be6f4585397fd43b3`
- Frozen successor: `9cb5fb9e9558f980da81c85ca3fdc595161c8d34`
- Successor tree: `54aabe958a1d748c8fb509d66ee25b0900bc8e90`
- Mage final PR: #26
- Final candidate CI: Actions run `36621195990`

## Semantic delta

### F-22 — battle protector leaves
`GameImpl.checkStateBasedActions` treats a battle protector whose Player object exists but is no longer in the game as unsuitable and re-runs XMage's native protector selection.

Protector selection itself is hardened to current opponents, so a departed player cannot be re-selected. The Rules Core remains authoritative for the replacement choice.

### F-23 — current opponent vs turn-snapshot semantics
The final remediation **does not globally redefine** `Game.getOpponents(playerId)`.

XMage retains the existing turn-start/range-snapshot semantics behind ordinary/historical opponent enumeration where trigger/history semantics can require them. The final candidate adds/uses the explicit current-state primitive:

`Game.getOpponentsInGame(UUID)`

Gameplay consumers whose rules text means opponents currently in the game are migrated to that primitive or an equivalent explicit departed-player filter. This includes current-state counts, comparisons, conditions, random/current opponent choices, and the audited card-local consumers.

Direct range consumers that bypass `getOpponents` are corrected separately:
- `VoteHandler`: departed players do not vote.
- `MyriadAbility`: departed players do not receive a myriad token/choice.

This design preserves XMage's snapshot capability while removing departed players from gameplay decisions and values where the current opponent set is authoritative.

## Runtime coverage required
Fresh successor evidence is required for:
- F-22 Invasion of Zendikar protector replacement and continued attackability.
- F-23 explicit current-opponent API contract.
- Inspired Sphinx opponent counts at 4P/5P after departures.
- Beza opponent-life comparison.
- Myriad after an opponent leaves.
- Council's Judgment through the Lab decision surface.
- full Mage test reactor on the frozen successor.
- Lab bridge/full-game/provider regression on the exact repin.
- exact engine identity and source-lock guards.

## Historical evidence
The following remain historical and are not relabeled:
- `qualification/xmage-mp-candidate-repin-20260929/SUCCESSOR_SOURCE_LOCK.json`
- Mage PR #24 qualification.
- Lab #337 qualification.
- WSR22/current-boundary evidence bound to older pins.

No prior pin-wide PASS is silently transferred to the successor.

## Qualification boundary
Build/import/fingerprint evidence is not gameplay qualification. Runtime credit requires executed behavior tests on the exact frozen bytes recorded in the successor source lock.

No FULL107 row is promoted by this workstream.
Production Provider remains NOT SELECTED.
Architecture Freeze remains NOT CLAIMED.
