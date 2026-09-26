# XMage Full-Game Migration Report

## Baseline reconstructed

The migration began from GitHub `main` commit `125be6a1c692177e328a59ffff0ea17390da1dae`, tree `af311b11f3d853aa2d5ca5e036af1f92fe06f8e1`, package `1.24.0`. The Google Drive current-status document was older than this software state and therefore was not used as the software pin.

The baseline already contained a real pinned XMage 1.4.61 bridge through B3/B4-F, but its validated external-control slice was intentionally incomplete. Generic legal-action/action-submission capability remained false, seed control was not promoted, and the compatibility `XmageBridgePlayer` still contained default/stub behavior outside its bounded validated decision class.

## Migration result

A new, explicit full-game lane is implemented rather than widening the compatibility bridge:

- `XmageFullGameDecisionController` — blocking, typed, fail-closed handoff;
- `XmageFullGameStateRedactor` — actor-scoped information projection;
- `XmageFullGamePlayer` — human-path XMage player forwarding Commander decisions;
- `XmageFullGameSession` — exactly 4P, explicit seed, one JVM/game;
- `XmageFullGameJsonlBridge` — dedicated `full-game` JSONL surface;
- `XmageFullGameRunner` — Python orchestration and Commander Lab pilot adapter;
- `XmageFullGameBatchRunner` — content-addressed resume/idempotency layer.

The old B3/B4 bridge keeps its historical capability truth. The new lane does not set global `legal_actions_supported` or `action_submission_supported` to true.

## Correctness hardening added during continuation

The continuation audit found and repaired three defects before release gating:

1. **Wire field mismatch** — Java emits `minimum_selections` / `maximum_selections`; the Python policy now consumes those canonical names, with the old aliases accepted only for compatibility.
2. **Replay RNG identity** — pilot stochastic RNG is no longer keyed by the random process-local XMage game UUID. It uses scenario seed, seat, decision offset and decision class.
3. **Transcript hidden-state retention** — actor-private `pilot_state` is no longer retained in exported audit transcripts. Only semantic option/decision metadata and state hashes are retained.

The continuation also removed remaining adapter-only discretionary shortcuts for boolean, pile, mana and scalar numeric choices: these are translated to pilot action views and decided through Commander Lab `BasePilot` methods.

## Rules and decision authority

- Rules authority: **XMage only**.
- Discretionary policy authority: **Commander Lab Our Pilots only**.
- Structural decision authority: **none**.
- Tactical decision authority: **none**.
- XMage AI authority: **none**.
- Random/default discretionary fallback: **none**.

Rules randomness remains inside XMage and is seeded through the pinned engine's `RandomUtil.setSeed(long)` before gameplay initialization.

## Information boundary

The acting pilot can see its own hand and mana, public zones and counts, and public stack information. It cannot see opponent hand identities or library order. Exported full-game transcripts do not retain per-decision private pilot state.

## Reproducibility and evidence

The dedicated conformance workflow builds the exact pinned XMage commit and executes a synthetic four-player Commander fixture to Game Over twice in fresh JVMs using the same seed. Semantic transcript equality is required. Raw-result identity is measured separately and does not automatically promote bit-exact replay.

All migration games are marked `technical_conformance_only`, `official_campaign_eligible=false`, `consumed_gameplay_evidence=false`, and `holdout_consumed=false`.

## Canonical-domain mutation

This migration does not alter canonical decklists, physical inventory quantities, allocations, purchase decisions, opponent observations or consumed/sealed holdout state.

## Remaining boundary

Passing this migration establishes a real end-to-end external-rules execution lane. It does **not** by itself authorize use of its technical fixture outcomes as deck-strength evidence. Any future official campaign must bind exact-main software, exact deck/opponent/pilot inputs and a fresh Decision Contract, then generate evidence under that separately authorized run.
