# XMage candidate repin v3 (F-44, F-43): impact adjudication

- **Change:** the live XMage pin moves from `9375f35ac7c9a540ebcb8b262b8645b8c6b1b326` to `4e59e8b9087878816b37728055eb61757a2fbf07` (tree `97951fd7`). Both are on the same candidate branch `claude/xmage-mp-candidate-20260929`. The prior pin is an ancestor.
- **Machine-readable lock:** `qualification/xmage-f43-f44-repin-v3-20261001/SUCCESSOR_SOURCE_LOCK.json`.
- **Not:** Production Provider selection, Architecture Freeze or a denominator change.
- **Target selection:** the candidate branch head was `4e59e8b9` at lock time and is the merge of F-43 (mage#29) onto the F-44 merge `9367341d` (mage#33).
  - The isolated F-43 head `3fba145b` is not a pin candidate: it lacks F-44.
  - No further candidate commits exist.
  - R1 (mage#34, Sudden Setback on a copy) is on mage `master` only, not on the candidate. It is not part of this pin.

## Modified engine paths (the complete production delta over `9375f35a`)

| Finding | Engine path | Behaviour change |
|---|---|---|
| F-44 (mage#33) | `GameImpl.checkTriggered` | When the player ordering its triggered abilities can no longer respond after `chooseTriggeredAbility`, none of its abilities is put on the stack (CR 800.4a). |
| F-43 (mage#29) | `CombatGroup`: attacker, trample and blocker assignment; `DamageAsThoughNotBlocked` and divided-damage choose-use; bounded re-requests | After every player callback, the exact damage source is re-resolved by `MageObjectReference`, with the same controller still in the game. If it is gone, that source deals no cached damage, gets no retry and gets no default vector. |

**Without a leaving player, both changes are behaviour-identical (CODE_DERIVED):**
- F-44 only adds an abort on `!canRespond()`.
- F-43 re-resolves the same permanent and continues.

No card data or other engine file changed.

## Evidence matrix

| Evidence | Crosses a modified path? | Disposition |
|---|---|---|
| Native Mage suites | yes (combat damage, triggered abilities) | **SURVIVES_IMPACT_ADJUDICATION**: re-executed on exact `4e59e8b9` in CI run 36825505981. Mage.Tests: 7032 run, 0 failures, 0 errors, 125 skipped. |
| Mage.Verify card/set data | no | **UNCHANGED (baseline-attributed FAIL)**: the same 3 set and 15 card-data errors as at the untouched prior pin (run 36778620482). |
| Lab engine-bridge suite | yes (combat, leavers, trigger order) | **SURVIVES**: re-executed against `4e59e8b9` via an isolated Maven repository. 903 run, 0 failures, 1 skipped (superseded START-2). |
| F-42 leaver unwind, `trigger_order` (bridge answers `null`) | yes (F-44 makes the engine agree) | **SURVIVES**: `XmageMultiplayerLeaverDecisionClassTest` is green. The bridge behaviour is unchanged. |
| F-42 follow-up 3, `multi_amount` fail-closed control (S-15) | yes (F-43) | **REQUALIFIED → promoted for combat damage only.** See `docs/multiplayer_findings/F-42_LEAVER_OWN_MAY_CHOICE.md`, follow-up 4. Green on the new pin. On the prior pin the same bridge code fails closed, and no damage is chosen for the departed player. |
| Engine identity (AF00-style) | yes | Re-established by `XmageProvider.ENGINE_COMMIT`, `JsonlBridgeTest` and the runtime fingerprint (new: F-43 `CombatGroup.revalidateCombatDamageSource`). |
| Current-boundary epoch `4cad91897216-a43e80d96595` (R-5 final, FULL107 / AF00–AF11) | bound to `9375f35a` | **HISTORICAL_ONLY**, unchanged. Credit at the new pin is **TARGETED_REQUALIFICATION_REQUIRED**: a PB-03 `workflow_dispatch` on the exact Lab `main` merge commit of this repin, persisted as a new epoch. Until then no FULL107 or AF credit is claimed for `4e59e8b9`. |
| WSR22 FULL107 evidence (`b19596980f27`) | — | **HISTORICAL_ONLY**, unchanged. |
| v2 repin guard (`test_xmage_mp_candidate_repin_v2_20260930.py`) and the v1 and 2026-09-25 guards | — | **HISTORICAL_ONLY**: the current-pin checks skip as superseded, and the historical checks stay active. |
| Hidden information, Rules RNG, replay, decision handoff, event-log/lifecycle contracts | no (no change in observation, RNG, decision publication or lifecycle code) | **CARRIES_FORWARD as code contracts.** Runtime credit goes through the successor epoch, like every other current-boundary row. |
| CI workflows | build the pinned engine (cache keyed by the commit) | Run on this PR at the new pin: the **exact-head gate**. |

**INVALIDATED:** none. **UNKNOWN:** current-boundary FULL107 standing at the new pin, until the successor epoch exists.
