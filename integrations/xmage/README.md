# XMage bridge integration point

## Current B3 compatibility bridge

Repository:

`https://github.com/moeendres-png/mage.git`

Pinned commit:

`77d7646da6958fdf8125ee7c8f4aabd130d21d4c`

Current Lab bridge protocol:

`2.0.0`

The Lab-owned Java bridge lives under `engine-bridge/` and identifies the real provider as:

- `engine=xmage`
- `runtime_kind=external_rules_engine`

The pinned XMage source is the current compatibility source used by the B3 bridge. The current photo-verified RogShai runtime build has its card identities registered for the validated import path.

## Proven B3 external-rules-engine capabilities

The current bridge has real XMage execution evidence for the bounded B3 surface:

- versioned JSONL process lifecycle;
- real XMage runtime loading;
- real deck import;
- Commander game construction;
- Partner commander construction;
- 2–5 player multiplayer construction;
- real game start;
- bounded pause/resume lifecycle used by the compatibility bridge.

These capabilities are `external_rules_engine` evidence because the real XMage process is executed. They are not Structural Simulation or Tactical Oracle results.

## Explicitly unproven / unsupported production capabilities

B3 does **not** claim:

- legal-action enumeration;
- action submission;
- event-log production;
- deterministic seed control;
- replay;
- full stack/priority protocol visibility and control;
- target/mode/trigger-order control;
- externally controlled mulligans;
- a complete production game loop.

The current machine-readable capability truth is `config/rules_engines.json`.

`NO_PROVIDER_READY` therefore remains current. The existence of a real B3 bridge does not make XMage a production-ready Commander Playtest Lab provider.

Mock bridges, fixtures, Structural Simulation and Tactical Oracle cannot substitute for real XMage execution.

## Current CI regression path

`.github/workflows/external-engine-integration.yml` builds the exact pinned XMage source and the Lab bridge, then executes `scripts/run_external_b3_regression.py` against the real JSONL process.

That regression intentionally fails if the bridge loses the proven B3 capabilities or unexpectedly advertises B4/B5-style action-loop capabilities without a separately authorized implementation phase. Evidence artifacts include the exact lab/XMage identities and SHA-256 of the bridge artifact.

## Historical provenance

The J-P3 provider-selection documents and J-P3B/J-P3C spike workflows are historical provenance. In particular, `docs/J_P3_PROVIDER_DECISION.json` records the state before the production bridge existed and must not be rewritten to describe B3.

### Historical B1 milestone

B1 established the real process/runtime handshake and supported:

- `START_ENGINE`
- `GET_PROVIDER_VERSION`
- `GET_CAPABILITIES`
- `SHUTDOWN_ENGINE`

At that milestone gameplay capabilities were deliberately unsupported and the bridge was correctly reported as degraded. B2/B3 subsequently added the bounded deck-import and Commander/Partner multiplayer construction/start capabilities listed above.

Historical B1 evidence remains useful provenance, but it is not current provider status.
