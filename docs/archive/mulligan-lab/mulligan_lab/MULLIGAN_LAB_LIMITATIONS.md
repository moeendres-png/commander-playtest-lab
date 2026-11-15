# Mulligan Lab limitations — completion revision 1.10.1

- All keeps, rules and placement estimates are structural model outputs, not absolute instructions or empirical win rates.
- Follow-up samples now execute complete Structural Simulator games with the selected hand forced for the controlled player; the simulator remains a role-level abstraction, not a comprehensive rules engine.
- The current persisted release run used 500 cheap hand samples and four complete follow-up games per policy and deck. Larger runs are supported but were not claimed as executed.
- Generated rules were executed against primary, holdout, ensemble and multiple-pilot contexts, but no real-game holdout exists because zero real games are imported.
- Opponent ensembles remain unweighted in the absence of observations.
- No real XMage/Forge game was used.
