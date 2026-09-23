# Commander Expert System — Phase E provenance branch

This branch is an isolated provenance/reference branch for the Deck Lab Phase-E capability work performed on 2026-09-23.

It intentionally does **not** modify Commander Simulator production behavior. The Commander Expert System remains Drive-authoritative and the simulator repository is only used here to pin current software provenance and retain a noncanonical execution receipt.

## Baseline
- base commit: 81f688d3fd06c8edf53a289c5206dbaeef9d1fee
- package at baseline: 1.25.0
- expert system before Phase E: 1.1
- deckbuilding method: 1.1
- canonical mutation: false

## Phase-E local qualification
- Decision-quality cases: 98 / 98 PASS
- deliberate false-PASS traps: 47
- metamorphic/counterfactual pair IDs: 24
- cross-commander cases: 14
- Phase-E total checks: 110 / 110 PASS
- prior bootstrap regression: 29 / 29 PASS
- prior Phase-D semantic regression: 86 / 86 PASS
- prior integrated system regression: 200 / 200 PASS
- Wolfram exact reference probabilities:
  - 0.7728857217150797932243138571757548077679304016124638297859
  - 0.6711495665302388220185897361990996699875748394134004365922
  - 0.5756267799400872950417323602456594789539104949701991845323

## Scope
Phase E implements/qualifies:
Universal Castability + Mulligan, Per-Deck Context Graph v2, Decision Quality Evals, Package Ontology v2, Candidate Retrieval v2, exact portfolio allocation feasibility, Threat–Answer Coverage v2, Finish/Table-Closure analysis, external benchmark isolation, and targeted Oracle/Rulings freshness.

No canonical deck, inventory, lot, reservation, allocation, purchase, or opponent-data mutation is authorized by this branch.

Authoritative Phase-E artifacts and hashes are published through the Commander Expert System on Google Drive after readback verification.
