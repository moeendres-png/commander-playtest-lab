# F-27: controlled-turn decisions and hidden-information projection

- **Issue:** #348
- **Predecessor PR:** #349 at `cc566983e6d6ac577c245c13388dd82448219c97`
- **Successor audit base:** `main@72665dcea00d3c74b3272586a9b2794bb86fd93c`
- **Surface:** XMage full-game lane decision routing and principal-scoped observation.
- **Classification:** bridge defect; no Rules-Core defect demonstrated.
- **Engine pin:** unchanged.

## Current Rules predicate

The current Wizards Comprehensive Rules (effective 2026-08-07) place
"Controlling Another Player" in **CR 723**. In particular:

- **723.4:** in-game object information visible to the controlled player is also
  visible to the controller of that player.
- **723.5:** the controller makes the choices and decisions the controlled player
  is allowed or instructed to make.
- **723.8:** the controller still makes its own choices and decisions.

The predecessor documentation/code comments said CR 722; that numbering is stale
because CR 722 is now Preparation Cards.

## Adversarial review of PR #349

PR #349 correctly identified and repaired the core routing defect: the engine
already records the controlling principal through `getTurnControlledBy()`, but
the Lab always addressed the callback player's own principal.

The review found that routing alone was insufficient for CR 723.4. The
predecessor widened the controlled player's hand/mana projection and captured
look observations, but two existing private-information surfaces still used a
strict `viewer == principal` predicate:

1. restored face-down permanent identity;
2. grant-scoped library looks.

A controller could therefore receive the controlled player's legal decision
while still lacking information the controlled player was entitled to use for
that decision.

## Successor remediation

The successor uses one reusable current-state predicate:

> a viewer may read a principal's private in-game projection iff the viewer is
> that principal or XMage currently reports the viewer as that principal's turn
> controller.

That predicate is applied to:

- hand, mana pool and land-play state;
- restored face-down permanent identity;
- active grant-scoped library looks.

Look observations are slightly different: the controller at the instant of the
look is captured in the existing observation log, so information already seen
does not disappear merely because the turn-control relationship later ends.

The Rules Core remains authoritative for the control relationship, legal
options, costs, targets and outcomes. The bridge neither infers card names nor
creates a second legality model. A missing engine controller fails closed.

## Tests

- `XmageMultiplayerTurnControlTest`: actual Mindslaver + Lightning Bolt at 2P
  through 5P; controlled player is never addressed during the controlled turn,
  `acting_for_seat` is explicit, and normal routing resumes next turn.
- `XmageMultiplayerTurnControlPrivacyTest`: actual Mindslaver at 2P through 5P plus
  actual Grizzly Bears identities restored face down. It proves:
  - no pre-control leak;
  - controlled face-down identity is visible to the controller;
  - unrelated face-down identity and hand remain hidden;
  - the controlled player's active library-look grant is inherited only during
    its grant window;
  - looked-at observations are visible to the controller but not unrelated
    principals.

No provider selection, Architecture Freeze, or global qualification credit is
claimed by this bounded remediation.


## Review remediation on merge path

Three independent P1 findings were addressed before merge:

- exported `decision_requested` and `decision_accepted` transcript events now
  preserve `acting_for_seat`, so semantic audit records distinguish decisions
  made for different controlled principals;
- actor-state rows carry an explicit `private_state_visible` authorization bit
  from the redactor. Replay canonicalization includes private fields only for
  the actor or a row carrying that authorization, preserving the downstream
  smuggled-opponent-field defense while binding controlled-player hand, mana,
  land-play state, granted-library data, and face-down private identity. The
  public-state digest explicitly strips that private identity again;
- actual-card Mindslaver routing and privacy qualification now executes at every
  mandatory player count, 2P/3P/4P/5P.
