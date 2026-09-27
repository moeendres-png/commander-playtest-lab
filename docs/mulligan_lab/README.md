# Mulligan Lab

The Mulligan Lab evaluates current Korvold and RogShai opening hands with exact hypergeometric category baselines, deterministic Monte Carlo sampling and controlled complete Structural Simulator follow-up games.

The London mulligan implementation draws seven, grants the first multiplayer mulligan free, redraws a complete seven and bottoms cards only for paid mulligans. Commanders remain outside the library. Results are conditioned on deck hash, opponent ensemble, seat, starting player, pod size, pilot profile and game plan.

Generated keep rules are non-absolute model candidates and are executed against primary, holdout, opponent-ensemble and multiple-pilot contexts before receiving `holdout_checked` status.
