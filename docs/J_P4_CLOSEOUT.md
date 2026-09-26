# Roadmap J-P4 Closeout

## Status

```text
J_P4_COMPLETE = pending_ci_and_recovery
J_P5_READY = pending_ci_and_recovery
```

## Canonical inputs

- source main: `01c03019fdbf835441514ddfee01f4ef5945fd5a`
- Korvold deck hash: `72c0cb6a804cfb97b5cb048ca5e2b261782037044f6360b98a6b7df51c79bf1f`
- RogShai deck hash: `3827c35995e280753c4e714e391b9baf0a34e2c019e9df519ea1db0260ff9932`
- opponent source: current structural profiles / current Drive opponent baseline; no empirical opponent-frequency weights invented
- P3 external engine: `NO_PROVIDER_READY / BLOCKED_WITH_REAL_EVIDENCE`; therefore no J-P4 external-rules-engine evidence is claimed.

## Baseline before tuning

- development corpus: 37 cases
- KorvoldPilot: 17/18 pass; mean class score 0.888889
- RogShaiPilot: 16/19 pass; mean class score 0.802632
- observed failures: low-value protection spend, low-threat counter spend, taxed Ishai overcommit under denial, Ishai exposure without reserve.

## Development

- `J_P4_DEVELOPMENT_GOLDENS_v1` SHA-256 `259cb59c70f86fe2117282c0751d218a9e9535b7121211117a1b504b81d49e78`
- final: 37/37 pass; mean class score 0.993243
- Korvold: 18/18 preferred, mean 1.000000
- RogShai: 19/19 contract-preserving, 18 preferred + 1 acceptable, mean 0.986842
- legacy targeted regression: 24/24 pass
- pilot integrations: 5/5 pass

## Untouched holdout

- ID: `J_P4_UNTOUCHED_HOLDOUT_v1`
- cases: 24
- SHA-256: `426e184e2dd3ade9245dd4756ee58e796841e1fa71237c3239b55ab16b0859f2`
- sealed before pilot tuning and stored in `docs/J_P4_HOLDOUT_SEAL.json`
- first and only intended evaluation: 24/24 pass
- mean action-class score: 0.989583
- bad actions: 0
- critical failures: 0
- Korvold holdout: 12/12, mean 1.000000
- RogShai holdout: 12/12, mean 0.979167
- holdout tuning violation: false
- no pilot/evaluator/corpus change is permitted after this evaluation in J-P4.

## Combined modeled quality

- Korvold: 30/30 contract-preserving, mean 1.000000
- RogShai: 31/31 contract-preserving, mean 0.983871
- threat / interaction relevant cases: 36/36, mean 0.986111
- rebuild-capacity cases: 13/13, mean 1.000000
- finish-window cases: 22/22, mean 0.977273
- 3-player: 9/9, mean 1.000000
- 4-player: 43/43, mean 0.988372
- 5-player: 9/9, mean 1.000000

## Sensitivity

962 development-scenario perturbations were evaluated across pod size, seat, all PilotStrength levels, commander denial, boardwipe risk, plausible unknown-opponent assumptions, and each current opponent structural profile as an unweighted scenario.

- Korvold: 468/468 preferred-or-acceptable; bad 0; critical 0
- RogShai: 494/494 preferred-or-acceptable; bad 0; critical 0
- every sensitivity level: contract-preserving rate 1.0

Political visibility is modeled only as a structural heuristic. No human political behavior is claimed.

## Remaining limits

- structural model quality is not empirical human play skill and not real win rate;
- no production external rules-engine provider is available from P3, so J-P4 has no new external-rules-engine validation;
- hidden information and opponent intent remain uncertainty heuristics, not opponent mind-reading;
- action-class goldens cover designed strategic situations, not the full MTG game-state space;
- sensitivity uses unweighted current opponent scenarios and deterministic transforms, not observed opponent frequencies;
- complete local pytest did not finish within the local execution window and is not claimed PASS; GitHub CI remains the full-suite gate.

## Scope

No canonical deck, inventory, purchase, allocation, or opponent mutation occurred. Kaervek remains frozen opponent-only. No P5 optimizer/search tuning was performed.
