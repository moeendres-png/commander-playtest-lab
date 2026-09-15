# ANNOUNCE_X_LIVE (P-A1 live half: DIRECTLY_VERIFIED)

## 1. Live-callback traversal (XmageNumericDomainWs229Test)

`announceXSmallAndLargeSpanSubmitInteriorValuesLive`: REAL `announceX`
callbacks on a real game object through the real bridge player +
controller transport + native submission.

- Frame 1: `announce_x`, context `{numeric_min: 0, numeric_max: 5}`,
  zero options. Submitted 1 (interior). Callback returned 1.
- Frame 2: `announce_x`, context `{numeric_min: 0, numeric_max: 100}`,
  zero options. Submitted 73 (interior — unofferable under the old
  {0,50,100} collapse). Callback returned 73; engine consumed it.
- Lossless projection asserted on the wire: `legal_options == []` with
  verbatim bounds (see LIVE_FRAME_CAPTURES.json for stable bytes).

## 2. Card-driven live fire (U5 probe, run-scoped /tmp/opencode/xprobe_announce.py)

2P Rograkh/Mountain/Blaze game, production Lab policy, deterministic pilot:

- The pilot cast Blaze at priority; the engine fired `announce_x` with
  context `{numeric_min: 0, numeric_max: 2147483647}` (Integer.MAX_VALUE —
  the pathological U1 case, observed empirically, not hypothesized).
- Lab descriptor path chose 2147483647 (benefit->max), submitted through
  the full JSONL lane; the engine CONSUMED it (game advanced to target
  selection + three mana_payment decisions).
- Post-fire dynamics (cancel then retry with empty pool) end in an
  engine-side activation failure; the identical sequence occurs on the
  unmodified base (stash experiment 2026-09-15) — pre-existing
  pilot/economy dynamics, not a WS229 effect.

## 3. Lab half (test_ws229_numeric_domain.py, bridge-shaped frames)

Benefit/detriment/neutral strategies at spans 5/100/16/17/10^9;
stochastic seeded draw in-domain; hostile max+1 and non-integer returns
fail closed. See POSITIVE_MATRIX_RESULTS P-A1.
