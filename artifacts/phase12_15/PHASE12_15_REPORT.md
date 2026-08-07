# Phase 12.15 — Synthetic opponent, pilot, politics and uncertainty model

## Result

```text
execution_status=passed_with_limitations
completion_status=synthetic_uncertainty_system_ready_with_limitations
validation_level=structural_only
```

Implemented 16 required pilot profiles, ten politics regimes and eleven explicit opponent uncertainty variants. Partially known opponents receive best-case, median and worst-case structural variants; fixed references remain separate. No assumed card is marked confirmed.

A deterministic policy tournament evaluates every pilot across all politics regimes, 3/4/5-player pods and all opponent variants. It includes scenario best-response ranking, adversarial worst-case scoring, quantile scoring and multiplicative-weights regret minimization. No hidden hand, exact future draw or empirical local weight is used.

The generated 5,280 scenario rows are structural utility samples, not simulated empirical win rates. This phase provides robust scenario coverage but not a solved multiplayer game or externally rules-validated self-play.
