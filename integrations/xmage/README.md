# XMage bridge integration point

## Current compatibility provider candidate

Repository:

`https://github.com/moeendres-png/mage.git`

Pinned commit:

`77d7646da6958fdf8125ee7c8f4aabd130d21d4c`

Branch used to produce that commit:

`playtest-lab-xmage-compatibility`

The pinned source passed the local full XMage Maven regression used for the
compatibility work. The current photo-verified RogShai build has 87/87 unique
card names registered in this XMage source.

These facts do not make XMage a production-ready Commander Playtest Lab
external provider.

## Evidence boundary

Current Lab bridge protocol: `2.0.0`.

A real provider-specific bridge must call actual XMage APIs and expose the
versioned JSONL protocol consumed by the Commander Playtest Lab.

It must identify as:

- `engine=xmage`
- `runtime_kind=external_rules_engine`

The process manager requires actual support for Commander/multiplayer,
deck import, legal-action queries, action submission and event logs before a
provider can become healthy.

`NO_PROVIDER_READY` remains current until the real bridge and semantic
acceptance gates pass.

Mock bridges, fixtures, Structural Simulation and Tactical Oracle cannot
substitute for real XMage execution.

## Historical provenance

The retained J-P3B XMage evidence workflows intentionally remain pinned to
the historical official XMage source used for those runs.

## B1 handshake bridge status

A Lab-owned development bridge now exists under:

`engine-bridge/`

B1 has been locally verified against the pinned XMage `1.4.61` runtime from
commit:

`77d7646da6958fdf8125ee7c8f4aabd130d21d4c`

The versioned JSONL process successfully supports:

- `START_ENGINE`
- `GET_PROVIDER_VERSION`
- `GET_CAPABILITIES`
- `SHUTDOWN_ENGINE`

The real XMage runtime is loaded by the Java bridge, but B1 deliberately
advertises all gameplay capabilities as unsupported.

The Commander Playtest Lab therefore reports this bridge as `DEGRADED`.

This is process/runtime integration evidence only. It is not Commander
gameplay evidence and does not satisfy the external rules-engine semantic
acceptance gate.

`NO_PROVIDER_READY` remains current.

Gameplay support begins with later bridge stages B2-B5.
