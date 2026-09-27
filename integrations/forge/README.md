# Forge bridge integration point

## Pin authority

The sole machine-readable authority for the current Forge pin is
`config/rules_engines.json` (`secondary_engine`: release, Rules-Core commit,
`source_archive`, license, plus `bridge_source` for the candidate
materialization source). This README must not restate commits and must not
be read as a second pin source. If this file and the manifest ever disagree,
the manifest wins and this file is stale.

Two identities are distinguished there and must never be conflated: the
Rules-Core authority the bridge reports, and the candidate bridge/
materialization source actually cloned and built. See `docs/engine_setup.md`
for the materialization path.

Current status detail (`PARTIAL`, missing capabilities, bridge protocol) likewise
lives in the manifest and in `docs/engine_setup.md`; it is not duplicated here.

## Historical provenance (not current truth)

Phase 8.5 prepared an earlier Forge path (`forge-2.0.13 @ 852066bf…`). That pin is
preserved only as provenance under `historical_phase85` in
`config/rules_engines.json` and in the Phase-8.5 artifacts. It must not be used
for new builds.

## Topology reminder

Forge remains a separate-process GPL-3.0 differential backend. This directory
contains no Forge runtime implementation: the qualified bounded Protocol-2.0.0
bridge lives in the owned Forge candidate source referenced by the manifest and
communicates over stdin/stdout JSONL from its own process. Lab consumes its
authoritative outputs only and never reproduces Forge rules. H4B remains
PARTIAL: unsupported decision classes (targets, modes, X, combat, triggers,
tuck, concede, replay, nonzero-mana execution) fail closed, global
legal/action/event capabilities stay false, and no provider is
production-selected (`provider_decision` in the manifest is `NO_PROVIDER_READY`).
