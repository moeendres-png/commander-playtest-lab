# XMAGE_ENGINE_CORE_REMEDIATION_REQUIRED

Pinned engine: cfc36f445f917f101fa2ed588770e043f53bc44c (1.4.61).
Bridge-only logic for the following would become a second Rules engine, so each
stays explicitly fail-closed until an engine-side boundary exists.

## 1. Concession

- Exact callback: `mage.players.Player.concede(Game)` — no blocking
  discretionary decision class exists in `XmageFullGameDecisionController`
  (17 decision classes, none `concede`); no `concede` route in
  `ExternalPilotDecisionPolicy._SUPPORTED_CLASSES`.
- Actual reproducer: any full-game session; invoking `player.concede(game)`
  now fails closed with `OUT_OF_SCOPE_DECISION` (WS204 explicit override;
  previously the inherited `PlayerImpl` default silently marked the actor
  lost via `Game.setConcedingPlayer` plus `lost()`).
- Why bridge-only is forbidden: a Lab-side concede would decide game-loss
  consequences, turn/authority transfer, and multiplayer continuation without
  an XMage-offered alternative set to select among.
- Smallest remediation: expose a blocking discretionary hook carrying
  actor plus confirm options through the decision controller as
  `decision_class=concede` (actor, prompt, Yes/No offered by the engine);
  until then `concede_supported=false` on both lanes and pilots cannot concede.

## 2. Combat damage assignment / blocker ordering

- Exact chain: `selectAttackers`/`selectBlockers` cover declaration only.
  No `assignDamage`/`orderBlockers`-class `Player` hook exists on the pinned
  `Player` interface (verified by `javap mage.players.Player`); damage
  distribution and blocker ordering resolve inside engine mechanics.
- Actual reproducer: any game reaching combat with multiple blockers; no
  native callback parks a damage-distribution decision in the controller.
- Why bridge-only is forbidden: Lab-side damage division would compute
  lethal assignment, deathtouch/trample interactions, and prevention
  ordering — core Rules semantics owned solely by XMage.
- Smallest remediation: expose blocking per-attacker damage-distribution and
  blocker-order choices (legal assignees plus min/max amounts) as controller
  decision classes; until then damage assignment stays engine-default and out
  of external-pilot conformance.

Non-entries (no core change needed): cast/land-or-spell choice, mana payment,
targets, X/numeric/multi-amount, modes, key-mode Choice (alternate-cost/modal),
piles, replacement/trigger ordering, search with D2 look window, attackers plus
defender-per-attacker, blockers declaration, Commander-movement-via-`chooseUse`,
mulligan — each already has a `Player` hook externalized through the
controller.
