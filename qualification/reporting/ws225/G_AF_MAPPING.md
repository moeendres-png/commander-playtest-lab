# WS225 G ↔ AF Mapping (narrative companion; machine truth is G_AF_MAPPING.json)

G00–G15 (production/full-game admission) and AF00–AF11 (Architecture Freeze
candidacy) are **not one-to-one**. The mapping below is reconstructed from the
live contracts (`FULL_RULES_REQUIREMENTS_CONTRACT_v1.json`,
`QUALIFICATION_OBLIGATION_CATALOG_v1.json`,
`architecture_freeze_gate_catalog_v1.json`) and the fixture manifest's
`requirement_ids`, which already record the intended pairs
(e.g. `PILOT_* → G05+G06+AF04`, `MICRO_* → G03+G05+AF06`).

## One-to-one pairs (shared fixture families)

- **G02 ↔ AF02** — player count. Same 4 lifecycle fixtures (`PLAYER_COUNT_*`).
- **G03 ↔ AF06** — general rules. Same 17 `MICRO_*` fixtures.
- **G04 ↔ AF07** — actual cards. Same 29 `CARD_*` fixtures (frozen denominator).
- **G07 ↔ AF05** — hidden information. Same 20 `HIDDEN_*` fixtures + sentinel.
- **G10 ↔ AF08** — Commander/multiplayer. Same 36 `WS05-*` rows; the 16
  preserved UNKNOWNs (APNAP, extra turns, CR800.4-control, zone
  exile/hand/library, damage thresholds, partner tax/damage) block both sides.

## Many-to-many (authority needs two halves)

- **G05 ↔ AF03 + AF04** — complete legal actions need authoritative options
  (AF03: Rules Core is sole authority) *and* complete offering with fail-closed
  gaps (AF04: boundary). Fixtures: 17 `PILOT_*` (+17 `MICRO_*` via G05).
- **G06 ↔ AF03 + AF04** — pilot authority: same pair, plus the 7 `NEGATIVE_*`
  fixtures proving each prohibited shortcut unsatisfying.
- **G08/G09 ↔ AF09** — RNG and replay share the 5 `RNG_*/REPLAY_*` rows;
  attribution (G08) and clean-process proof (G09/AF09) consume the same tapes.
  XMage rows are satisfied by sealed WS218 tape-lane evidence (explicit
  cross-branch pointers, tape-lane scope noted; campaign-scale replay stays
  with G14).

## Same concern, zero fixtures (structural gap made explicit, F-QUAL-01)

- **G11 ↔ AF10** (reliability/accounting) and **G12 ↔ AF11**
  (interop/topology): the manifest assigns **zero fixtures** to AF00, AF01,
  AF03, AF10, AF11. Their joins live in `EVIDENCE_JOIN_CONTRACT.json` direct
  bundles instead of pretending fixture coverage exists.
- **G00 ↔ AF00** — source-lock identity at lab vs candidate scope.

## Deliberately unmapped (AF ≠ admission boundary)

- **G01** (domain freshness), **G13** (admission rollup), **G14** (campaign),
  **G15** (holdout) have **no AF home**: freeze gates assume a frozen domain,
  while G01 guards freshness and G13–G15 *are* the admission/campaign layer.
  An all-AF-PASS candidate with G01 failing is still not admissible.
- **AF01** (RSP handshake runtime) has **no G home**: it is adjacent to G00
  identity but is a runtime event, not a lock record. AF01 is UNKNOWN for all
  candidates (no handshake runtime exists).

## Rejected alternative

A forced 1:1 table (e.g. inventing AF coverage for G01/G13–G15, or G coverage
for AF01) was inspected and rejected: it would assert relationships the
contracts do not contain. Unmapped-with-rationale is the honest record.
