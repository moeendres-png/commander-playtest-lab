# XMage bridge integration point

## Current B4-A compatibility bridge

Repository:

`https://github.com/moeendres-png/mage.git`

Pinned commit:

`77d7646da6958fdf8125ee7c8f4aabd130d21d4c`

Current Lab bridge protocol:

`2.0.0`

The Lab-owned Java bridge lives under `engine-bridge/` and identifies the real provider as:

- `engine=xmage`
- `runtime_kind=external_rules_engine`

The pinned XMage source is the current compatibility source. The current photo-verified RogShai runtime build has its card identities registered for the validated import path.

## Proven external-rules-engine capabilities

B0-B3 remain the validated lifecycle foundation. B4-A adds real read-only observation of the live pinned XMage game without widening the external-control claim.

Real XMage execution now proves the bounded surface:

- versioned JSONL process lifecycle;
- real XMage runtime loading;
- real deck import;
- Commander game construction;
- Partner commander construction;
- 2–5 player multiplayer construction;
- real game start through the bounded turn-1/upkeep handoff;
- `GET_GAME_STATE` against the running real XMage `Game`;
- real turn, phase and step observation;
- real active-player and priority-player observation;
- real player seats, life totals, poison counters and mana-pool observation;
- real library, hand, battlefield, graveyard, exile and command-zone observation;
- real stack visibility;
- a monotonic state-observation offset for ordered snapshots.

These capabilities are `external_rules_engine` evidence because the real pinned XMage process is executed. They are not Structural Simulation or Tactical Oracle results.

### RNG / reproducibility boundary

The current pinned XMage bridge does not expose validated deterministic seed control. `GameState.seed` and the external RNG counter are therefore returned as `null` for B4-A. The bridge must never synthesize a numeric sentinel such as `0` and present it as reproducibility evidence.

A state snapshot is observation evidence, not deterministic replay evidence.

## Explicitly unproven / unsupported production capabilities

B4-A does **not** claim:

- complete legal-action enumeration;
- action submission or external priority control;
- event-log production;
- deterministic seed control;
- replay;
- target/mode/trigger-order control;
- externally controlled mulligans;
- a complete multi-action / multi-turn production game loop;
- production-provider readiness.

The current machine-readable capability truth is `config/rules_engines.json`.

`NO_PROVIDER_READY` therefore remains current. Real state, priority and stack visibility do not make XMage a production-ready Commander Playtest Lab provider.

Mock bridges, fixtures, Structural Simulation and Tactical Oracle cannot substitute for real XMage execution.

## Current CI regression path

`.github/workflows/external-engine-integration.yml` builds the exact pinned XMage source and the Lab bridge. It then executes, in order:

1. `scripts/run_external_b3_regression.py` against the real JSONL process to protect the already-validated B3 lifecycle; and
2. `scripts/run_external_b4a_regression.py` against the real JSONL process to validate read-only live-state observation without consuming Confirmatory or Sealed Holdout evidence.

The B4-A regression fails if it sees an invented seed/RNG counter, wrong game identity, incorrect real opening state, a non-monotonic observation offset, or an unexpected widening of legal-action/event-log capability truth. Evidence artifacts bind the Lab head, exact XMage commit and bridge SHA-256.

## Next production-readiness boundary

The next slice is B4-B: a separate external decision handoff plus real `GET_LEGAL_ACTIONS`. It must preserve the B3 lifecycle regression path. Legal actions must come from the real running XMage state and remain fail-closed for unsupported choice classes. No action-submission capability may be promoted until a later real end-to-end B4-C regression proves it.

## Historical provenance

The J-P3 provider-selection documents and historical J-P3B/J-P3C spike material remain provenance. In particular, `docs/J_P3_PROVIDER_DECISION.json` records the state before the production bridge existed and must not be rewritten to describe B3 or B4-A.

### Historical B1 milestone

B1 established the real process/runtime handshake and supported:

- `START_ENGINE`
- `GET_PROVIDER_VERSION`
- `GET_CAPABILITIES`
- `SHUTDOWN_ENGINE`

At that milestone gameplay capabilities were deliberately unsupported and the bridge was correctly reported as degraded. B2/B3 subsequently added bounded deck-import and Commander/Partner multiplayer construction/start. B4-A adds only the read-only state-observation surface documented above.

Historical milestone evidence remains useful provenance, but it is not current provider status.
