# RQ-X1 — UNKNOWN Ledger (explicitly absent evidence; UNKNOWN != PASS)

Pin: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`. Every entry is UNKNOWN with
the cheapest closer. Nothing here may be cited as PASS, PARTIAL, or support
for provider selection / Architecture Freeze.

## Source-insufficient (needs runtime mirror M-1…M-5 or stays UNKNOWN)

| # | UNKNOWN | Why source cannot close it | Cheapest closer |
|---|---|---|---|
| U-1 | Wire legal sets complete + fail-closed AT RUNTIME | revalidation logic read, never executed; timing/concurrency paths (CALL vs GAME thread, 30 s timeout, last-writer-wins) unobserved | M-1 |
| U-2 | UUID+ZCC binding under real duplicate/stale/double-submit pressure | map-lookup logic read; zone-change races and double-apply behavior unobserved | M-2 |
| U-3 | Hidden-info safety under byte-level adversarial observation | projection logic read; actual bytes, log-string edge cases (all 1000s of card log paths), timing/ordering side channels unobserved | M-3 |
| U-4 | Empirical RNG-seed falsification | source predicts failure; only execution closes it as RUNTIME evidence | M-4 (R-A…R-D) |
| U-5 | Adapter-side journal re-drive boundary | recordability inferred from transient wire; re-drive divergence boundary unmeasured | M-5 |
| U-6 | 2–5P per-count conformance (each count separately) | variable-count architecture confirmed; zero runtime evidence at ANY count in RQ-X1 | per-count qualification (NOT part of any mirror; full campaign) |
| U-7 | Client-behavioral edge cases (undo, auto-pay, F-key skips at runtime) | `allowUndo` bookmark paths and skip logic read; interactive behavior unobserved | interactive session probing (mirror-adjacent; needs contract) |
| U-8 | Performance/lifecycle fitness (start/connect/shutdown, memory, 4P load) | J-P3B has bounded lifecycle evidence at OLD pin `06d166b`; nothing at `77d7646d` | bounded lifecycle probe (mirror-adjacent) |

## Out of scope for any mirror (needs full qualification or authority, not probing)

| # | UNKNOWN | Closer |
|---|---|---|
| U-9 | Card-level Rules correctness (any card, any interaction) | full qualification campaign + official-rules validation; test counts are not correctness |
| U-10 | Whether engine RNG/replay gaps are acceptable to the mission | AUTHORITY_GATE (Sol High): mission-scope tolerance for adapter-side determinism limits |
| U-11 | Provider selection / Architecture Freeze | AUTHORITY_GATE; explicitly NOT CLAIMED here |
| U-12 | Cross-pin validity (J-P3B `06d166b` results vs `77d7646d` source) | impact adjudication + required requalification before mixing pins |
| U-13 | License clearance for any reuse/port | LEGAL_REVIEW_REQUIRED (note MIT-not-GPL correction in source lock) |

## Downgrade/upgrade rules (binding on readers)

- CODE_DERIVED findings (R-1…R-6, C-1…C-5) become runtime-usable ONLY via
  M-1…M-5 or equivalent executed evidence. Until then they are architecture
  facts for planning, not qualification facts.
- Any single M-probe FAIL on a load-bearing claim (M-1 illegal echo executed;
  M-3 hidden-name leak; M-4 all-pass surprise without follow-up) INVALIDATES
  the corresponding reverser — recorded as invalidated, never smoothed over.
- Missing evidence stays UNKNOWN or explicitly absent. No inference, no
  backfill, no promotion.
