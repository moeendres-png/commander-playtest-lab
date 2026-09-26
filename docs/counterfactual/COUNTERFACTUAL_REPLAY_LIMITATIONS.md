# Counterfactual Replay limitations — completion revision 1.10.1

- Structural replays do not encode the full Magic rules state at every priority pass.
- Immediate card, mana, life, board, hand, reserve, threat and win-progress deltas are explicit but remain structural approximations.
- Same-realized-future mode controls the observed public suffix; it is not causal identification.
- Resampled futures are synthetic uncertainty samples.
- Public-information mode does not infer hidden hands or library order.
- Tactical Oracle covers only registered primitives and is not an external engine.
- No real XMage/Forge counterfactual was executed.
- Private real-game data is not exported outside project folders.
