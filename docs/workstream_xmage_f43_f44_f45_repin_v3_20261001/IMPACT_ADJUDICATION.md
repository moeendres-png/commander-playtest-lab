# XMage candidate repin v3 (F-44, F-43, F-45): impact adjudication

- **Change:** the live XMage pin moves from `9375f35ac7c9a540ebcb8b262b8645b8c6b1b326` to `37e4df6c914f1e189e24f0ef59fa91734c922436` (tree `dac695ab`). Both are on the same candidate branch `claude/xmage-mp-candidate-20260929`. The prior pin is an ancestor.
- **Machine-readable lock:** `qualification/xmage-f43-f44-f45-repin-v3-20261001/SUCCESSOR_SOURCE_LOCK.json`.
- **Not:** Production Provider selection, Architecture Freeze or a denominator change.

## Target selection

The first v3 retarget on this PR bound `4e59e8b9`, the candidate after F-44 (mage#33) and F-43 (mage#29). The owner then gated the repin on F-45 (Lab #442, comment 5926695737 on #444): the candidate was still advancing.

- mage#35 (F-45, head `9dbda865`, parent exactly `4e59e8b9`) was merged into the candidate as `37e4df6c`. Its tree equals the donor head tree.
- The candidate head was re-read immediately before the lock: `37e4df6c`. No further candidate commits exist.
- `4e59e8b9` was never live. Its native and bridge evidence stays in the lock under `intermediate_candidate`, with its own identity. It is **not** relabelled as evidence for `37e4df6c`.

## Modified engine paths (the complete production delta over `9375f35a`)

| Finding | Engine path | Behaviour change |
|---|---|---|
| F-44 (mage#33) | `GameImpl.checkTriggered` | When the player ordering its triggered abilities can no longer respond after `chooseTriggeredAbility`, none of its abilities is put on the stack (CR 800.4a). |
| F-43 (mage#29) | `CombatGroup`: attacker, trample and blocker assignment; `DamageAsThoughNotBlocked` and divided-damage choose-use; bounded re-requests | After every player callback, the exact damage source is re-resolved by `MageObjectReference`, with the same controller still in the game. If it is gone, that source deals no cached damage, gets no retry and gets no default vector. |
| F-45 (mage#35) | `PlayerImpl.moveObjectToLibrary` | A spell being put into a library is looked up by the **moved object's** id, never by the effect source. A copy of a spell with no original card ceases to exist (CR 707.10a) and no card moves. |

**Without a leaving player, F-43 and F-44 are behaviour-identical (CODE_DERIVED):**
- F-44 only adds an abort on `!canRespond()`.
- F-43 re-resolves the same permanent and continues.

**F-45 changes behaviour only when the effect source and the moved spell differ.** At `9375f35a` and `4e59e8b9`, a library move of a spell copy could move the resolving source instead (Sudden Setback on a Bolt copy). When the moved spell is not a copy, the original-spell path is unchanged.

No card data or other engine file changed.

## Evidence matrix

| Evidence | Crosses a modified path? | Disposition |
|---|---|---|
| Native Mage suites | yes (combat damage, triggered abilities, library moves) | **SURVIVES_IMPACT_ADJUDICATION**: re-executed on exact `37e4df6c` (see the lock, `native_qualification`). |
| Mage.Verify card/set data | no | **UNCHANGED (baseline-attributed FAIL)**: the same 3 set and 15 card-data errors as at the untouched prior pin (run 36778620482). |
| Lab engine-bridge suite | yes (combat, leavers, trigger order, zone moves) | **SURVIVES**: re-executed against `37e4df6c` via an isolated Maven repository. |
| F-42 leaver unwind, `trigger_order` (bridge answers `null`) | yes (F-44 makes the engine agree) | **SURVIVES**: `XmageMultiplayerLeaverDecisionClassTest` is green. The bridge behaviour is unchanged. |
| F-42 follow-up 3, `multi_amount` fail-closed control (S-15) | yes (F-43) | **REQUALIFIED, promoted for combat damage only.** See `docs/multiplayer_findings/F-42_LEAVER_OWN_MAY_CHOICE.md`, follow-up 4. Green on the new pin. On `9375f35a` the same bridge code fails closed, and no damage is chosen for the departed player. |
| Lab evidence on spell copies moved to a library | yes (F-45) | **No Lab fixture asserts the defective outcome.** The engine regression is native (`SuddenSetbackCopyTest`, red at `4e59e8b9` + test only, green at `37e4df6c`). Ledger S-16 records the defect. |
| Engine identity (AF00-style) | yes | Re-established by `XmageProvider.ENGINE_COMMIT`, `JsonlBridgeTest` and the runtime fingerprint (F-43 `CombatGroup.revalidateCombatDamageSource`). F-44 and F-45 have no structural signature. |
| Intermediate candidate `4e59e8b9` evidence (CI run 36825505981; bridge 903 / 0 / 0 / 1) | — | **HISTORICAL_ONLY**: evidence about `4e59e8b9`, which was never live. |
| Current-boundary epoch `4cad91897216-a43e80d96595` (R-5 final, FULL107 / AF00–AF11) | bound to `9375f35a` | **HISTORICAL_ONLY**, unchanged. Credit at the new pin is **TARGETED_REQUALIFICATION_REQUIRED**: a PB-03 `workflow_dispatch` on the exact Lab `main` merge commit of this repin, persisted as a new epoch. Until then no FULL107 or AF credit is claimed for `37e4df6c`. |
| WSR22 FULL107 evidence (`b19596980f27`) | — | **HISTORICAL_ONLY**, unchanged. |
| v2 repin guard (`test_xmage_mp_candidate_repin_v2_20260930.py`) and the v1 and 2026-09-25 guards | — | **HISTORICAL_ONLY**: the current-pin checks skip as superseded, and the historical checks stay active. |
| Hidden information, Rules RNG, replay, decision handoff, event-log/lifecycle contracts | no (no change in observation, RNG, decision publication or lifecycle code) | **CARRIES_FORWARD as code contracts.** Runtime credit goes through the successor epoch, like every other current-boundary row. |
| CI workflows | build the pinned engine (cache keyed by the commit) | Run on this PR at the new pin: the **exact-head gate**. |

## F-45 evidence families

| Family | Disposition |
|---|---|
| Spell copies (copy semantics, CR 707.10) | **SURVIVES_IMPACT_ADJUDICATION** with a corrected engine: the only changed branch is a library move of a stack object. Copy creation, copy targeting and copy resolution are untouched. Native copy, counter and cascade classes ran green in the exact `37e4df6c` Mage.Tests run. |
| Zone changes from the stack to a library | **REQUALIFIED**: `SuddenSetbackCopyTest` covers both cases, a copy (ceases to exist) and an original (top of the owner's library). It is green on exact `37e4df6c`; the red control is mage#36. |
| Other move-to-library effects (from graveyard, hand or battlefield) | **SURVIVES**: the non-spell path of `moveObjectToLibrary` is unchanged. The Lab actual-card corpus rows that move a card from a graveyard to a library top ran green in the bridge suite on exact `37e4df6c`. |
| Stack resolution | **SURVIVES**: a resolving source is no longer moved by a third party's effect. No Lab fixture depends on the old outcome (searched: Sudden Setback, Memory Lapse, Remand, Hinder, Spell Crumple, Lapse of Certainty and `moveObjectToLibrary` in Lab tests). |
| Event/replay tapes | **SURVIVES**: the bridge's semantic replay twins (`XmageFullGameReplayTwinTest`) and every Lab replay test ran green on exact `37e4df6c`. Persisted tapes of earlier epochs stay HISTORICAL_ONLY; new tapes come from the successor epoch. |
| Current-boundary FULL107 / AF rows | **REQUIRES_REQUALIFICATION**, through the successor PB-03 epoch on the exact Lab `main` merge commit, like every other row at the new pin. |

## Lab main drift

The old #444 base was `953b231d`; the current `main` is `a79257c2` (#443).

- **Delta:** `current_boundary/game_driver.py` (a declared `ORDER_CHOICE` cost-order pilot policy) and its test.
- **Semantic interaction:** the driver is the PB-03 game driver. The XMage bridge emits no `ORDER_CHOICE` or `cost_order` frame (`git grep` over `engine-bridge/src/main`), so the new branch is unreachable for XMage and fails closed on malformed input.
- **Integration:** `main` is merged into this PR (`774f2cfc`). The exact-head PB-03 and the successor epoch therefore run with it.

**INVALIDATED:** none.

**UNKNOWN:** the current-boundary FULL107 standing at the new pin, until the successor epoch exists.
