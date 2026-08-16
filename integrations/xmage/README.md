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
