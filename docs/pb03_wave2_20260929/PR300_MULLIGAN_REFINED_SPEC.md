# PR #300 mulligan bottoming — refined implementation spec (exact seam)

Supersedes the seam description in `PR300_MULLIGAN_BOTTOMING_GAP.md`. Two corrections from
reading the current source, both material:

## Correction 1 — `super.putCardsOnBottomOfLibrary` is not the hidden default

The earlier audit called the `super.` delegation in
`XmageBridgePlayer.putCardsOnBottomOfLibrary` (line 380) a hidden default selection. That is
wrong. The pinned engine funnels the bottom selection through
`choose(Outcome, Cards, TargetCard, Ability, Game)`, and `super.` merely orchestrates that
call. The delegation is only a problem if the callback it reaches falls back instead of
projecting. No change is needed in `putCardsOnBottomOfLibrary` itself.

## Correction 2 — the seam is one method, and it currently throws

`XmageBridgePlayer.choose(Outcome, Cards cards, TargetCard target, Ability source, Game game)`
(line 235) is where the engine asks for the London bottom. Its current body:

```
if (externalDecisionController != null && BOTTOM_SELECTION.get()) {
    throw new XmageGameManager.GameException(
            "UNSUPPORTED_COMPATIBILITY_DECISION: London bottom-card selection "
                    + "requires external decision control; no default card choice is permitted");
}
failIfExternallyControlled("choose(Cards,TargetCard)");
cards.getCards(game).stream().map(MageItem::getId)
        .forEach(cardId -> target.add(cardId, game));
return true;
```

So on the external path the method throws, which is the engine failure that surfaces as
`MULLIGAN_RESOLUTION_FAILED`. On the non-external path it selects **every** card — an old
compatibility default that must never become production-reachable.

`chooseDiscardBottom` (`return cardIds.subList(0, count)`, line 284) is a first-N helper, but
it is reached only from the `chooseTarget` bottom-message branch, which calls
`failIfExternallyControlled` first, so it throws on the external lane and is not the reachable
seam. It remains a latent first-N default worth removing or fencing.

## Exact engine-authoritative inputs available at the seam

| Input | Source |
|---|---|
| actor | `this` (`XmageBridgePlayer`), already identity-mapped by the controller |
| offered identities | `cards.getCards(game)` — the acting player's own cards, actor-scoped |
| engine-declared cardinality | `target.getMinNumberOfTargets()` / `getMaxNumberOfTargets()` |
| resolution effect | `target.add(cardId, game)` for exactly the selected ids, then `return true` |

No Lab-side rule is needed or permitted: the count and the candidate set both come from the
engine call.

## Minimal implementation

1. `ExternalDecisionController`: add a `mulligan_bottom` decision kind and a publication
   method taking the actor, the offered card list (stable id + display name), and the
   engine-declared min/max. Add `submitMulliganBottom(engineGameId, decisionId, actorId,
   List<String> selectedIds)` that validates, in order: live controller; decision kind is
   `mulligan_bottom`; `decisionId` matches; `actorId` matches; every selected id is a member
   of the offered set; the selection size is within the engine-declared min/max. Any failure
   throws, and nothing is submitted.
2. `XmageBridgePlayer.choose(Outcome, Cards, TargetCard, ...)`: replace the throw with
   publication when `externalDecisionController != null && BOTTOM_SELECTION.get()`, await the
   selection, `target.add` exactly those ids, return true. Remove the add-every-card default
   from any externally reachable path.
3. `XmageGameManager`: expose the bottoming decision through the existing `legalActions`
   snapshot and add `resolveMulliganBottom(...)` mirroring `resolveMulligan`, including
   `awaitDecisionAdvance` and the `engineFailure` check.
4. `JsonlBridge`: route the new request to that manager method using the existing
   decision-identity fields.
5. Lab driver: answer the `mulligan_bottom` decision from the offered ids only; the selected
   ids enter the decision tape so they participate in replay data.
6. Tests: update `XmageGenericExternalMulliganTest`'s accepted-boundary test to assert genuine
   completion with the engine-declared count; add negatives for wrong cardinality,
   non-offered identity, and absence of any default.

## Why this run stopped before writing it

The gap is now exact at method granularity, including the two engine-declared inputs. But the
implementation spans the controller, the player callback, the manager, the bridge protocol,
the Python driver and the tests, and it must then be qualified on three cells. The remaining
execution budget in this run could not carry that end to end, and a partially applied change
across five Java files plus the driver would have left the bridge in a non-compiling or
unvalidated state on a surface that is currently green. Per the workstream rule, the checkpoint
is persisted instead, with the spec at implementation granularity so the next run writes code
rather than rediscovering the seam.

No source file was modified in this run. No test was rerun beyond the direct baseline already
recorded, because nothing changed.

`PROVIDER_SELECTION_READY = NO` · `PRODUCTION_PROVIDER = NOT SELECTED` · `ARCHITECTURE_FREEZE = NOT CLAIMED`
