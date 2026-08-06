# Phase 12.4 – Archetype and Package Extraction

Status: `package_extraction_ready_with_limitations`

- Package version: `1.4.0`
- Branch: `feature/archetype-package-extraction`
- Versioned package records: **20**
- Unique package IDs: **19**
- Latest curated Korvold packages: **9**
- Latest curated RogShai packages: **10**
- Validated packages: **0**
- Machine-extracted packages passing the strict threshold: **0**

## Implemented capabilities

- Weighted multi-archetype profiles.
- Versioned package registry with core, support, optional, enabler, payoff and finisher roles.
- Package completeness, density, redundancy and failure-mode diagnostics.
- Dead support and payoff-without-enabler detection.
- Package version comparison.
- Package-aware structural card profiles and pilot scoring.
- Registry-backed package ablation and package-aware variant search.
- Package diagnostics in deck inspection and meta comparison.

## Machine extraction

Co-occurrence is grouped by exact format band and requires at least three same-format deck snapshots. The current Meta Knowledge Base has only one or two matching snapshots per band. Therefore no machine cluster passed. The raw clusters are rejected as undersampled and are not promoted to `machine_extracted`, `curated`, or `validated`.

## Curated package sets

### Korvold
- `korvold-free-sacrifice-outlets` — Korvold free and low-cost sacrifice outlets; status=`curated`; confidence=0.88
- `korvold-graveyard-protection` — Korvold graveyard risk management; status=`curated`; confidence=0.82
- `korvold-independent-finishers` — Korvold commander-independent finishers; status=`curated`; confidence=0.94
- `korvold-land-sacrifice-recursion` — Korvold land sacrifice and recursion; status=`curated`; confidence=0.94
- `korvold-mazirek-szarel-counters` — Korvold Mazirek/Szarel counter scaling; status=`curated`; confidence=0.91
- `korvold-mirkwood-table-damage` — Korvold Mirkwood Bats table damage; status=`curated`; confidence=0.90
- `korvold-token-sacrifice-material` — Korvold token and sacrifice material; status=`curated`; confidence=0.90
- `korvold-treasure-clue-food` — Korvold Treasure/Clue/Food engine; status=`curated`; confidence=0.86
- `korvold-wipe-rebuild` — Korvold boardwipe and rebuild; status=`curated`; confidence=0.93

### RogShai
- `rogshai-combat-draw` — RogShai combat draw; status=`curated`; confidence=0.95
- `rogshai-commander-damage` — RogShai commander damage; status=`curated`; confidence=0.94
- `rogshai-double-strike` — RogShai double-strike conversion; status=`curated`; confidence=0.92
- `rogshai-independent-draw` — RogShai independent draw; status=`curated`; confidence=0.89
- `rogshai-independent-spellslinger` — RogShai independent spellslinger engine; status=`curated`; confidence=0.91
- `rogshai-jeska-finish` — RogShai Jeska finish window; status=`curated`; confidence=0.94
- `rogshai-kediss-table-damage` — RogShai Kediss table damage; status=`curated`; confidence=0.95
- `rogshai-protection-counter` — RogShai protection and counter reserve; status=`curated`; confidence=0.96
- `rogshai-rograkh-resource` — RogShai Rograkh resource conversion; status=`curated`; confidence=0.84
- `rogshai-wipe-protection` — RogShai boardwipe plus protection; status=`curated`; confidence=0.90

## Structural ablation smoke

Two packages were removed in three paired structural games each. The smoke detected directional damage/resource changes, but the sample is too small for stable placement or power claims.

## Safety boundaries

- No package is automatically applied to a deck.
- No meta package is treated as physically owned.
- No Korvold/RogShai deck, inventory, or allocation file was changed.
- Structural outputs are not empirical win rates.
- Tactical Oracle remains separate from an external rules engine.
