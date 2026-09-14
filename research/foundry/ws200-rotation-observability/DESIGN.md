# WS200 Design

## Objective

Evidence-honest, threshold-free session-rotation observability:
authoritative state + live Git/worktree facts + optional WS199 aggregates
-> pure factual observation -> `NO_ROTATION` or `REVIEW_PROMPT` advisory
-> capsule / launch context -> operator or worker may choose a fresh
compact continuation. WS200 never rotates the session; it only observes
and advises.

## Technical decisions (HIGH, from authoritative source evidence)

1. **Pure logic stays in `autonomy.py`, I/O in capsule/launcher.**
   No new helper module: the capsule already separates I/O from pure
   decisions, and a new module would widen the mutation surface without
   benefit. Import footprint unchanged (`re`, `collections.abc` only),
   so the WS198 purity regression still passes unmodified.
2. **No schema change.** Repeat detection takes an explicit
   `--previous-fingerprint` / `previous_observation` parameter instead of
   a persisted history field, so legacy states remain valid byte-for-byte
   and no migration is required. Conservative default stays `NO_ROTATION`.
3. **Fingerprint without new imports.** Deterministic 64-bit FNV-1a hex
   over the canonical repr of the six structural facts (no `hashlib` /
   `json` imports, keeping the purity test green; unlike builtin
   `hash()`, FNV-1a is stable across runs).
4. **Single exact repeat -> REVIEW_PROMPT, never forced rotation.**
   No "repeat N times" counter, no wall-clock, no token/time/commit
   thresholds anywhere. Telemetry values are not parameters of the
   recommendation functions by construction.
5. **Telemetry enrichment is render-only.** The capsule I/O layer proves
   `telemetry-status.json` `CAPTURED` + exact session match + per-field
   `AUTOCAPTURED` provenance before citing any value; all other shapes
   render the export-missing disclaimer. The launcher records only a
   boolean availability flag (never values) and never gates `LAUNCH_READY`.

## Non-goals enforced

No rotate-after-N rule of any kind (tokens, context %, minutes, commits,
cache ratio, cost, "looks large"); no hidden equivalent; no `os.kill` /
terminate / SIGTERM / automatic restart / `/compact` / provider-model
override in any rotation path (gated by tests + final-diff audit).
