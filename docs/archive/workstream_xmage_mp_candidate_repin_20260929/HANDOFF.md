# XMAGE MULTIPLAYER CANDIDATE INTEGRATION / REPIN HANDOFF

Claude Opus 5.5 (Claude Code), 2026-09-29. Candidate requalification under Coordinator authority.
`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## Source Lock
- **Old Mage pin:** `b19596980f2734496ea1896504253e1bdd2756dd` (tree `04c00f25`).
- **Integrated Mage head:** `f79e4168902e65063034b21be6f4585397fd43b3`, tree `18c3e8e7588627b22accc08a644729399d702ee3` (Mage PR #24).
  - Tested code: `5a827488` (tree `c19777af`).
  - The head differs from the tested code by the handoff document only.
- **Donor heads:**
  - #19 `6044132e` (F-18)
  - #20 `0962f0b5` (F-19)
  - #21 `9ec76cc6` (F-20)
  - #22 `0082ad29` (F-21 donor; not merged)
  - bounded F-21 commits `e5729e7d` and `5a827488`
- **Lab base:** main `b31f144b` (tree `a26e0c5c`).
- **New Lab pin commit:** `f79e4168…` in `config/rules_engines.json`.
- **Machine-readable:** `qualification/xmage-mp-candidate-repin-20260929/SUCCESSOR_SOURCE_LOCK.json`.

## Integration Decisions
- #19, #20 and #21 merged unchanged.
- #21 was verified against CR 726.4 and 726.2 verbatim.
- **#22 was not merged.** Its global `Game.getOpponents()` redefinition is rejected, and the documented starting-turn-order contract is kept. What replaces it:
  - the explicit primitives `Game.getPlayerIdsInApnapOrder()` / `getOpponentsInApnapOrder()`, walked with `PlayerList.getNext(game, false)` (reversed turn order, departed players skipped, range kept);
  - migration of only the order-sensitive consumers: `SacrificeAllEffect` (both paths), Grave Pact ("each other player") and six tempting-offer cards.
- #22's tests were carried over unchanged, and all pass.
- **WSR22 `source_lock.py` is not repinned.** It remains the historical identity, and a successor lock carries the live pin.

## Rules Fixes Included
- F-18: commander-zone SBA choices in APNAP order, applied together.
- F-19: Rhystic Study / Mystic Remora, the payer decides first.
- F-20: the initiative passes on when its holder leaves.
- F-21: simultaneous each-player / each-opponent choices in APNAP order (bounded design).

## Native Mage Evidence
72/72 targeted:
- F-18: 12;
- F-19: 6;
- F-20: 16;
- F-21: 38 (donor sacrifice 20, tempting offer 12, primitive 5, range of influence 1).

## Full Mage Regression
`mvn -o -pl Mage,Mage.Sets,Mage.Tests test`: **7001 run, 0 failures, 0 errors, 125 skipped** (the prior pin's 6929 / 125 plus the 72 new tests).

## Lab Tests Re-enabled
Each was verified against its obligation, red on the prior-pin artifacts and green on the candidate:

| Test | Finding |
|---|---|
| `XmageMultiplayerCommanderZoneChoiceTest.commanderZoneChoicesFollowApnapOrder` | F-18 |
| `XmageMultiplayerUnlessCostTest.thePayingPlayerDecidesBeforeTheController` | F-19 |
| `XmageMultiplayerInitiativeTest` (both 726.4 branches) | F-20 |
| `XmageMultiplayerEachOpponentChoiceTest.opponentsChooseInApnapOrder` (Liliana's Triumph → `SacrificeAllEffect`) | F-21 |
| `XmageMultiplayerTemptingOfferTest.opponentsAreOfferedInApnapOrder` | F-21 |
| new `XmageCandidateEngineFingerprintTest` | the runtime-loaded engine must carry the candidate API, so no stale-cache credit |

Also corrected:
- two companion tests that pinned pre-fix orders;
- `XmageStapleDecisionTest`'s Rhystic flow, which now follows the ruled payer-first order.

## Lab Runtime Evidence
- **Isolated Maven repository:** scratchpad `m2-xmage-candidate-f79e4168`. Everything is symlinked to `~/.m2` except a real `org/mage`, where the candidate `mage` / `mage-sets` 1.4.61 are installed (sha256 `e544eb16…` / `4c851528…`). The shared `~/.m2` is untouched.
- **Bridge suite:** `cd engine-bridge && mvn -o -Dmaven.repo.local=<isolated> -Dcheckstyle.skip=true test` → **538 run, 0 failures, 1 skipped** (superseded START-2).
- **Python suite:** 2187 passed, 8 skipped, 0 failed.
- **Successor guard:** `tests/qualification/test_xmage_mp_candidate_repin_20260929.py` 6/6.

## Impact Adjudication
See `IMPACT_ADJUDICATION.md`.

## Historical Evidence Invalidated
None. Nothing is rewritten.

## Historical Evidence Retained
- WSR22 current-boundary evidence and `source_lock.py`: historical, on `b19596980f27`.
- The 2026-09-25 repin guard: current-pin checks superseded, historical checks active.
- WS218 / WS232: already historical.

## PASS / FAIL / UNKNOWN
- **PASS:** native combined, the Lab bridge on the candidate, Python, and the successor guard.
- **UNKNOWN:**
  - FULL107 current-boundary standing at the new pin (a successor current-boundary run is required);
  - CI exact-head gates on the repin PR (pending at the time of writing).

## Remaining Blockers
- A successor current-boundary (FULL107) run on the new pin, whenever current-boundary credit is wanted. This is a separate workstream.
- PR #316's workflow uses the prior pin (owner notified).

## Dependencies Unblocked
- F-18 to F-21 are fixed in the live pin.
- The multiplayer campaign can build on APNAP-correct commander deaths, sacrifices, tempting offers and initiative.

## Exact Next Multiplayer Action
After this PR merges:
1. update trackers #317, #323, #327 and #328 with the candidate SHA, the Lab repin SHA and the enabled-regression result;
2. resume the campaign.

Candidates for the campaign:
- the roughly 70 card-local "each player sacrifices" loops that start from the controller (see donor #22's handoff), each migrated only with evidence;
- other simultaneous-choice families surfaced by 4P/5P actual-card probes.
