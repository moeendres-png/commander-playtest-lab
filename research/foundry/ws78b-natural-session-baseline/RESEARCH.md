# WS78B — Natural-Session Baseline Research

Date: 2026-09-14.
Workstream: `WS78B-NATURAL-BASELINE`, branch
`ws78b/natural-session-baseline-20260914` (DIRECTLY_VERIFIED via `git status`).
Source lock: audit base `7725570b6b8690daed6e645dc1611f5e196de8c5`
(DIRECTLY_VERIFIED via state file `audit_base_sha` and `git rev-parse HEAD`
at session start; tree clean).

This record is measurement/research only. It grants no Rules behavior credit,
no Production Provider selection, and no Architecture Freeze. It makes no
canonical Foundry, launcher, configuration, Forge, XMage, or simulator Rules
change (`CANONICAL_FOUNDRY_CHANGES = NONE`, DIRECTLY_VERIFIED via empty
`git diff --stat` at start and final diff review limited to
`research/foundry/ws78b-natural-session-baseline/`).

## Objective

Extract and quantify every useful measurement available from two natural
completed engineering sessions — WS191 (Forge bridge integration) and WS196
(Commander Lab cross-repo tool routing) — without artificial paid benchmarking,
and derive a defensible session-rotation, quota-efficiency, and throughput
baseline.

## Natural evidence sources (DIRECTLY_VERIFIED file presence)

- WS191 run root `/tmp/foundry-ws191-20260914-021713/`: 14 top-level entries
  including `launch-context.json`, `metrics.jsonl` (1 line),
  `state-patch-01/02/03.json`, `ws191-results.json`, `ws191-source-lock.json`,
  `ws191-evidence-report.md` (JSON handoff fragment), `ws191-handshake.py`,
  `ws191-handshake-transcript.jsonl`, `ws191-handshake-stderr.log`,
  `bridge-cp.txt`, `ws191-artifact-index.json` (3674 entries, CODE_DERIVED
  count), `config-dir/`.
- WS196 run root `/tmp/foundry-ws196-20260914-022551/`: 4 top-level entries:
  `launch-context.json`, `metrics.jsonl` (1 line),
  `ws196-checkpoint-patch.json`, `config-dir/`.
- Remotely published terminal identities (task-provided, provenance):
  WS191 Forge `7360737b7f1f3580eb51b7aca49bd1c0e72d9bff`;
  WS196 Commander Lab `691dbe504b8626a7e6e7a59cf994cc43777a8abf`.
  WS196 identity is independently DIRECTLY_VERIFIED in this repository via
  `git log --all --grep=WS196` and `git show 691dbe50` (commit, 6 files,
  +530/−0, AuthorDate 2026-09-14T00:36:23Z). WS191 Forge identity is not
  verifiable from this worktree (Forge is a separate repository; no reference
  root declared for this run): its bytes are provenance from the WS191 run
  root (`ws191-source-lock.json`, `ws191-results.json`, state file), not
  independently re-verified here.
- Dedicated state files (DIRECTLY_VERIFIED bytes):
  `.../ws191-forge-aa5c-h4f/WORKSTREAM_STATE.yaml`
  (`state_written_against_head` = `validated_head` = `7360737b…`,
  `current_reasoning_tier: xhigh`);
  `.../ws196-cross-repo-tool-routing/WORKSTREAM_STATE.yaml`
  (`state_written_against_head` = `validated_head` = `691dbe50…`,
  `current_reasoning_tier: high`).
- Canonical measurement tooling (DIRECTLY_VERIFIED source read):
  `tools/foundry/session_stats.py` (aggregates ONLY from an
  `opencode export <session>` JSON file; absent keys stay absent; compaction
  count reported unavailable, never inferred) and `tools/foundry/metrics.py`
  (JSONL records with `AUTOCAPTURED / CALLER_SUPPLIED /
  UNAVAILABLE_FROM_PINNED_CLI / UNKNOWN` provenance; values only from
  authoritative sources, never invented).

## Session identities (DIRECTLY_VERIFIED from both launch-contexts + metrics)

| Field | WS191 | WS196 |
|---|---|---|
| model | `opencode-go/muse-spark-1.3-contributor` | same |
| provider | `opencode-go` | same |
| reasoning lane | `xhigh` | `high` |
| execution override | `canonical` | `canonical` |
| variant resolution | `canonical_agent_variant` | same |
| OpenCode pin | `1.18.30` (ok: true) | same |
| repo profile | `forge` | `cpl` |
| task class | `workstream-session` | same |
| base SHA | `aa5c00aa…` (Forge Rules-Core lineage) | `7725570b…` (this repo HEAD) |
| launch-context session | `""` (empty) | `""` (empty) |

Consequence: no non-secret OpenCode session identifier is available in either
run root (DIRECTLY_VERIFIED). Any `opencode export` aggregation therefore has
no session key to target; no export file exists in either run root
(DIRECTLY_VERIFIED by top-level listings). All export-derived metrics below
are honestly UNKNOWN.

## What was directly measured vs what is UNKNOWN

Fully specified in `BASELINE_METRICS.json` / `BASELINE_METRICS.md`. Summary:

- DIRECTLY_VERIFIED: model, provider, lane, override, variant, CLI pin,
  repo profile, base SHAs, empty session field, run-dir file spans
  (WS191 00:17:28–00:35:12Z = 1064 s lower-bound visible activity; WS196
  00:26:02–00:37:27Z = 685 s lower bound), WS196 commit time 00:36:23Z inside
  its window, WS191 7 session-reported validated claims + bridge engine init
  7938 ms + 4-message handshake exit 0, WS196 6-file +530 commit + 12
  hermetic test functions authored (CODE_DERIVED blob count), both terminal
  states COMPLETE with matching `validated_head`, artifact-index size
  (3674 entries, WS191).
- UNKNOWN (explicitly, never estimated): input/output/reasoning tokens,
  cache-read/write tokens, model turns, tool calls, tool calls by tool, tool
  errors, retry/timeout/no-progress counts, true wall-clock session duration,
  context growth, provider-reported cost, quota/accounting indicators,
  WS196 test execution verdict, WS191 Forge-side independent revalidation
  from this worktree.
- The user-reported WS196 context size near 127k is provenance only
  (UNKNOWN until an export-backed `session_stats.py` summary verifies it).
  Anecdotal latency is not converted into telemetry.

## Headline comparative findings

1. Visible-activity rate (CODE_DERIVED ratios over lower-bound denominators;
   true session rates UNKNOWN): WS191 sealed 7 validated runtime claims in
   ≥17.7 min (≈23.7 claims/hr visible); WS196 authored 1 terminal commit
   carrying 12 hermetic test functions in ≥11.4 min (≈5.3 commits/hr,
   ≈63 test-functions/hr authored, execution verdict UNKNOWN).
   Denominators are run-dir mtime spans, not export `elapsed_seconds`.
2. Lane effect (XHIGH adjudication vs routine HIGH): WS191's bounded XHIGH
   adjudication produced the merge-base/delta analysis (state-patch-01) that
   unlocked a purely additive 35-file port with 7 fresh runtime validations;
   WS196 HIGH produced deterministic routing plus hermetic tests with no
   engine runtime. No HIGH-vs-XHIGH quality or cost equivalence is claimed
   (UNKNOWN beyond milestone shape).
3. Checkpoint frequency: WS191 3 state patches + 2 session-reported commits
   (port checkpoint + terminal); WS196 1 checkpoint patch + 1 terminal
   commit. Evidence-sealing overhead in WS191 included a 3674-entry artifact
   index dominated by the config-dir snapshot (including `node_modules`);
   future sealing should scope the index to workstream outputs.
4. Rotation: with zero token telemetry, no token-based threshold can be set
   from these sessions. The defensible policy (`SESSION_ROTATION_POLICY.md`)
   is milestone/artifact-time based plus a mandatory export-capture gate, so
   the next sessions actually produce the missing telemetry. A fresh compact
   continuation dominates preserving a very large context only when export
   evidence shows context growth without cache benefit — currently a MODELED
   hypothesis, not a measured result.

## What was deliberately NOT claimed

- No token, cache-hit, cost, turn, tool-call, latency, or context-growth
  number is reported as measured. Every such field is UNKNOWN.
- No provider-reported vs locally-estimated vs quota-bar disagreement is
  resolved: with all three legs absent the ledger stays
  `ACCOUNTING_UNKNOWN`.
- No HIGH-vs-XHIGH equivalence, no cache-hit inference from context shape,
  no PASS from missing telemetry, no synthetic benchmark.
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`.
  `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Outputs in this namespace

`RESEARCH.md` (this file), `BASELINE_METRICS.json`, `BASELINE_METRICS.md`,
`QUOTA_ECONOMICS.md`, `SESSION_ROTATION_POLICY.md`, `OPTIMIZATION_PLAN.md`,
`MEASUREMENT_LIMITATIONS.md`, `EVIDENCE_INDEX.md`, `HANDOFF.md`.
