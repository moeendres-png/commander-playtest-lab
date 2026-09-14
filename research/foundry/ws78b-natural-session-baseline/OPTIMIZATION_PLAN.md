# WS78B Optimization Plan (ranked proposals — NOT implemented here)

Scope: proposals only. No implementation, no canonical change, no weaker
testing/evidence. Ranked by: useful-work/hour gain; useful-work/quota gain;
implementation cost; correctness risk; ownership overlap; required
requalification. Correctness risk is veto-grade: any proposal that weakens
Rules Correctness or evidence rigor is rejected regardless of efficiency.

## P0 — Mandatory export + metrics gate (enables everything else)

- What: enforce the `SESSION_ROTATION_POLICY.md` export gate
  (`opencode export` → `session_stats.py` → `metrics.py` AUTOCAPTURED) after
  every milestone.
- Useful-work/hour: indirect (diagnosis). Useful-work/quota: enables
  measurement. Cost: low. Correctness risk: none (read-only aggregation;
  raw exports LOCAL_ONLY). Overlap: Foundry tooling owner. Requalification:
  Foundry tool tests only.
- Rank: first — without this, every other gain is unmeasurable.

## P1 — Scope evidence-sealing indexes to workstream outputs

- Observation (CODE_DERIVED): WS191's 3674-entry artifact index is
  dominated by the config-dir snapshot including `node_modules`.
- Proposal: index workstream outputs + referenced config files by hash;
  record the config snapshot as one manifest hash instead of thousands of
  entries.
- Work/hour: small direct (less sealing I/O). Work/quota: negligible.
  Cost: low. Risk: low (index is evidence, not behavior) provided the
  manifest remains byte-exact. Requalification: evidence-tool tests.

## P2 — Compact continuation capsule (`/work` path, WS78 lineage)

- Proposal: reuse one stable session per workstream where safe; resume via
  an explicit session identity + compact derived capsule instead of pasting
  multi-thousand-token prompts; never ambiguous `--continue`.
- Work/hour: medium (less re-prompting). Work/quota: medium-high IF cache
  affinity holds (MODELED — prior WS78 research found the client sends a
  stable session key; cache hits still require export proof).
  Cost: medium. Risk: medium (stale-context resumption) — mitigated by
  source-lock/validated-head gates. Requalification: launcher + state +
  permission battery.

## P3 — Bound noisy tool/test output before model context

- Proposal: conservative `tool_output.max_lines/max_bytes` with guaranteed
  full-output recovery path (per WS78 research constraints).
- Work/hour: low-medium. Work/quota: medium (large Maven/log outputs are
  the likeliest dynamic-context source). Cost: low-medium. Risk: medium
  (truncated diagnostics) — gate on `TRUNCATION_RECOVERY`. Requalification:
  config + tooling tests with representative log cases.

## P4 — Skills-on-demand discipline

- Observation: skills load full bodies only on `skill`-tool call
  (DIRECTLY_VERIFIED prior research). Proposal: keep procedures in skills,
  advertise IDs only.
- Gains: low-medium / low-medium. Cost: low. Risk: low. Requalification:
  agent/skill tests.

## P5 — Deduplicate provably-redundant always-on instruction bytes

- Gains: low (stable policy is cheap when cached — prior adjudication).
  Cost: medium (proof burden). Risk: high if rushed — last, and only with
  machine-enforced invariance proof. Requalification: full Foundry + policy
  conformance.

## P6 — Calibrated rotation thresholds from P0 data

- After ≥5 export-backed sessions spanning HIGH/XHIGH, fit stall/token/
  cache-miss thresholds and promote `SESSION_ROTATION_THRESHOLD` from
  MODELED to calibrated. Not scheduled until P0 yields data.

## Rejected (not ranked)

- Weaker tests, smaller denominators, skipped validations, cache-hit
  claims without exports, silent provider fallback, paid A/B/volume
  benchmarking to "prove" savings, probing sibling worktrees for context.
