# WS213 I01_AUTHORITY_ADJUDICATION — `I01_AUTHORITY_STATUS = ADJUDICATED_NO_GATE`

Question (from WS207): the sealed WS90 I01 fixture lists Pacifism (owner P1)
under controller P0 enchanting P0's Bear — apparently inconsistent with the
Rules expectation that the caster (P1) controls its Aura.

Evidence (current official Rules, Wizards 2026 CR PDFs/TXT fetched 2026-09-14/15):
- CR 110.2: a permanent's controller is by default the player under whose
  control it entered; 110.2a for put-onto-battlefield effects.
- CR 303.4e: "An Aura's controller is separate from the enchanted object's
  controller or the enchanted player; the two need not be the same." Split
  control is expressly legal and reachable (control-change effects), so the
  fixture state is NOT Rules-impossible.
- CR 303.4f/303.4g govern how Auras enter; nothing in the sealed objective
  asserts an entry history, only a board state plus a blink outcome.
- The sealed I01 assertions are controller-insensitive: Momentary Blink
  returns the Bear under its owner's control clean (counters cease on exile);
  Pacifism goes to its OWNER's graveyard (P1) by CR 400.3 regardless of
  controller; Blink goes to P0's graveyard.

Adjudication: no objective inconsistency exists between the fixture and its
intended Rules objective, so no correction is needed and none is made. The
sealed fixture is untouched. No AUTHORITY_GATE is raised. WS207's stored
predicate (Pacifism@P0) is preserved as-is for any successor. The I01 slot
itself remains UNKNOWN (Bear+Pacifism unassembled in the bounded 500-run;
not chased per scope).

Machine companion: `I01_AUTHORITY_ADJUDICATION.json`.
