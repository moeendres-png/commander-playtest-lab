# Q-G04 Sol Adjudication Packet — Control Magic + leaving player

Scenario: `RQ-C1-G04` (Control Magic controller leaves game).
Status: `AUTHORITY_GATE_REQUIRED` (execution blocked until Sol promotes).
Preparation recommendation: `SOL_REVIEW_RECOMMENDED_DIRECT_AUTHORITY`
(official authority mechanically determines every material point; Sol
still performs final promotion — Muse awards nothing).

## 1. Exact scenario (from RQ-C1, unmutated)

- Battlefield: Runeclaw Bear owned by P1, controlled by P0; Control
  Magic owned and controlled by P0 enchanting that Bear.
- Hands: all `HIDDEN:4`. Stack: empty. Life 40 all. Turn 8, active
  player P2, phase PRECOMBAT_MAIN.
- Script: (seq 1) P0 leaves the game — scripted loss/concession, always
  available per 104.3a ("A player can concede the game at any time. A
  player who concedes leaves the game immediately.");
  (seq 2) all principals pass through cleanup verification.
- RQ-C1 proposed terminal: P0 gone; P1/P2/P3 remain; Control Magic gone
  with P0; Bear on battlefield under P1 control.

## 2. Official citations (baseline CR effective 2026-08-07)

- **800.4a**: leaving-player cleanup — all objects owned by the leaving
  player leave the game; effects giving that player control of objects
  end; noncard stack objects they controlled cease; remaining controlled
  objects are exiled. "This is not a state-based action. It happens as
  soon as the player leaves the game." Priority hand-off if the leaver
  had priority.
- **800.4a official example (verbatim pattern match)**: "Alex casts Mind
  Control, an Aura that reads, 'You control enchanted creature,' on
  Bianca's Assault Griffin. If Alex leaves the game, so does Mind
  Control, and Assault Griffin reverts to Bianca's control." Mind
  Control's text is functionally identical to Control Magic's ("You
  control enchanted creature").
- **800.4b**: no control change toward a departed player.
- **800.4c**: orphaned control (effect ended, default controller gone)
  exiles the object — NOT triggered here (default controller P1
  remains).
- **800.4d**: departed players' triggers never stack — NOT triggered
  here (no triggers involved).
- **104.3a**: concession legality (script seq 1 needs no derived
  legality).
- **110.2 / 108.3**: Bear's owner (P1) is fixed; P1 is the default
  controller once the Aura's layer-2 effect ends.

## 3. Point-by-point determination

| # | Required point (§9) | Determination |
|---|---|---|
| 1 | Applicable 800-series provisions | 800.4a (+ 800.4b–d confirmed non-triggering) |
| 2 | Ownership/control cleanup sequence | Owned-by-P0 objects leave (Aura); control-grants to P0 end; both in one immediate (non-SBA) step |
| 3 | Objects owned by leaver | Control Magic (P0-owned) leaves the game with P0 |
| 4 | Control-changing effects | The Aura's control effect ends with the Aura leaving |
| 5 | Effects giving control | Same as 4; no other control effects present |
| 6 | Objects/cards not owned by leaver | Bear (P1-owned) stays; reverts to P1 control per the 800.4a example |
| 7 | Stack objects controlled by leaver | None (stack empty) |
| 8 | Continuous-effect implications | Layer-2 control change simply ends; no lingering effect |
| 9 | SBA timing after leave-game handling | Cleanup is immediate, not an SBA; normal 704.3 checks resume after (nothing pending) |
| 10 | Trigger implications | None: no zone-change trigger fires (Bear never changes zones; Aura leaving the game with its owner is not a battlefield-to-graveyard event for any witness present) |

## 4. Competing interpretations

NONE found in current authority. The CR's own example decides the
exact configuration (owner-leaves-with-Aura / owner-keeps-creature).
A conceivable misreading — "the Aura is exiled rather than leaving, or
control gaps to no one" — has no textual support (800.4a says owned
objects *leave the game*, and the example shows reversion with no gap).

## 5. Exact unresolved question for Sol

> Confirm that RQ-C1-G04's proposed terminal (Control Magic leaves the
> game with P0; Runeclaw Bear remains on the battlefield under P1 with
> no gap and no triggers) is the mechanically-required outcome of
> 800.4a, and promote it — or identify any residual interpretation this
> preparation missed.

## 6. Proposed test assertions under the recommended reading

- `P0 absent from game; P1/P2/P3 present.`
- `Control Magic in no zone (left game with owner P0).`
- `Bear on battlefield, controller P1, owner P1.`
- `Zero triggered abilities created for any principal.`
- (No alternative-interpretation assertions exist; no competing reading
  was found.)

## 7. Provenance

CR text verified line-anchored in the August-7-2026 baseline file
retrieved 2026-09-10 (see `RQ_C2_AUTHORITY_BASELINE.md`). No candidate
behavior consulted. No second Rules engine used.
