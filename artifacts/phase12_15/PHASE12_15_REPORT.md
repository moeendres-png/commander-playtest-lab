# Phase 12.15 – Opponent, pilot, politics and uncertainty robustness

Status: `passed_with_limitations`

Package version: `1.10.3`  

## Executed

- 16 requested pilot profiles mapped to the 11 utility dimensions actually consumed by the Structural Simulator.
- 10 politics regimes implemented as deterministic visible-state utility perturbations; no hidden hands, library order or future draws are exposed.
- Exact uncertainty boundaries preserved: Cosmic Spider-Man 4 confirmed / 96 unknown; Alen Morcant 53 confirmed / 47 unknown; Doom Prevails uses the exact official 100-card precon baseline plus a bounded unknown-upgrade role band.
- 3-, 4- and 5-player pods.
- Cheap exhaustive synthetic stress surface: 6240 rows. This is not self-play.
- Actual Structural Simulator policy tournament: 960 games across 60 scenario contexts, 960 completed, 0 aborted.
- Actual same-policy-all-seats Structural self-play: 96 games across 6 contexts, 96 completed, 0 aborted.
- Best-response ranking, adversarial worst-case evaluation and multiplicative-weights regret minimization executed.
- Common-random-number seeds preserved across competing policies within each structural context.

## Truth boundary

All outputs are `structural_model_estimates`. They are not empirical win rates and do not claim to predict human politics. No real-playtest calibration is used or required. Unknown opponent cards remain unknown.
