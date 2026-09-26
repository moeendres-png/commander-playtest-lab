# RULES SERVICE PROTOCOL — WS-10R / RSP 1.1.0

**Canonical protocol identity:** `commander-lab.rules-service/1.1.0`

This is a **new authoritative rematerialization**. The original WS-10 bundle listed in `WS-10_FINAL_HANDOFF.md` could not be recovered from supplied files, Google Drive, or the target repository. Byte identity with the unavailable `commander-lab.rules-service/1.0.0` bundle is therefore `UNKNOWN`. The version is advanced to 1.1.0 to prevent false claims of byte/semantic identity.

## Authority separation

The provider Rules Core alone decides legal actions, costs, mana, stack, priority, targets, combat, triggers, replacement/prevention, continuous effects/layers, state-based actions, zones, copy/control, Commander, multiplayer, and rules randomness. Pilots choose only among provider-offered legal options. Adapters translate identifiers and transport data only; they may not reconstruct legality or synthesize missing choices.

## Session cardinality

A conforming production-capable provider must support independent 2P, 3P, 4P and 5P sessions. 6P is SHOULD. Player identity and live-player turn order are dynamic and are never encoded as a fixed four-seat semantic type.

## Actor-aware observation

Every pilot-visible field—including prompts, context, option IDs/labels/metadata, source/ability/pile metadata and events—must be filtered by the same viewer/knowledge model. `viewer_player_id`, decision subject, and actual decision authority are distinct protocol concepts.

## Decision frames

`DECISION_FRAME` binds a provider-owned legal-option set to `session_id`, `decision_id`, `state_revision` and a SHA-256 `options_digest`. Submission selects exact provider-offered option IDs or typed numeric/assignment payloads defined by the frame. Stale revisions/digests are rejected.

Unsupported production-reachable discretionary paths are terminal and never answered by first/random/default yes-no/internal AI/GUI/parent fallback.

## Replay and RNG

Rules RNG and pilot decisions are separate. Qualification evidence uses `ReplayManifest`, `RulesRngTape`, `DecisionTape`, semantic `EventTape`, and semantic checkpoints/state hashes. Required replay is clean-process semantic replay under the same manifest; process UUIDs, memory addresses, wall clock values and unstable serialization identities are excluded from semantic identity.

## Errors

Malformed requests, stale decisions, impossible cardinalities, unavailable provider capabilities, unsupported decisions and provider failures are typed failures. No error path may silently become PASS.
