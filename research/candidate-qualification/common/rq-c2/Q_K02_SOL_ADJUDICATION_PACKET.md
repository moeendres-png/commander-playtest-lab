# Q-K02 Sol Adjudication Packet — Clone across controllers / legend rule / dies

Scenario: `RQ-C1-K02` (Clone across controllers: no legend transit).
Status: `AUTHORITY_GATE_REQUIRED` for the same-controller variant only;
the cross-controller path is prepared as mechanically determined (Sol
promotes both).
Preparation recommendation: direct-authority confirmation for (1);
direct-authority reading with stated reasoning for (2) — Sol decides.

## 1. Exact scenario (from RQ-C1, unmutated)

- Battlefield: Ghalta, Stampede Tyrant (legendary 12/12) controlled by
  P1; Blood Artist controlled by P0; 4 Islands P0.
- Hand: P0 holds Clone. Stack empty. Turn 9, active player P0.
- Script: (seq 1) P0 casts Clone, entering as a copy of Ghalta
  ("You may have this creature enter as a copy..." — 614.1c
  replacement; copiable values per 707.2; only Ghalta and Artist are
  copyable creatures, Ghalta scripted);
  (seq 2) pass; no legend action across different controllers.
- RQ-C1 proposed terminal (cross-controller path): two Ghaltas coexist
  (P0 copy + P1 original); zero Blood Artist triggers (nothing died);
  Clone-copy ETB puts zero (P0 hand empty after casting Clone).
- Gated variant (NOT to execute before adjudication): same-controller
  Clone of own legend — does the legend-rule transit to graveyard count
  as dies for trigger purposes (Artist witness)?

## 2. Official citations (baseline CR effective 2026-08-07)

- **704.5j**: "If two or more legendary permanents with the same name
  are controlled by the same player, that player chooses one of them,
  and the rest are put into their owners' graveyards. This is called
  the 'legend rule.'" (An SBA, via 704.5/704.3.)
- **700.4**: "The term dies means 'is put into a graveyard from the
  battlefield.'" — a single sentence with NO legend-rule (or any other)
  exception in current text.
- **704.3**: SBAs performed simultaneously as one event; triggers wait
  until checks complete, then stack.
- **603.10 / 603.10a**: simultaneous-death look-back (leaves-the-
  battlefield abilities see same-event deaths; CR example: mass
  destruction fires a dies ability for co-dying permanents including
  itself).
- **603.3a**: trigger controlled by whoever controlled its source when
  it triggered (Artist's controller).
- **603.3d**: trigger targets chosen on stacking (Artist's "target
  player" chosen then).
- **614.1c / 707.2**: Clone enters as a copy with Ghalta's copiable
  values (hence legendary, hence the SBA interaction).

## 3. Point-by-point determination

| # | Required point (§10) | Determination |
|---|---|---|
| 1 | Legend-rule applicability | 704.5j fires only for 2+ same-name legendaries under ONE player's control |
| 2 | Same-controller requirement | Fails here (P0 copy vs P1 original): NO legend action — coexistence |
| 3 | SBA timing | Next 704.3 check after Clone's entry; nothing to perform on the cross-controller path |
| 4 | Objects going to graveyard | None on the cross-controller path |
| 5 | Dies-event semantics | No dies events (700.4 needs battlefield-to-graveyard movement) |
| 6 | LKI / source visibility | Artist is on the battlefield throughout; 603.10 normal check sees no matching event |
| 7 | Simultaneous state changes | N/A (no SBA action taken) |
| 8 | Trigger generation after SBA | None waiting; stack stays empty |
| 9 | Controller of resulting triggers | N/A (zero triggers) |
| 10 | Multiplayer relevance | None beyond 4P being the shell; question is controller-based, not seat-based |

## 4. The gated same-controller variant (prepared reading)

If one player controlled both Ghaltas, 704.5j would keep one and put
the other into its owner's graveyard. That movement is
battlefield-to-graveyard, which 700.4 defines as dies with no
exception. A Blood Artist on the battlefield would therefore trigger
exactly once for that transit (controller = Artist's controller;
target player chosen at stacking per 603.3d). No competing provision
was found: 603.10/603.10a confirm simultaneous-death visibility, and
the "chooses one to keep" choice (704.5j) does not negate the dies
event for the one put into the graveyard. (Commander-movement 903.9a
could follow for a commander going to graveyard, but it does not
negate the dies event either; K02's variant needs no such follow-up
for the Artist question.)

## 5. Competing interpretations considered

- (a) "Legend-rule transit is a game-rule movement, not dies." REJECTED
  as a reading: 700.4 defines dies purely by zone movement, with no
  cause-based exception in current text.
- (b) "The kept permanent's continuity negates the event." REJECTED:
  the put-into-graveyard permanent still moved zones; 700.4 is
  satisfied regardless of what is kept.
- No textual support for (a) or (b) was found; both are recorded so Sol
  can confirm their rejection rather than rediscover them.

## 6. Exact unresolved questions for Sol

> (1) Confirm cross-controller coexistence with zero triggers for
> promotion. (2) For the gated same-controller variant, confirm or
> correct the prepared reading: legend-rule transit to the graveyard
> counts as dies (700.4), so the Artist witness fires exactly once —
> or state the correct trigger accounting. Authorize or withhold the
> gated variant's execution accordingly.

## 7. Proposed test assertions

- Cross-controller path: `two Ghaltas coexist (P0 copy + P1 original)`;
  `zero Blood Artist triggers`; `Clone-copy ETB resolved with zero
  creatures put`.
- Same-controller variant (pending Sol answer): `exactly one dies
  event from the legend transit`; `exactly one Artist trigger by its
  controller with a legally chosen target`; `kept permanent remains
  per 704.5j choice`.
- Under rejected reading (a)/(b): `zero triggers on the variant` —
  recorded only to make the fork explicit, NOT recommended.

## 8. Provenance

CR text verified line-anchored in the August-7-2026 baseline file
retrieved 2026-09-10. No candidate behavior consulted or used as
tie-breaker. No second Rules engine used.
