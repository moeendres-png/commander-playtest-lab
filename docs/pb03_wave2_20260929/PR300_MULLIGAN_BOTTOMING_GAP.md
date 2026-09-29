# PR #300 mulligan bottoming — baseline evidence and exact projection gap

Run: `deepseek/pr300-mulligan-bottoming-20260929`, based on PR #300 head `71ebc911`
(branching, not merging or rewriting the foreign branch).

## Ownership verification

| Check | Result |
|---|---|
| PR #300 | OPEN, not draft, head `71ebc911c04a62c44e28d1644d4f0e4c0bae15ab`, unchanged since the previous run |
| PR #300 last commit | `test: accept native fail-closed London bottoming boundary` — the owner explicitly accepted the boundary |
| Surface taken over by a newer PR? | No. #315 (`claude/xmage-mp-voting`) and #316 (`sol/pb03-current-main-runtime-v2`) touch `XmageFullGameJsonlBridge` and multiplayer tests only; neither touches `game_driver.py`, `XmageGameManager`, `JsonlBridge`, `ExternalDecisionController` or the mulligan tests |
| Writer status | Active elsewhere (#315/#316), quiescent on this surface; last act declared the remaining gap out of its own scope |
| Action taken | No write to `sol/final-boundary-hardening-20260929`. Work is on my own branch rooted at that head, so integration stays the owner's/Coordinator's decision. No push, no merge, no rebase |

## Baseline evidence (runtime, executed)

Command: `mvn -o -B -ntp -Dcheckstyle.skip=true -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test -Dtest='XmageGenericExternalMulliganTest'` (workdir `engine-bridge`)
Result: `Tests run: 4, Failures: 0, Errors: 0, Skipped: 0`, BUILD SUCCESS.

That includes `selectedMulliganFailsClosedAtUnprojectedLondonBottoming`, which proves at
runtime that the engine offers the mulligan decision, the pilot selects mulligan, and the
keep that follows is rejected because the London bottoming cannot be resolved.

## Exact contract gap (code, with locations)

1. `ExternalDecisionController.submitMulligan` (line 378) rejects any non-empty
   `bottomCardIds` with
   `UNSUPPORTED_COMPATIBILITY_DECISION: London bottom-card selection is a separate engine
   decision and cannot be injected here`.
   So the mulligan decision deliberately carries only keep/mulligan; the bottoming is not
   part of it, and injecting it there would be the wrong seam anyway.
2. The engine's actual London-bottoming callback is
   `XmageBridgePlayer.putCardsOnBottomOfLibrary(cards, game, source, anyOrder)` (line 380).
   On the external-control path it does not publish a decision: it either throws the
   `UNSUPPORTED_COMPATIBILITY_DECISION` above (line 244) or delegates to
   `super.putCardsOnBottomOfLibrary(...)` (lines 387, 391).
   **The `super.` delegation is an engine-internal default selection — a forbidden
   fallback for a production-reachable discretionary decision.**

## Implementation-ready specification of the missing projection

Project the bottoming callback as its own external decision:

- **kind**: a new decision kind, e.g. `mulligan_bottom`, distinct from `mulligan`.
- **actor scope**: the decision belongs to the player XMage is asking; the offered
  identities are that player's own cards from the `cards` argument. Those are the actor's
  own hand cards, so exposing them leaks nothing across principals and stays
  principal-scoped.
- **engine-declared cardinality**: the required number is `cards.size()` as the engine
  supplies it. The Lab must not compute it, and must not derive it from player count.
- **selection**: the pilot returns exactly that many IDs, all of which must be members of
  the offered set; a wrong cardinality or a non-offered identity fails closed.
- **resolution**: perform the engine's own move for the selected cards, then let the
  engine continue; on the external path, remove the `super.` delegation entirely so no
  internal default can ever choose for the pilot.
- **fail closed** when the decision is malformed, when the contract cannot represent it,
  or when no decision is published.

Note: 2P requires bottoming one card after one mulligan and 4P Commander's first mulligan
is free, so the engine-declared cardinality differs per case. That difference must come
from the engine, which is precisely why the count may not be computed in the Lab.

## Qualification cells (verified, not inferred)

All three are `UNKNOWN` in **both** provider columns on the canonical boundary
(`qualification/final-current-boundary-20260927/`):

| Cell | XMage | Forge | Obligation |
|---|---|---|---|
| `PILOT_MULLIGAN` | UNKNOWN | UNKNOWN | 4P free first mulligan, `bottom_count:P1:0` |
| `WS05-CMD-MULL-2` | UNKNOWN | UNKNOWN | 2P one mulligan, not free, bottoms 1 |
| `WS05-CMD-MULL-4` | UNKNOWN | UNKNOWN | 4P one mulligan, free, bottoms 0 |

PR #300's surface is XMage (`engine-bridge`), so this projection unblocks the XMage column.
The Forge column needs the equivalent capability in the Forge bridge, which is a different
surface and is not owned here.

## Work not performed, and why

The projection itself was not implemented in this run. It requires the callback projection,
the resolution path, removal of the internal default, driver/Lab support, an update to
PR #300's accepted-boundary test, and then runtime qualification of the cells. Attempting
that with the remaining execution budget would have produced an unvalidated change to a
currently green surface, which is worse than this documented, implementation-ready gap.
Per the workstream rule, a transport that cannot represent the engine decision is
documented rather than improvised around.

No existing test was weakened. No source file was modified. No suite was rerun beyond the
directly relevant mulligan test class, because nothing else was affected.

`PROVIDER_SELECTION_READY = NO` · `PRODUCTION_PROVIDER = NOT SELECTED` · `ARCHITECTURE_FREEZE = NOT CLAIMED`
