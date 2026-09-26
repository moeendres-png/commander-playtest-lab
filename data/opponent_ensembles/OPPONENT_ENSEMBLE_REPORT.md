# Opponent Ensemble Report

Status: `opponent_ensembles_ready_with_limitations`

## Scope

- Three versioned ensembles.
- Four variants per ensemble.
- Twelve variants total.
- All local incomplete-list ensembles are unweighted because zero real games are available.
- The official Doom precon remains a separate non-synthetic reference variant.
- No assumed card is marked as confirmed.
- No historical or official opponent profile is overwritten.
- All matchup outputs are structural model estimates.

## Ensembles

### Cosmic Spider-Man uncertainty ensemble
- ID: `cosmic-spiderman-ensemble-v1`
- Commander: Cosmic Spider-Man
- Weight mode: `unweighted`
- Variants: 4
  - `cosmic-aggressive` — Aggressive; synthetic=true; confidence=0.25; known cards=0; assumed cards=0
  - `cosmic-midrange` — Midrange; synthetic=true; confidence=0.25; known cards=0; assumed cards=0
  - `cosmic-legends-value` — Legends Value; synthetic=true; confidence=0.25; known cards=0; assumed cards=0
  - `cosmic-control` — Control-oriented; synthetic=true; confidence=0.25; known cards=0; assumed cards=0

### Doom Prevails uncertainty ensemble
- ID: `doom-prevails-ensemble-v1`
- Commander: Doctor Doom
- Weight mode: `unweighted`
- Variants: 4
  - `doom-official-precon` — Official Precon; synthetic=false; confidence=0.25; known cards=0; assumed cards=0
  - `doom-artifact-upgrade` — Artifact Upgrade; synthetic=true; confidence=0.25; known cards=0; assumed cards=0
  - `doom-villain-typal` — Villain Typal; synthetic=true; confidence=0.25; known cards=0; assumed cards=0
  - `doom-recursion-control` — Recursion/Control; synthetic=true; confidence=0.25; known cards=0; assumed cards=0

### Morcant Elves uncertainty ensemble
- ID: `morcant-elves-ensemble-v1`
- Commander: High Perfect Morcant
- Weight mode: `unweighted`
- Variants: 4
  - `morcant-go-wide` — Go-wide; synthetic=true; confidence=0.25; known cards=0; assumed cards=0
  - `morcant-counters` — Counters/Proliferate; synthetic=true; confidence=0.25; known cards=0; assumed cards=0
  - `morcant-etb` — ETB Value; synthetic=true; confidence=0.25; known cards=0; assumed cards=0
  - `morcant-blight` — Blight Focus; synthetic=true; confidence=0.25; known cards=0; assumed cards=0

## Robustness interpretation

Every matchup output includes average, median, worst variant, best variant, spread, positive-variant share, and the most sensitive uncertainty dimension. A change that only improves one speculative variant is not robust.

## Truth boundaries

- Known cards and assumed cards are separate fields.
- Synthetic variants are explicitly labelled.
- Empty card fields do not imply an empty deck; they mean no card-level claim was made.
- No complete opponent decklist is generated.
- No automatic deck update is performed.
