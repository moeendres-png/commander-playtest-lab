# XMage bridge integration point

## Current bounded B4-D bridge

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

B0-B3 remain the validated lifecycle foundation. B4-A through B4-D extend that foundation with bounded external observation, decision/action control and bridge-audit lifecycle evidence. Every capability listed below is only considered `external_rules_engine` evidence after the real pinned XMage process passes the corresponding regression.

The bounded validated surface now includes:

- versioned JSONL process lifecycle;
- real XMage runtime loading;
- real deck import;
- Commander game construction;
- Partner commander construction;
- 2–5 player multiplayer construction;
- real game start;
- `GET_GAME_STATE` against the live XMage `Game`;
- real turn, phase and step observation;
- real active-player and priority-player observation;
- real player seats, life totals, poison counters and mana-pool observation;
- real library, hand, battlefield, graveyard, exile and command-zone observation;
- real stack visibility;
- monotonic state-observation offsets;
- an external decision boundary sourced from the real XMage priority flow;
- bounded `GET_LEGAL_ACTIONS` from the live XMage player's playable actions;
- stable decision/action identities and stale-decision rejection;
- bounded `PASS_PRIORITY` against the real XMage priority flow;
- bounded `SUBMIT_ACTION` for submission-ready actions without unsupported extra choices;
- a real Rograkh command-zone cast to the XMage stack in the B4-C regression;
- `EXPORT_EVENT_LOG` / compatibility `GET_EVENT_LOG` for the Lab-owned XMage bridge audit stream;
- monotonic per-game external audit-event sequencing;
- action/decision identity linkage in audit events;
- pre/post live-XMage state hashes for externally submitted actions;
- `SHUTDOWN_GAME` with real XMage end/cleanup and release of process-local deck handles;
- repeated-game lifecycle validation in one bridge process.

These capabilities are real pinned-XMage evidence. They are not Structural Simulation or Tactical Oracle results.

### Event-log evidence boundary

The B4-D event stream records the real XMage bridge lifecycle and the externally controlled action boundaries observed by the Lab. It is deliberately **not** claimed to be an exhaustive raw internal XMage `GameEvent` tap.

Structural events, Tactical Oracle events and synthetic events must not be relabeled as XMage events.

### RNG / reproducibility boundary

The current pinned XMage bridge does not expose validated deterministic seed control. `GameState.seed` and the external RNG counter are therefore returned as `null`. The bridge must never synthesize a numeric sentinel such as `0` and present it as reproducibility evidence.

State snapshots and the B4-D audit stream provide ordered diagnostic/audit evidence; they do not by themselves prove deterministic replay.

## Explicitly incomplete / unsupported production capabilities

The bounded B4-D bridge still does **not** claim complete production coverage for:

- full legal-action enumeration across every Commander decision class;
- full action submission across every choice-bearing action;
- target selection;
- mode selection;
- trigger ordering;
- replacement/optional-choice control;
- combat attacker/blocker choice coverage;
- externally controlled mulligans;
- deterministic seed control;
- replay;
- a fully validated complete multi-turn / game-end autonomous production loop;
- the project-wide interaction release gate;
- production-provider readiness.

Accordingly, machine-readable capability truth must remain fail-closed for the incomplete global action surfaces. `NO_PROVIDER_READY` remains current until the later provider release gate is actually satisfied.

The current machine-readable capability truth is `config/rules_engines.json`.

Mock bridges, fixtures, Structural Simulation and Tactical Oracle cannot substitute for real XMage execution.

## Current CI regression path

`.github/workflows/external-engine-integration.yml` builds the exact pinned XMage source and the Lab bridge. It then protects the incremental capability chain by executing the real JSONL process regressions for:

1. B3 lifecycle / deck import / Commander game start;
2. B4-A live state observation;
3. B4-B external decision handoff and bounded real legal-action enumeration;
4. B4-C bounded priority/action submission with stale identity protection;
5. B4-D external audit event log, action linkage, shutdown/cleanup and repeated-game lifecycle.

The B4-D regression also verifies that Confirmatory and Sealed Holdout evidence are not consumed and that no canonical MTG data is mutated.

Evidence artifacts bind the Lab head, exact XMage commit and bridge/runtime evidence for the executed workflow.

## Next production-readiness boundary

The next XMage work belongs to later B4-E/F slices and must extend the existing bridge rather than create a parallel integration. Priority areas are the actually still-missing choice and game-loop surfaces: target/mode/trigger control, combat decisions, externally controlled mulligans, broader Commander-specific interactions, complete multi-turn/game-end operation, honest determinism/replay boundaries, and finally the real interaction-suite provider release gate.

These later slices are an additional tactical evidence axis. They do not block Structural RogShai optimization once the Structural campaign inputs and decision workflow are independently current and reproducible.

## Historical provenance

The J-P3 provider-selection documents and historical J-P3B/J-P3C spike material remain provenance. In particular, `docs/J_P3_PROVIDER_DECISION.json` records the state before the production bridge existed and must not be rewritten to describe later B3/B4 milestones.

### Historical milestones

- B1 established the real process/runtime handshake (`START_ENGINE`, `GET_PROVIDER_VERSION`, `GET_CAPABILITIES`, `SHUTDOWN_ENGINE`).
- B2/B3 added bounded deck import and Commander/Partner multiplayer construction/start.
- B4-A added read-only live-state observation.
- B4-B added the external decision boundary and bounded legal-action enumeration.
- B4-C added bounded priority/action submission and stale identity protection.
- B4-D adds the external bridge audit event stream and per-game cleanup/repeated-game lifecycle.

Historical milestone evidence remains useful provenance, but it is not current provider status.
