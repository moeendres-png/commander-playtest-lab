# WS213 HIDDEN_INFORMATION — `HIDDEN_INFORMATION = PASS`

Principal scoping re-proven on the repinned engine (`XmageFullGameStateRedactor.actorView`
unchanged in behavior; all offers flow through it):

- Structural: only the actor entry carries `hand`/`mana_pool`; every other
  entry carries counts (`hand_count`, `library_count`) plus public zones
  (battlefield, graveyard, command, stack, commander_status). Grant-scoped
  `granted_library` populates only inside the D2 entitlement window.
- Unit: `XmageFullGameHiddenInformationTest` (live game, 60 decisions):
  non-actor `hand`/`mana_pool` absence asserted per row; test-oracle UUID
  scan (opponent hand+library card identities, reflection-only, never pilot
  input) asserted absent from the serialized actor view; grants observed
  only inside `choose_object` library frames.
- Runtime: per-decision verdicts in all 19 twin constructions + scans:
  8709 rows scanned, 0 violations (structural + oracle).
- Negatives: wrong-actor and unknown-action submissions rejected without
  advancing (every matrix run); cross-principal UUID oracle clean.

Machine companion: `HIDDEN_INFORMATION.json`.
