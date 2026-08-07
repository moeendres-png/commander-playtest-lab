# Phase 12.14 — Card and rules coverage

## Result

```text
execution_status=passed_with_limitations
completion_status=card_rules_coverage_ready_with_limitations
card_records=229
golden_scenarios=37
external_engine_verified=0
```

The latest canonical deck workbook was downloaded from Drive and imported read-only. It confirms 100 cards for Korvold, RogShai and Kaervek. The derived immutable snapshot stores 85, 82 and 76 unique Oracle names respectively.

## Coverage

- Korvold: 27 tactical-only, 58 structural-only unique names.
- RogShai: 30 tactical-only, 52 structural-only unique names.
- Kaervek: 4 tactical-only, 72 structural-only unique names.
- all records: 56 tactical-only and 173 structural-only.
- no card or scenario is marked as XMage- or Forge-verified.

The Golden Rules registry contains 37 required scenario families. Twenty-five map to the existing 73-case Tactical Oracle corpus; nine currently have structural evidence only; three opponent scenario families are unsupported because no concrete card/fixture data exists.

## Opponent boundary

The executable repository contains structural profiles and uncertainty ensembles, not complete current 100-card lists for Cosmic Spider-Man, Doom upgrades, Morcant Elves, Wakanda, Dance of the Elements or Blight Curse. Only known commanders and explicitly recorded cards were registered. Unknown slots remain unknown.

No canonical deck, inventory or allocation file was modified.
