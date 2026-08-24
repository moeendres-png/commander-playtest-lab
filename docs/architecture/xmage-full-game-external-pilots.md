# XMage Full-Game External-Pilot Architecture

## Status

This document defines the dedicated full-game lane introduced after the B3/B4 compatibility bridge. It is deliberately separate from the older bounded JSONL bridge so that previously validated capability claims are not silently widened.

Operational scope is **exactly four-player Commander**. A run in this lane is **technical conformance evidence only** until a later, separately authorized decision contract promotes a validated configuration for official deck-comparison evidence.

## Authority split

```text
DECK_CANDIDATE_SET
        |
        v
objective hard validation
        |
        v
SIMULATION_CANDIDATE_QUEUE
        |
        v
scenario + 4 decks + 4 pilot bindings
        |
        +---------------------------+
        |                           |
        v                           v
XMage 1.4.61                    Commander Lab Our Pilots
rules authority                discretionary policy authority
(card/rules/stack/priority/    (mulligan, priority action,
combat/SBA/commander rules/    targets, choices, modes,
rules randomness)              trigger order, combat, etc.)
        |                           ^
        | typed legal choices      |
        +------ decision protocol--+
        |
        v
XMage mutation / next choice / Game Over
```

Structural Simulation and Tactical Oracle have **no decision authority** in this lane. XMage AI has **no decision authority**. There is no random/default discretionary fallback. Any unrecognized or invalid decision class fails closed.

## Runtime identity

- XMage engine version: `1.4.61`.
- Pinned XMage commit: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`.
- Engine protocol: `2.0.0` envelope.
- Full-game decision protocol: `xmage-external-decision-protocol-1.0.0`.
- Lane: `xmage_full_game_external_pilots`.
- Evidence class: `technical_conformance_only`.

The pinned XMage runtime exposes `mage.util.RandomUtil.setSeed(long)`. Because this RNG is process-global, the correctness contract is **one isolated JVM process per game**. A new process is launched for every run. No starting-state or scenario-state injection is used.

## Decision handoff

`XmageFullGamePlayer` follows XMage's human-player code path. It publishes only choices that XMage itself says are legal for the current callback, then blocks the engine thread in `XmageFullGameDecisionController` until the corresponding Commander Lab pilot returns a response.

The inventory currently covers:

- priority and playable activations/spells;
- targets and non-target object choices;
- distributed target amount choices;
- London mulligan keep/mulligan and bottom-card choices;
- yes/no use choices;
- string choices and piles;
- mana ability selection during payment;
- X, scalar amount and constrained multi-amount choices;
- replacement-effect selection;
- triggered-ability ordering;
- mode selection;
- attacker destination decisions;
- blocker assignment decisions.

Sideboarding, limited construction and drafting are outside Commander full-game scope and fail closed.

The machine-readable inventory is `artifacts/xmage-full-game/DECISION_CLASS_INVENTORY.json`.

## Pilot authority

`ExternalPilotDecisionPolicy` converts typed XMage options into `PilotActionView`/`PilotStateView` inputs. Every supported discretionary class ultimately calls a Commander Lab `BasePilot` decision/evaluation method. The adapter may translate XMage-specific structures into pilot action views, but it does not substitute Tactical, Structural, XMage-AI, random, or silent default decisions.

For stochastic pilot configurations, the pilot RNG is derived from:

`scenario seed + seat + monotonic decision offset + decision class`

It is intentionally independent of XMage's process-local game UUID and object UUIDs.

## Hidden-information boundary

`XmageFullGameStateRedactor.actorView` is the only state projection sent to the acting pilot.

The actor receives its own hand identities and mana pool. Opponents expose public battlefield/graveyard/command information plus public counts such as hand size and library size. Opponent hand arrays and library card/order arrays are absent. Face-down exile identities are not exported.

The bridge's exported audit transcript does not retain the actor-private `pilot_state`. It records semantic decision metadata, public/private state hashes, legal option types/labels and accepted option types/labels. This prevents post-game transcript artifacts from becoming a repository of every seat's private hand state.

## Commander rules

Commander legality and deck import are delegated to XMage's real `Commander` validator. During games, commander zone movement, commander tax, commander damage, state-based actions, stack resolution, replacement effects and all card mechanics remain XMage rules responsibilities. The lab does not duplicate these rules.

Not every XMage-owned rule datum is currently projected into `PilotStateView`. In particular, this lane does not claim a complete high-level Commander semantic telemetry API. Missing pilot telemetry reduces policy sophistication; it does not move rules authority away from XMage.

## Replay and reproducibility

A same-scenario/same-seed gate runs the full game in two fresh JVM processes. The semantic transcript hash excludes ephemeral engine object identities. The raw-result hash is also retained. `bit_exact_replay_validated` remains false unless raw identity equality is separately established; semantic replay equality is the required current conformance property.

Rules randomness is always XMage-owned. The Commander Lab pilot RNG is independent and deterministic from scenario identity for deterministic/stochastic policy replay.

## Batch, resume and idempotency

`XmageFullGameBatchRunner` content-addresses each case over the complete scenario, four deck inputs and four pilot bindings. A completed matching record is reused on resume. A failed record is retained and is not silently retried unless `retry_failed=True` is explicitly requested. Each newly executed case still receives a fresh XMage JVM.

Batch artifacts remain technical conformance evidence and explicitly carry:

- `consumed_gameplay_evidence = false`;
- `holdout_consumed = false`;
- `official_campaign_eligible = false`;
- `canonical_data_mutated = false`.

## Failure model

The Python boundary distinguishes configuration, protocol, conformance and engine failures. The Java decision controller separately fails closed for stale decisions, wrong actors, illegal option IDs, invalid numeric ranges, duplicate selections, timeouts and unsupported out-of-scope callbacks. Unknown future discretionary decision classes are not guessed.

## Evidence gates

The dedicated `XMage Full Game Conformance` workflow:

1. checks out the exact pinned XMage commit;
2. builds XMage and the Java bridge;
3. runs focused Python and Java contract tests;
4. generates versioned JSON schemas/invariant reports;
5. runs two fresh, seeded four-player Commander games to Game Over on a synthetic technical fixture;
6. verifies same-seed semantic replay;
7. verifies the hidden-information/export boundary;
8. writes checksums and uploads the technical evidence bundle.

The synthetic fixture is not an opponent observation, not a physical inventory claim and not deck-strength evidence.

## Non-goals and retained limitations

- No official deck-strength comparison is executed by this migration.
- No sealed holdout is opened or consumed.
- No canonical decklist, inventory quantity, allocation, purchase decision or opponent observation is changed.
- The lane does not claim exhaustive semantic telemetry for every Commander-specific public datum.
- Bit-exact replay is not preclaimed.
- Structural/Tactical results do not become external-rules evidence merely because this lane exists.
