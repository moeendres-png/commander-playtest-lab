# Agent Efficiency Benchmark — measurement contract

Status: EXPERIMENTAL / MEASUREMENT-ONLY.

This layer extends the existing Foundry telemetry instead of inventing a second session
capture system. It does not change Rules authority, evidence authority, OpenCode routing,
model allowlists, `AGENTS.md`, context loading, tool permissions, or qualification.

## Inputs

1. Run the existing `tools/foundry/session_stats.py` over a LOCAL_ONLY
   `opencode export` and retain only its sanitized aggregate output.
2. Add an explicit benchmark-arm JSON record with:
   - identical `case_id`, task class, 40-hex source SHA and 64-hex fixture/contract digest
     for both A/B arms;
   - a case-bound required evidence class of `DIRECTLY_VERIFIED`,
     `TECHNICALLY_CONFORMANT`, or `EXTERNALLY_RULE_VALIDATED`;
   - the sanitized session summary, including distinct session ID plus agent/model/provider,
     variant and exact CLI version provenance;
   - technical outcome, final validation, evidence completeness/loss, evidence class,
     missed defects, unresolved review findings, scope violations, failed attempts,
     fix waves, checks run, and (only if directly known) context reloads.
3. Compare with `tools/foundry/agent_benchmark.py`.

Raw session exports remain LOCAL_ONLY and must never be committed or pasted into evidence.

## What is measured

When present in both arms:
- input/output/reasoning/cache tokens;
- wall time;
- model turns;
- total tool calls and direct `read`/`list` versus `grep`/`glob`/`lsp`
  call counts;
- patches;
- failed attempts, fix waves, checks run, and explicitly observed context reloads.

The direct read/search counts are deliberately named *direct*: shell-internal file reads are
not reconstructed from command text. The comparator preserves both sanitized session summaries
in the result so a measurement artifact remains self-describing. It rejects unknown schema
fields, duplicate/self-comparisons, CLI-version mismatches and any
`tool_calls_by_tool` total that does not equal `tool_calls`.

Tool-output byte volume is currently `UNAVAILABLE_FROM_SANITIZED_SESSION_STATS`; it stays
UNKNOWN until the pinned CLI exposes a safe aggregate or a separately qualified local collector
is added. Compaction count remains unavailable under the existing session exporter and must stay
`null`; it is never inferred.

## Quality-first loss rule

The baseline must itself pass the benchmark quality gate; a broken or under-evidenced
baseline is rejected rather than used to manufacture an apparent improvement. A candidate
is rejected for the pair if it loses evidence, misses a defect, leaves an unresolved review
finding, violates scope, lacks PASS final validation/technical outcome, or fails the
case-bound required evidence class. UNKNOWN/MODELED/SYNTHETIC evidence cannot satisfy the gate.

If a previously exercised baseline has nonzero checks and the candidate runs zero checks, the
candidate is rejected as a verification collapse. A candidate with missing core efficiency
metrics is INCONCLUSIVE, never a measured saving.

Every measured delta carries an explicit direction. Results distinguish improvement, mixed
efficiency, regression and no-change; a slower/more expensive pair is never hidden behind a
generic favorable disposition. Quality-rejected pairs return CLI exit code 3; malformed,
incomparable or unsafe input/output returns 2.

Benchmark outputs are write-once. Publication uses an atomic no-clobber link from a completed
temporary file, so an existing normal file, symlink or hard-link target is never overwritten.

Even a `PAIR_MEASURED_EFFICIENCY_IMPROVEMENT` result does **not** authorize a default harness
change. Default promotion needs representative repeated cases across at least:

- CI/gate failure diagnosis;
- Python qualification/row work;
- Mage/Forge Java bridge navigation;
- bounded bugfix;
- cross-file review.

A default change also goes through fresh-context review and the normal exact-head gates.

## Current baseline status (2026-10-05)

GitHub contains the telemetry/parser infrastructure but intentionally does not contain raw
OpenCode session exports. Therefore current real-session token/cache/time baseline values are
`UNKNOWN / NOT_AVAILABLE_FROM_GITHUB`. Synthetic unit fixtures prove parser behavior only;
they are not performance evidence.

No token/time saving is claimed by this workstream until real sanitized session summaries
from equivalent A/B runs are supplied.

## CLI result contract

- exit 0: valid non-rejected comparison (including measured regression/mixed/no-change or INCONCLUSIVE);
- exit 2: malformed/incomparable input or unsafe publication;
- exit 3: baseline/candidate quality rejection. The JSON result is still emitted or published so the rejection remains auditable.

A single pair always emits `default_promotion_authorized = false`.
