# Triage — PARTNER-TAX event obligations (2026-09-22)

Frozen obligations (`expected_events`): required `tax:cmd:P1-A:+4`,
`tax:cmd:P1-B:+0`; no forbidden/order/partial-order constraints. Script is
empty; procedure is CONSTRUCT + ENUMERATE_CAST_COSTS + RESOLVE_TO_TERMINAL.

## Per-obligation classification

| Required event | Class | Basis |
|---|---|---|
| `tax:cmd:P1-A:+4` | DERIVED | Engine-computed figure `{0}+{4}` (cost pipeline on a COMMAND-zoned ability copy) + watcher count 2 + CR 903.8 arithmetic. Asserted in `partnerTaxFiguresAreIndependent`. |
| `tax:cmd:P1-B:+0` | DERIVED | Engine-computed figure `{1}+{R}` (equals printed cost) + watcher count 0. Same test. |

## What is NOT claimed

- No engine event stream emits `tax:...` strings; no audit export is
  presented as event evidence. The engine emits no CAST_SPELL, MANA_PAID,
  or failure events in this flow (no casts, no payments — consistent with
  the empty script and the unpayable-from-board position).
- Native facts grounding the derivations: per-commander watcher counts
  (2 vs 0, read from the engine watcher), figure strings (engine cost
  pipeline output), distinct commander UUIDs, readback MATCH of the full
  starting state, readback equality around enumeration (purity: the query
  mutates nothing).

## Verdict

Both obligations SATISFIED in the derived-evidence class — the same class
as WS05 London bottom counts and TAX-2 `mana_paid`/`tax` derivations
(pool deltas, zone counts, watcher deltas read natively, arithmetic
documented). No engine-emitted contradiction exists (clean arrival, zero
engine failures on the path). The derivations are specific: swapped
histories swap figures and zero histories show no tax (negative controls
green), so the figures track histories rather than echoing expectations.
