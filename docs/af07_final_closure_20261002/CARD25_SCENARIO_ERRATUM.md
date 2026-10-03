# CARD_25 (Basilisk Collar): causal-attachment scenario erratum

Status: **ADJUDICATED**. Recorded in `FULL107_SUCCESSOR_CONTRACT_v1_0_18.json` as an
`ACTUAL_CARD_SCENARIO_ERRATUM`. Every obligation key is untouched, so the obligation
digest equals the predecessor's. `PRODUCTION_PROVIDER = NOT_SELECTED`,
`ARCHITECTURE_FREEZE = NOT_CLAIMED`. CARD_25 lies outside the 107-row provider
denominator.

Adjudicated by the Claude campaign session as sole project executor and temporary
technical Coordinator (owner instruction, 2026-10-02). A newer owner or Coordinator
ruling supersedes it.

## The predecessor checkpoint

The checkpoint is P1's turn-1 declare-attackers step. P1 controls a 1/1 Soldier
**token**, already equipped with Basilisk Collar, and attacks P2. P2's 5/5 Colossal
Dreadmaw (a 6/6 with a -1/-1 counter) blocks.

The obligation:

- **Required events:** 1 combat damage to the blocker, 5 to the attacker, a lifelink
  gain of 1 for P1, and the deathtouch SBA.
- **Postconditions:** P1 at 21 life; both creatures dead.

## Why it cannot be constructed

- **The token.** A token exists only because an effect created it (CR 111.1, 111.4).
  A restoration vehicle loads cards, and placing a token would fabricate one.
- **The attachment.** Attachment is history the Rules Core must cause: an Equipment
  becomes attached through its equip ability, activated only as a sorcery
  (CR 301.5, 702.6a), or through an effect. Placing the Collar attached would
  fabricate that history.

The XMage restoration did not read `attached_to` at all, so a requested attachment
would have been silently dropped. It now fails closed with `UNSUPPORTED_ATTACHMENTS`.
The Java test `aRequestedAttachmentFailsClosedInsteadOfBeingDropped` covers this.

## The correction

- **Attacker.** Eager Cadet, a vanilla 1/1 Human Soldier creature card, takes the
  token's place.
- **Collar and mana.** The Collar starts unattached, with two Plains for Equip {2}.
- **Checkpoint.** It moves to P1's precombat main phase of the same turn. The
  restored permanents enter when the first turn begins (CR 103.6a), so the Cadet has
  been under P1's control continuously since the turn began (CR 302.6).
- **Decision script.** P1 activates Equip, targets the Cadet, and pays with the
  declared Plains. The predecessor's attack and block follow unchanged.

The events, the postconditions, the card binding and the players are unchanged.

## Why the plan cannot pass for the wrong reason

Eager Cadet has no abilities, so the plan's evidence can come only from the Collar
being attached:

- **The Dreadmaw's destruction.** The blocker is destroyed after taking exactly 1
  damage from the Cadet. It is a 5/5, so only deathtouch kills it.
- **The life gain.** P1 gains exactly 1 life (a `GAINED_LIFE` event) and ends at 21.
  Only lifelink gains that life.
- **The Cadet's death.** The Cadet takes 5 from the blocker and dies.
- **The Collar.** It stays on P1's battlefield.
