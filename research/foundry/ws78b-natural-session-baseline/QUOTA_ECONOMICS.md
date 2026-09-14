# WS78B Quota Economics

Rule: keep three legs strictly distinct. Any disagreement remains
`ACCOUNTING_UNKNOWN`. No leg is estimated into existence.

## Leg 1 — Provider-reported cost/usage (UNKNOWN)

- WS191: no `cost`/`tokens` keys in `metrics.jsonl` (1 launch line only);
  no export JSON in `/tmp/foundry-ws191-20260914-021713/`; launch-context
  `session` empty. Classification: UNKNOWN (DIRECTLY_VERIFIED absence).
- WS196: identical absence in `/tmp/foundry-ws196-20260914-022551/`.
  Classification: UNKNOWN (DIRECTLY_VERIFIED absence).
- `session_stats.py` emits `cost_usd` ONLY from an export's `info.cost`
  (DIRECTLY_VERIFIED source read). No export → no provider leg. Nothing in
  this namespace invents it.

## Leg 2 — Locally token-derived estimated cost (UNKNOWN)

- Formula (MODELED template, not a measurement):
  `estimate = input_tokens × input_rate + output_tokens × output_rate +
  cache_read_tokens × cache_read_rate (+ cache-write iff the provider
  exposes a separate charge)`.
- Inputs absent for both sessions (UNKNOWN), so no estimate is computed.
  Publishing a number here would be fabrication.
- Historical rate context (provenance only, NOT re-verified authority for
  this baseline): prior WS78 research recorded listed Muse Spark 1.3
  Contributor rates of $0.10 / $0.20 / $0.002 per 1M for input / output /
  cached read with no separately listed cached-write charge and a $60
  monthly usage figure. Those figures are NOT used as measured facts in
  this baseline; any future estimate must cite the rate source and date it
  was verified, then keep the result labeled MODELED until a provider leg
  confirms it.

## Leg 3 — OpenCode quota/accounting indicators (UNKNOWN)

- No quota-bar, balance, limit, or accounting snapshot exists in either run
  root (DIRECTLY_VERIFIED absence). Classification: UNKNOWN.
- Quota-dollar per milestone is therefore UNKNOWN for both sessions. The
  visible-activity ratios in `BASELINE_METRICS.md` (claims/hr, commits/hr)
  are throughput observations, not cost efficiency.

## Ledger verdict

`ACCOUNTING_CONSISTENCY = ACCOUNTING_UNKNOWN` (all three legs absent;
verified, not assumed). The mandatory fix is procedural, not analytical:
capture `opencode export` + `session_stats.py` summaries and any
provider-side usage snapshot after every future milestone, so the next
baseline has all three legs. See `SESSION_ROTATION_POLICY.md` (export gate)
and `MEASUREMENT_LIMITATIONS.md`.
