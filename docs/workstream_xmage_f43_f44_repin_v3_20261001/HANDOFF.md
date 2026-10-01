# Handoff: XMage candidate repin v3 (F-44, F-43), 2026-10-01

## Source lock

| | Before | After |
|---|---|---|
| Lab `main` | `953b231d` (after #440) | the merge commit of this PR |
| XMage pin | `9375f35a` (tree `0fb7c2f9`) | `4e59e8b9087878816b37728055eb61757a2fbf07` (tree `97951fd7`), branch `claude/xmage-mp-candidate-20260929` |

**Ownership.** No active lane owned the repin:
- `origin/sol/xmage-f43-f44-repin-20261001` points at the then-current `main` with no commits;
- there was no open Lab PR and no state file claimed it.

The owner explicitly authorized this successor workstream.

## Work completed

**Lab repin:**
- `config/rules_engines.json` pin, archive and authority note.
- The 10 remaining literal consumers: 4 workflows, 3 Java files and 3 pin guards. G1 (#440) had already moved the Python consumers to the manifest.
- Successor lock v3 and guard `tests/qualification/test_xmage_f43_f44_repin_v3_20261001.py`.
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

| Evidence | Result | Class |
|---|---|---|
| Native Mage.Tests on exact `4e59e8b9`, CI run 36825505981 | 7032 run / 0 failures / 0 errors / 125 skipped | DIRECTLY_VERIFIED, remote exact head |
| F-43 head `3fba145b`, CI run 36823663089 | Mage.Tests SUCCESS | DIRECTLY_VERIFIED |
| F-43 red control on the merge tree without the `CombatGroup` change | 3/5 fail at 4P, 3/5 at 5P | local |
| Lab bridge suite against `4e59e8b9` (isolated Maven repository) | 903 / 0 / 0 / 1 skipped | DIRECTLY_VERIFIED |
| F-43 Lab guard on the new pin | 14/14 and 3/3 | DIRECTLY_VERIFIED |
| F-43 Lab guard, same code on the prior pin | fails closed | DIRECTLY_VERIFIED |
| Python suite | see the PR | — |
| Exact-head Lab CI | this PR | — |

## Remaining / next

1. Merge this PR on a green exact head.
2. Dispatch the PB-03 workflow on the exact `main` merge commit.
3. Persist the new current-boundary epoch, as #439 did.
4. Record its FULL107 and AF matrix for #255.

R1 (mage#34) is not in the candidate. Moving it into the candidate, and a later repin, is a separate step.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`
