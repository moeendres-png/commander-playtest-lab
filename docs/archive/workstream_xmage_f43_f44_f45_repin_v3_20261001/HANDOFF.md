# Handoff: XMage candidate repin v3 (F-44, F-43, F-45), 2026-10-01

## Source lock

| | Before | After |
|---|---|---|
| Lab `main` | `77f99951` (after #443 and the parallel #446/#447) | the merge commit of this PR |
| XMage pin | `9375f35a` (tree `0fb7c2f9`) | `37e4df6c914f1e189e24f0ef59fa91734c922436` (tree `dac695ab`), branch `claude/xmage-mp-candidate-20260929` |
| Intermediate candidate (live on main only from #446 to #447) | — | `4e59e8b9` (tree `97951fd7`, F-44 + F-43 only), kept in the lock with its own evidence |

**Ownership.** No active lane owned the repin:
- `origin/sol/xmage-f43-f44-repin-20261001` points at the then-current `main` with no commits;
- there was no open Lab PR and no state file claimed it.

The owner explicitly authorized this successor workstream.

**Target identity.** The owner gated the repin on F-45 (comment 5926695737 on #444). The F-45 red/green controls were read back on mage#35:
- red control #36: 7034 run / 1 failure (`SuddenSetbackCopyTest`);
- fixed head `9dbda865`: 7034 / 0.

At the owner's request, mage#35 was then merged into the candidate as `37e4df6c` (expected head `9dbda865`; never to Mage `master`). The candidate head was re-read before the lock.

## Work completed

**Lab repin:**
- `config/rules_engines.json` pin, archive and authority note.
- The 10 remaining literal consumers: 4 workflows, 3 Java files and 3 pin guards.
- Successor lock v3 with three donors (F-44, F-43, F-45) and the `intermediate_candidate` record.
- Guard `tests/qualification/test_xmage_f43_f44_f45_repin_v3_20261001.py`, which also asserts that no consumer keeps the intermediate pin.
- The v2 guard's current-pin checks marked superseded.
- Ratchet allow-list updated.
- F-43 runtime fingerprint added.

**F-43 Lab integration:**
- `multi_amount` is now retired for a player who left, **only** for CombatGroup combat damage dialogues.
- The bridge answers `null`; the F-43 engine then deals no damage for the departed source, or asks the departed player again and the lane fails closed.
- Engine-bound qualification test: `XmageCombatDamageLeaverUnwindQualificationTest`.

**Not repinned:**
- the WSR22 `source_lock.py`;
- the v1 and v2 successor locks;
- the R-5 epoch `4cad91897216-a43e80d96595`.

## Tests / evidence

See `SUCCESSOR_SOURCE_LOCK.json` for exact numbers and run ids.

| Evidence | Class |
|---|---|
| Native Mage.Tests on exact `37e4df6c` (`native_qualification`) | DIRECTLY_VERIFIED, remote exact head |
| F-45 red control #36 and fixed head `9dbda865` | DIRECTLY_VERIFIED, remote |
| Lab bridge suite against `37e4df6c` (isolated Maven repository) | DIRECTLY_VERIFIED |
| F-43 Lab guard on the new pin; the same code fails closed on `9375f35a` | DIRECTLY_VERIFIED |
| Intermediate `4e59e8b9`: CI run 36825505981 (7032 / 0) and bridge suite 903 / 0 / 0 / 1 | HISTORICAL_ONLY |
| Exact-head Lab CI | this PR |

## Remaining / next

1. Merge this PR on a green exact head.
2. Dispatch the PB-03 workflow on the exact `main` merge commit.
3. Persist the new current-boundary epoch, as #439 did.
4. Record its FULL107 and AF matrix for #255 and #441.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`
