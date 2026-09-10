# RQ-C2 Native Setup Boundary Review

WS51 rule (binding): RESTORE_PATH_REJECTED — no scenario may restore
into a decision-bearing step and pretend native lifecycle entry
occurred. Restore-as-construction strictly before the first
decision-bearing step is preserved; native progression thereafter is
required. RQ-C1 declares per-scenario boundaries in
`RQ_C1_NATIVE_SETUP_BOUNDARIES.json`: 35 NATURAL_GAME_START, 4
PRE_STEP_NATIVE_PROGRESSION (E01, E02, E03, J02), 1
PRE_DECISION_CONSTRUCTION (G03).

## Capability verdicts

- **35 NATURAL_GAME_START scenarios**: CAPABLE. Board established
  through native plays; every decision under test occurs natively after
  setup. No pre-answered decisions. (Includes both AUTHORITY_GATE
  scenarios G04 and K02: leaving/Clone-copy decisions occur natively.)
- **E01, E02, E03, J02 (PRE_STEP_NATIVE_PROGRESSION)**: CAPABLE.
  Starting the fixture at DECLARE_ATTACKERS (combat) or equivalent with
  attackers/blockers/attack-trigger to be declared natively does not
  pre-answer any decision: attacker/blocker/damage-division choices all
  occur after setup through the native turn-based actions (508.1,
  509.1, 510.1) and priority passes. E02's required reshape (drop the
  nonexistent ordering decision) does not change this verdict.
- **G03 (PRE_DECISION_CONSTRUCTION)**: CAPABLE-WITH-SOL-CONFIRMATION —
  no redesign required by RQ-C2, but Sol must approve the seeding
  locus. Analysis: the pre-seeded 12-damage commander ledger is
  pre-game HISTORY (construction strictly before the first
  decision-bearing step), not a mid-combat injection and not an
  already-executed discretionary transition of THIS game instance. The
  only discretionary Rules transitions in the scenario (attackers,
  blockers, pass-to-damage) all execute natively after setup, and the
  final 12 damage is dealt by the native combat sequence. This matches
  the WS51-allowed shape (construction before first decision + native
  progression thereafter). The open question is fixture-design
  legitimacy (may a qualification fixture assert prior-game history?),
  which is exactly Q-G03's Sol question — not a boundary violation.
  `SETUP_BOUNDARY_REDESIGN_REQUIRED` is NOT raised.

## Attention item G03 (per §17)

Confirmed: G03's neutral setup does NOT assume an already-executed
discretionary Rules transition within the game instance. The ledger
asserts a historical total, and every decision that produces the
scenario's terminal state is taken natively. Sol's decision is whether
that historical assertion is an acceptable fixture shape, not whether
the boundary mechanics work.

## No candidate-harness redesign

Per scope, no candidate-specific harness is designed or redesigned here.
The G02 10-mana abstraction ("mana base abstracted as payable") is a
documented fixture abstraction for the future execution harness to
fund, not a boundary defect.
