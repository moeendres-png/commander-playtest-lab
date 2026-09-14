# WS78B Session Rotation Policy

Status: MODELED policy derived from verified gaps; no token-calibrated
threshold is claimed (every threshold below is a hypothesis until export
telemetry calibrates it). Rules Correctness outranks token efficiency; this
policy never weakens testing or evidence requirements.

## Why rotation policy cannot be token-based yet

Both natural sessions expose zero token telemetry (UNKNOWN, DIRECTLY_VERIFIED
absence). Any fixed token threshold today would be invented. The policy below
therefore triggers on observable milestone/artifact-time signals and —
critically — mandates the export capture that makes future token thresholds
possible.

## Mandatory export gate (the fix for this baseline's UNKNOWNs)

After every validated milestone AND at session end, before any rotation
decision:

1. Run `opencode export <session>` to a `LOCAL_ONLY` path outside the Git
   worktree (raw exports are never committed, never pasted into evidence —
   DIRECTLY_VERIFIED `session_stats.py` contract).
2. Aggregate with `tools/foundry/session_stats.py --export …` (turns, tool
   counts, token totals, cost, errors — absent keys stay absent).
3. Append one line via `tools/foundry/metrics.py` with `AUTOCAPTURED`
   provenance for machine-read fields.
4. Record only the aggregates in the state file / handoff.

A session with no export at its milestones is procedurally non-conformant
regardless of its engineering outcome.

## Rotation triggers (MODELED; calibrate with exports)

Rotate (checkpoint, seal evidence, start a fresh compact continuation) when
ANY holds:

1. **Milestone cadence stall**: no validated milestone for ~60–90 min of
   wall time on routine HIGH work (wider for XHIGH adjudication with
   recorded reasoning). Rationale (CODE_DERIVED): WS191 sealed 7 claims in
   ≥17.7 min visible; WS196 committed in ~10.3 min — healthy sessions here
   produced evidence in minutes, so an hour without a milestone is a stall
   signal, not patience.
2. **No-progress pattern**: repeated tool errors, retries, timeouts, or
   latency complaints across consecutive turns with no milestone advance.
   (No baseline rate exists — UNKNOWN — so the first calibrated sessions
   must log these counts via the export gate.)
3. **Context-growth without cache benefit**: export shows input/context
   growth with negligible `tokens_cache_read` ratio across turns. Never
   infer cache hits from context shape; the export is the authority.
4. **Checkpoint density**: after ~3 state patches or ~2 commits without
   Coordinator review on a complex port (WS191's observed density,
   CODE_DERIVED), seal and hand off rather than accumulating unreviewed
   context.
5. **Reported-context anomaly**: a credible report of very large context
   (e.g. the WS196 ~127k provenance-only report, UNKNOWN until verified)
   triggers an immediate export check; if verified and cache-poor, rotate
   to a fresh compact continuation rather than preserving the context.

## Fresh continuation vs preserving context

- A fresh compact continuation likely dominates when exports show large
  context + low cache-read ratio + stalled milestones (MODELED hypothesis).
- Preserving context is preferred when cache-read ratio is high and
  milestones advance (stable cached prefix is cheap; prior WS78 research,
  provenance only).
- Until exports exist, the tie-break is milestone cadence + checkpoint
  density, never anecdote. Anecdotal latency is never DIRECTLY_VERIFIED
  telemetry.

## Explicit non-goals

- No weaker testing, no weakened denominators/assertions, no synthetic PASS.
- No silent provider fallback; no probe of protected sibling worktrees to
  "recover" another session's context.
- No rotation INTO another active owner's branch/worktree (WS197 and all
  active surfaces remain untouched).

`SESSION_ROTATION_THRESHOLD = MODELED` (no measured token threshold;
UNKNOWN until export-calibrated).
