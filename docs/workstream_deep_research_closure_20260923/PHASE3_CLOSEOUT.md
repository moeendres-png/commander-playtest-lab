# Phase 3 Closeout — P1 Hidden-Information & Decision-Family Closure

Source lock (execution): worktree HEAD `ce1823f0` on `2231ff4b`
(engine `1.4.61`/`db134b97`, seeds 424242).

## Rule honored: rerun before redesign — no new pilot API created.

## Executed + promoted (DIRECTLY_VERIFIED, exact fixture/count/seed)

- `MICRO_LAYERS → DIRECT` (`XmageFullGameMicroExecutionTest`: Humility layer-6
  ability removal + 7b/7c 2/2-vs-1/1 from engine-direct facts).
- `MICRO_TARGETS → DIRECT` (engine-offered 7-target set unfiltered, P2 by
  exact identity, {R} payment, 40→37 resolution).
- `PILOT_CHOOSE_MODE → DIRECT` (`XmageFullGameDecisionExecutionTest`: two
  Oracle modes engine-offered, Devil-token mode by exact identity,
  {3}{R}{R} payment, 3× `Devil Token` under P1).
- `NEGATIVE_FIRST_OPTION`: direct negative evidence WITHOUT promotion —
  forged option rejected typed (`ILLEGAL_ACTION`), decision stays parked
  (no fallback/skip), explicit Devil selection, parked-payment proof (3 polls,
  no auto-pass), explicit cancel returns to priority. The frozen terminal's
  terminate-with-failure half is SUPERSEDED (bridge supports the mode class);
  per §19 the cell stays UNKNOWN with this evidence pointer.

## UNKNOWN-blocker correction (executed analysis, not inference)

Many UNKNOWN cells are dimension-blocked, not merely unrunned:

- HIDDEN_01..19 + sentinel: require library identity + facedown → still
  unsupported (Phase 1 dispositions stand). Hand slices now covered
  (Phase 1 honeycard test); per-fixture HIDDEN runs need library/facedown
  follow-ups. Stay UNKNOWN with corrected reason.
- PILOT_CHOICE/PILE/REPLACEMENT_EFFECT (stack), TRIGGER_ORDER/CHOOSE_ABILITY
  (counters/temporal), MICRO_* stack/temporal/control variants: blocked per
  Phase 1 matrix. Stay UNKNOWN/BLOCKED-equivalent with exact reasons.
- RNG/REPLAY tapes (library zones): blocked; replay-method work is Phase 5.
- MICRO_COMBAT: battlefield-only BUT terminal needs combat-damage progression
  (temporal scope) → executor follow-up, not promotion.

## Rerun evidence (current bytes, all green)

43 tests: HiddenInformation, NameCanary(4), Ws92DecisionKindCensus,
Ws204DecisionKindCensus, BridgePlayerFailClosed(5), DecisionRejectionWs229(16),
NumericDomainWs229(12), Ws05Mulligan(2), StateObservation. Supporting roles
unchanged (no per-fixture exactness claimed).

## Argentum 4-pattern audit → ALREADY_IMPLEMENTED_VERIFIED, no code change

1. Perspective-scoped observation: `XmageFullGameStateRedactor` (actor-only
   hand/mana, grant scoping) + hidden/canary tests green.
2. Engine-authoritative legal options: projections with
   `xmage_option_metadata` (ability_type/source_name/object identity);
   harness selects by exact issued identity only.
3. Schema/version drift identity: `protocol_version` mismatch rejection
   (`JsonlBridge` + `XmageFullGameJsonlBridge`; `JsonlBridgeTest` rejects
   `999.0`); dimensions schema versioned (`1.1.0`).
4. Semantic state digest: requested/constructed digests + digest-credit tests.
   Heuristic fallback correctly absent everywhere audited.

## Census delta (this phase)

```text
DIRECT 9 → 12 (+MICRO_LAYERS, +MICRO_TARGETS, +PILOT_CHOOSE_MODE)
UNKNOWN 57 → 54
NOT_RUN_BLOCKED 28, SUPPORTING 13 unchanged
```
