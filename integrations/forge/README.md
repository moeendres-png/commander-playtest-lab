# Forge bridge integration point

## Pin authority

The sole machine-readable authority for the current Forge pin is
`config/rules_engines.json` (`secondary_engine`: release, commit,
`source_archive`, license). This README must not restate the commit and must not
be read as a second pin source. If this file and the manifest ever disagree, the
manifest wins and this file is stale.

Current status detail (`PARTIAL`, missing capabilities, bridge protocol) likewise
lives in the manifest and in `docs/engine_setup.md`; it is not duplicated here.

## Historical provenance (not current truth)

Phase 8.5 prepared an earlier Forge path (`forge-2.0.13 @ 852066bf…`). That pin is
preserved only as provenance under `historical_phase85` in
`config/rules_engines.json` and in the Phase-8.5 artifacts. It must not be used
for new builds.

## Topology reminder

Forge remains a separate-process GPL-3.0 differential backend. This directory
contains no claimed Forge runtime. A real bridge must expose the current bridge
protocol version declared by the manifest and report actual capabilities rather
than assumed ones. No provider is production-selected (`provider_decision` in the
manifest is `NO_PROVIDER_READY`).
