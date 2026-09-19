# Construction Report — 11 SOS Prepare identities on pinned xmage-1.4.61

Method: `CardRepository.instance.findCard(name, true)` after the importer's
verified initialization (DIRECTLY_VERIFIED, `PrepareConstructionGateTest`,
8/8 PASS), plus full-deck import and 4P game-start probes. DFC-lookup control
(`Delver of Secrets // Insectile Aberration` → `Delver of Secrets`, ISD 51)
proves the lookup shape is sound, so NULLs below are genuine absence.

## PASS (construction, pinned engine)

| oracle identity | resolution | import | 4P game start |
|---|---|---|---|
| Biblioplex Tomekeeper | `mage.cards.b.BiblioplexTomekeeper` (SOS 247), exact identity | PASS (98+2 shell, Commander validation green) | PASS (4P, 40 life, 7 cards, paused turn 1) |
| Skycoach Waypoint | `mage.cards.s.SkycoachWaypoint` (SOS 261), exact identity | PASS (98+2 shell, Commander validation green) | NOT_RUN (import-level only; same harness as Tomekeeper) |

## FAIL (construction — absent from pinned artifact, fail-closed)

All 9 Prepare-creature DFCs resolve NULL in both `A // B` and front-face form:

Blazing Firesinger // Seething Song, Cheerful Osteomancer // Raise Dead,
Dirgur Focusmage // Braingeyser, Goblin Glasswright // Craft with Pride,
Inspired Skypainter // Maestro's Gift, Sanar, Unfinished Genius // Wild Idea,
Spellbook Seeker // Careful Study, Studious First-Year // Rampant Growth,
Tam, Observant Sequencer // Deep Sight.

Import probe (`Blazing Firesinger` substituted into a 100-card shell) throws
`UNKNOWN_CARD_NAME` before Commander validation; `storedDeckCount` stays 0;
no game is created. Fail-closed behavior PASS.

## Adversarial guard

`Seething Song` resolves to `mage.cards.s.SeethingSong` (SLD 7051 standalone
reprint) — a DIFFERENT mechanical card from the unresolvable Prepare back
face. Name similarity confers zero behavior credit (asserted in-gate).

## Behavior consequence (110 rule-path cells)

- 2 enabler cards × 10 paths: construction PASS; in-game behavior NOT_RUN
  (no further engine driving in this workstream; Tomekeeper 4P start proves
  the setup path only).
- 9 creature cards × 10 paths (90 cells): NOT_RUN, blocked by construction
  absence (ENGINE_PIN_GAP). Zero behavior PASS claimed.
